#!/usr/bin/env python3
"""
Run ED+MCMC pipeline on a single category and save metrics.
Compares MCMC-reconstructed direction with true neutrino direction.
"""

import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import argparse
import json
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

import tensorflow as tf
from scipy.interpolate import RegularGridInterpolator
import h5py


def load_cluster_images(cat_dir, cat_name, plane='X'):
    """Load 3-plane cluster images for all events in category."""
    cluster_dir = Path(cat_dir) / f"{cat_name}_cluster_images_tick3_ch2_min2_tot3_e2p0" / plane
    
    if not cluster_dir.exists():
        return None, None, None
    
    all_images = []
    all_event_ids = []
    all_energies = []
    
    for npz_file in sorted(cluster_dir.glob('*.npz')):
        data = np.load(npz_file, allow_pickle=True)
        images = data['images']
        metadata = data['metadata']
        
        event_ids = metadata[:, 0].astype(int)
        energies = metadata[:, 4]
        
        all_images.append(images)
        all_event_ids.append(event_ids)
        all_energies.append(energies)
    
    if not all_images:
        return None, None, None
    
    return np.concatenate(all_images), np.concatenate(all_event_ids), np.concatenate(all_energies)


def load_ed_model(model_path):
    """Load ED model."""
    model = tf.keras.models.load_model(model_path, compile=False)
    return model


def load_energy_cosine_pdf(pdf_path):
    """Load and create interpolator for energy-cosine PDF."""
    data = np.load(pdf_path)
    pdf_2d = data['pdf_2d']
    energy_bins = data['energy_bins']  # Shape: (n_energy, 2) with [min, max]
    cosine_bins = data['cosine_bin_centers']
    
    # Convert energy bins to centers
    energy_centers = energy_bins.mean(axis=1)
    
    interpolator = RegularGridInterpolator(
        (energy_centers, cosine_bins),
        pdf_2d,
        method='linear',
        bounds_error=False,
        fill_value=1e-10
    )
    
    return interpolator, energy_centers, cosine_bins


def load_true_neutrino_direction(cat_dir, cat_name):
    """Load true neutrino direction from tps ROOT files (constant for entire category)."""
    import uproot
    
    tps_dir = Path(cat_dir) / 'tps'
    
    # Load first ROOT file to get the neutrino direction
    root_files = sorted(tps_dir.glob('*.root'))
    if not root_files:
        return None
    
    with uproot.open(root_files[0]) as f:
        tree = f['tps']
        
        nu_px = tree['neutrino_px'].array(library='np')
        nu_py = tree['neutrino_py'].array(library='np')
        nu_pz = tree['neutrino_pz'].array(library='np')
        
        # Find first non-zero neutrino momentum
        for i in range(len(nu_px)):
            p_vec = np.array([nu_px[i], nu_py[i], nu_pz[i]])
            p_norm = np.linalg.norm(p_vec)
            
            if p_norm > 1e-10:
                # Normalize to unit vector
                return p_vec / p_norm
    
    return None


def compute_log_likelihood(direction, cluster_directions, cluster_energies, pdf_interpolator):
    """Compute log-likelihood for proposed direction."""
    direction = direction / np.linalg.norm(direction)
    
    cosines = np.dot(cluster_directions, direction)
    cosines = np.clip(cosines, -1.0, 1.0)
    
    points = np.column_stack([cluster_energies, cosines])
    pdf_values = pdf_interpolator(points)
    pdf_values = np.maximum(pdf_values, 1e-10)
    
    likelihood_terms = cosines * pdf_values
    likelihood_terms = np.maximum(likelihood_terms, 1e-10)
    
    log_likelihood = np.sum(np.log(likelihood_terms))
    
    return -log_likelihood


def run_mcmc_optimization(cluster_directions, cluster_energies, pdf_interpolator, n_trials=50):
    """Run MCMC optimization to find best direction."""
    current_dir = np.mean(cluster_directions, axis=0)
    current_dir = current_dir / np.linalg.norm(current_dir)
    current_ll = compute_log_likelihood(current_dir, cluster_directions, cluster_energies, pdf_interpolator)
    
    step_size = 0.1
    n_accepted = 0
    
    history = [current_dir.copy()]
    ll_history = [current_ll]
    
    for _ in range(n_trials):
        proposal = current_dir + np.random.normal(0, step_size, 3)
        proposal = proposal / np.linalg.norm(proposal)
        
        proposal_ll = compute_log_likelihood(proposal, cluster_directions, cluster_energies, pdf_interpolator)
        
        if proposal_ll < current_ll:
            current_dir = proposal
            current_ll = proposal_ll
            n_accepted += 1
        else:
            alpha = np.exp(current_ll - proposal_ll)
            if np.random.random() < alpha:
                current_dir = proposal
                current_ll = proposal_ll
                n_accepted += 1
        
        history.append(current_dir.copy())
        ll_history.append(current_ll)
    
    acceptance_rate = n_accepted / n_trials
    
    burn_in = len(history) // 2
    final_samples = np.array(history[burn_in:])
    mean_direction = np.mean(final_samples, axis=0)
    mean_direction = mean_direction / np.linalg.norm(mean_direction)
    
    return mean_direction, -current_ll, acceptance_rate


