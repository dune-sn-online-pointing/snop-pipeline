#!/usr/bin/env python3
"""
Run ED+MCMC using TRUE main tracks (skip MT identification).
This bypasses the MT classifier and feeds all true electron tracks to ED.
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
import uproot


def load_true_main_tracks(cat_dir, cat_name):
    """Load TRUE main track cluster images from matched_clusters."""
    # In the cluster metadata, we can identify main tracks
    # Column 10 appears to be particle_energy and column 11 is cluster_energy
    # We want clusters that are main tracks (electron tracks from CC interactions)
    
    cluster_dir = Path(cat_dir) / f"{cat_name}_cluster_images_tick3_ch2_min2_tot3_e2p0"
    
    X_images, U_images, V_images = [], [], []
    X_events, U_events, V_events = [], [], []
    X_energies = []
    
    # Load from all planes
    for npz_file in sorted((cluster_dir / 'X').glob('*.npz')):
        data = np.load(npz_file, allow_pickle=True)
        images = data['images']
        metadata = data['metadata']
        
        # Metadata: [event, plane, interaction_type, particle_id, ...]
        # interaction_type==1 means CC (charged current)
        # We want main tracks: particle_id==0 or similar
        
        # For now, take ALL clusters from CC events
        # Column 2 is interaction_type (1=CC, 0=NC)
        cc_mask = metadata[:, 2] == 1
        
        X_images.append(images[cc_mask])
        X_events.append(metadata[cc_mask, 0].astype(int))
        
        # Energy from column 10 (particle energy) or 11 (cluster energy)
        # Use column 10 since it's the true particle energy
        energies = metadata[cc_mask, 10]
        X_energies.append(energies)
    
    for npz_file in sorted((cluster_dir / 'U').glob('*.npz')):
        data = np.load(npz_file, allow_pickle=True)
        metadata = data['metadata']
        cc_mask = metadata[:, 2] == 1
        U_images.append(data['images'][cc_mask])
        U_events.append(metadata[cc_mask, 0].astype(int))
    
    for npz_file in sorted((cluster_dir / 'V').glob('*.npz')):
        data = np.load(npz_file, allow_pickle=True)
        metadata = data['metadata']
        cc_mask = metadata[:, 2] == 1
        V_images.append(data['images'][cc_mask])
        V_events.append(metadata[cc_mask, 0].astype(int))
    
    return (np.concatenate(X_images), np.concatenate(X_events), np.concatenate(X_energies),
            np.concatenate(U_images), np.concatenate(U_events),
            np.concatenate(V_images), np.concatenate(V_events))


def load_ed_model(model_path):
    """Load ED model."""
    model = tf.keras.models.load_model(model_path, compile=False)
    return model


def load_energy_cosine_pdf(pdf_path):
    """Load and create interpolator for energy-cosine PDF."""
    data = np.load(pdf_path)
    pdf_2d = data['pdf_2d']
    energy_bins = data['energy_bins']
    cosine_bins = data['cosine_bin_centers']
    
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
    """Load true neutrino direction from tps ROOT files."""
    tps_dir = Path(cat_dir) / 'tps'
    
    root_files = sorted(tps_dir.glob('*.root'))
    if not root_files:
        return None
    
    with uproot.open(root_files[0]) as f:
        tree = f['tps']
        
        nu_px = tree['neutrino_px'].array(library='np')
        nu_py = tree['neutrino_py'].array(library='np')
        nu_pz = tree['neutrino_pz'].array(library='np')
        
        for i in range(len(nu_px)):
            p_vec = np.array([nu_px[i], nu_py[i], nu_pz[i]])
            p_norm = np.linalg.norm(p_vec)
            
            if p_norm > 1e-10:
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
    parser.add_argument('--output-dir', default='results/ed_mcmc_true_tracks')
    parser.add_argument('--max-events', type=int, default=None)
    
    args = parser.parse_args()
    
    print(f"Processing category: {args.cat_name} (using TRUE main tracks)")
    
    print("Loading TRUE main track clusters...")
    X_images, X_event_ids, X_energies, U_images, U_event_ids, V_images, V_event_ids = load_true_main_tracks(args.cat_dir, args.cat_name)
    
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
            if len(results) <= 5 or (len(results) % 10 == 0):
                print(f"  ✓ Event {event_id}: cos={result['cosine_angle']:.4f}, angle={result['angle_deg']:.2f}°, n_clusters={result['n_clusters']}")
    
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