def process_event(event_id, X_images, U_images, V_images, X_event_ids, U_event_ids, V_event_ids, X_energies, 
                  ed_model, pdf_interpolator, true_neutrino_direction):
    """Process single event: run ED, MCMC, compare to truth."""
    
    X_mask = X_event_ids == event_id
    U_mask = U_event_ids == event_id
    V_mask = V_event_ids == event_id
    
    if not (X_mask.any() and U_mask.any() and V_mask.any()):
        return None
    
    event_X = X_images[X_mask]
    event_U = U_images[U_mask]
    event_V = V_images[V_mask]
    
    n_clusters = min(len(event_X), len(event_U), len(event_V))
    if n_clusters == 0:
        return None
    
    event_X = event_X[:n_clusters]
    event_U = event_U[:n_clusters]
    event_V = event_V[:n_clusters]
    
    if event_X.ndim == 3:
        event_X = event_X[..., np.newaxis]
        event_U = event_U[..., np.newaxis]
        event_V = event_V[..., np.newaxis]
    
    cluster_directions = ed_model.predict([event_X, event_U, event_V], verbose=0)
    
    norms = np.linalg.norm(cluster_directions, axis=1, keepdims=True)
    cluster_directions = cluster_directions / norms
    
    cluster_energies = X_energies[X_mask][:n_clusters]
    
    mcmc_direction, final_ll, acceptance_rate = run_mcmc_optimization(
        cluster_directions, cluster_energies, pdf_interpolator
    )
    
    cosine_angle = np.dot(mcmc_direction, true_neutrino_direction)
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0)
    angle_deg = np.degrees(np.arccos(cosine_angle))
    
    return {
        'event_id': int(event_id),
        'n_clusters': n_clusters,
        'cosine_angle': float(cosine_angle),
        'angle_deg': float(angle_deg),
        'mcmc_acceptance_rate': float(acceptance_rate),
        'mcmc_log_likelihood': float(final_ll),
        'true_direction': true_neutrino_direction.tolist(),
        'mcmc_direction': mcmc_direction.tolist()
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cat-dir', required=True)
    parser.add_argument('--cat-name', required=True)
    parser.add_argument('--ed-model', required=True)
    parser.add_argument('--energy-cosine-pdf', required=True)
    parser.add_argument('--output-dir', default='results/ed_mcmc_cats')
    parser.add_argument('--max-events', type=int, default=None)
    
    args = parser.parse_args()
    
    print(f"Processing category: {args.cat_name}")
    
    print("Loading cluster images...")
    X_images, X_event_ids, X_energies = load_cluster_images(args.cat_dir, args.cat_name, 'X')
    U_images, U_event_ids, U_energies = load_cluster_images(args.cat_dir, args.cat_name, 'U')
    V_images, V_event_ids, V_energies = load_cluster_images(args.cat_dir, args.cat_name, 'V')
    
    if X_images is None or U_images is None or V_images is None:
        print("✗ Failed to load cluster images")
        return
    
    print(f"  Loaded {len(X_images)} clusters")
    
    unique_events = np.unique(X_event_ids)
    if args.max_events:
        unique_events = unique_events[:args.max_events]
    
    print(f"  Processing {len(unique_events)} events")
    
    print("Loading ED model...")
    ed_model = load_ed_model(args.ed_model)
    
    print("Loading energy-cosine PDF...")
    pdf_interpolator, energy_bins, cosine_bins = load_energy_cosine_pdf(args.energy_cosine_pdf)
    
    print("Loading true neutrino direction...")
    true_neutrino_direction = load_true_neutrino_direction(args.cat_dir, args.cat_name)
    if true_neutrino_direction is None:
        print("✗ Failed to load true neutrino direction")
        return
    print(f"  ✓ True neutrino direction: [{true_neutrino_direction[0]:.6f}, {true_neutrino_direction[1]:.6f}, {true_neutrino_direction[2]:.6f}]")
    
    print("\nProcessing events...")
    results = []
    
    for i, event_id in enumerate(unique_events):
        result = process_event(event_id, X_images, U_images, V_images, X_event_ids, U_event_ids, V_event_ids, 
                              X_energies, ed_model, pdf_interpolator, true_neutrino_direction)
        
        if result is not None:
            results.append(result)
            print(f"  ✓ Event {event_id}: cos={result['cosine_angle']:.4f}, angle={result['angle_deg']:.2f}°")
        else:
            print(f"  ✗ Event {event_id}: failed")
    
    print(f"\n✓ Successfully processed {len(results)}/{len(unique_events)} events")
    
    if not results:
        print("✗ No results to save")
        return
    
    cosines = np.array([r['cosine_angle'] for r in results])
    angles = np.array([r['angle_deg'] for r in results])
    
    summary = {
        'cat_name': args.cat_name,
        'n_events': len(results),
        'mean_cosine': float(np.mean(cosines)),
        'median_cosine': float(np.median(cosines)),
        'std_cosine': float(np.std(cosines)),
        'p68_cosine': float(np.percentile(cosines, 68)),
        'mean_angle_deg': float(np.mean(angles)),
        'median_angle_deg': float(np.median(angles)),
        'p68_angle_deg': float(np.percentile(angles, 68)),
    }
    
    print("\nSummary:")
    print(f"  68th percentile cos(angle): {summary['p68_cosine']:.4f}")
    print(f"  Median cos(angle): {summary['median_cosine']:.4f}")
    
    output_dir = Path(args.output_dir) / args.cat_name
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / 'metrics.json'
    output_data = {
        'cat_name': args.cat_name,
        'summary': summary,
        'events': results
    }
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n✓ Results saved to: {output_file}")


if __name__ == '__main__':
    main()
