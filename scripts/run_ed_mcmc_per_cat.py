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

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import tensorflow as tf
from scipy.interpolate import RegularGridInterpolator
from scipy.optimize import minimize
import h5py


def load_cluster_images(cat_dir, cat_name, plane='X'):
    """Load 3-plane cluster images for all events in category."""
    cluster_dir = Path(cat_dir) / f"{cat_name}_cluster_images_tick3_ch2_min2_tot3_e2p0" / plane
    
    if not cluster_dir.exists():
        return None, None, None
    
    all_images = []
    all_event_ids = []
    all_energies = []
    
    # Load all .npz files
    for npz_file in sorted(cluster_dir.glob('*.npz')):
        data = np.load(npz_file, allow_pickle=True)
        images = data['images']
        metadata = data['metadata']
        
        # Metadata columns: [event_id, plane, interaction_type, particle_id, cluster_energy, px, py, pz, ...]
        # Extract event IDs (column 0) and cluster energies (column 4)
        event_ids = metadata[:, 0].astype(int)
        energies = metadata[:, 4]
        
        all_images.append(images)
        all_event_ids.append(event_ids)
        all_energies.append(energies)
    
    if not all_images:
        return None, None, None
    
    return np.concatenate(all_images), np.concatenate(all_event_ids), np.concatenate(all_energies)


def load_ed_model(model_path):
    """Load ED model with proper custom object registration."""
    # ED v50 doesn't need custom loss functions
    model = tf.keras.models.load_model(model_path, compile=False)
    return model


def load_energy_cosine_pdf(pdf_path):
    """Load and create interpolator for energy-cosine PDF."""
    data = np.load(pdf_path)
    pdf_2d = data['pdf_2d']  # Shape: (n_energy_bins, n_cosine_bins)
    energy_bins = data['energy_bins']  # Shape: (n_energy_bins, 2) - edges
    cosine_bin_centers = data['cosine_bin_centers']
    
    # Convert energy bins from edges to centers
    energy_centers = energy_bins.mean(axis=1)
    
    # Create interpolator
    interpolator = RegularGridInterpolator(
        (energy_centers, cosine_bin_centers),
        pdf_2d,
        method='linear',
        bounds_error=False,
        fill_value=1e-10
    )
    
    return interpolator, energy_centers, cosine_bin_centers


def load_true_direction(cat_dir, cat_name, event_id):
    """Load true neutrino direction from volume metadata."""
    metadata_file = Path(cat_dir) / f"{cat_name}_volume_metadata.h5"
    
    with h5py.File(metadata_file, 'r') as f:
        # Find index for this event
        event_ids = f['event_ids'][:]
        idx = np.where(event_ids == event_id)[0]
        
        if len(idx) == 0:
            return None
        
        idx = idx[0]
        
        # Get momentum components
        px = f['main_track_momentum_x'][idx]
        py = f['main_track_momentum_y'][idx]
        pz = f['main_track_momentum_z'][idx]
        
        # Normalize to unit vector
        p_vec = np.array([px, py, pz])
        p_norm = np.linalg.norm(p_vec)
        
        if p_norm < 1e-10:
            return None
        
        return p_vec / p_norm


def load_cluster_energies(cat_dir, cat_name, event_id, X_energies, X_event_ids):
    """Get cluster energies for an event from already-loaded data."""
    mask = X_event_ids == event_id
    if not mask.any():
        return None
    return X_energies[mask]


def compute_log_likelihood(direction, cluster_directions, cluster_energies, pdf_interpolator):
    """
    Compute log-likelihood for proposed direction.
    log L = Σ log[cos(θ_i) * P(E_i, cos(θ_i))]
    """
    # Normalize direction
    direction = direction / np.linalg.norm(direction)
    
    # Compute cosines with all cluster directions
    cosines = np.dot(cluster_directions, direction)
    cosines = np.clip(cosines, -1.0, 1.0)
    
    # Query PDF values
    points = np.column_stack([cluster_energies, cosines])
    pdf_values = pdf_interpolator(points)
    pdf_values = np.maximum(pdf_values, 1e-10)
    
    # Compute likelihood terms
    likelihood_terms = cosines * pdf_values
    likelihood_terms = np.maximum(likelihood_terms, 1e-10)
    
    log_likelihood = np.sum(np.log(likelihood_terms))
    
    return -log_likelihood  # Return negative for minimization


def run_mcmc_optimization(cluster_directions, cluster_energies, pdf_interpolator, n_trials=50):
    """
    Run MCMC optimization to find best direction.
    Returns: (best_direction, log_likelihood, acceptance_rate)
    """
    # Initial guess: mean of cluster directions
    current_dir = np.mean(cluster_directions, axis=0)
    current_dir = current_dir / np.linalg.norm(current_dir)
    current_ll = compute_log_likelihood(current_dir, cluster_directions, cluster_energies, pdf_interpolator)
    
    # MCMC parameters
    step_size = 0.1
    n_accepted = 0
    
    history = [current_dir.copy()]
    ll_history = [current_ll]
    
    for _ in range(n_trials):
        # Propose new direction
        proposal = current_dir + np.random.normal(0, step_size, 3)
        proposal = proposal / np.linalg.norm(proposal)
        
        # Compute likelihood
        proposal_ll = compute_log_likelihood(proposal, cluster_directions, cluster_energies, pdf_interpolator)
        
        # Metropolis-Hastings acceptance
        if proposal_ll < current_ll:  # Better (lower negative log-likelihood)
            current_dir = proposal
            current_ll = proposal_ll
            n_accepted += 1
        else:
            # Accept with probability
            alpha = np.exp(current_ll - proposal_ll)
            if np.random.random() < alpha:
                current_dir = proposal
                current_ll = proposal_ll
                n_accepted += 1
        
        history.append(current_dir.copy())
        ll_history.append(current_ll)
    
    acceptance_rate = n_accepted / n_trials
    
    # Return mean of last 50% of samples (burn-in)
    burn_in = len(history) // 2
    final_samples = np.array(history[burn_in:])
    mean_direction = np.mean(final_samples, axis=0)
    mean_direction = mean_direction / np.linalg.norm(mean_direction)
    
    return mean_direction, -current_ll, acceptance_rate


def process_event(event_id, X_images, U_images, V_images, X_event_ids, U_event_ids, V_event_ids, X_energies, ed_model, pdf_interpolator, 
                  cat_dir, cat_name):
    """Process single event: run ED, MCMC, compare to truth."""
    
    # Get indices for this event from each plane
    X_mask = X_event_ids == event_id
    U_mask = U_event_ids == event_id
    V_mask = V_event_ids == event_id
    
    if not (X_mask.any() and U_mask.any() and V_mask.any()):
        return None
    
    # Get cluster images for this event
    event_X = X_images[X_mask]
    event_U = U_images[U_mask]
    event_V = V_images[V_mask]
    
    # Check all planes have same number of clusters
    if not (len(event_X) == len(event_U) == len(event_V)):
        return None
    
    # Ensure 4D shape: (n_clusters, 128, 32, 1)
    if event_X.ndim == 3:
        event_X = event_X[..., np.newaxis]
        event_U = event_U[..., np.newaxis]
        event_V = event_V[..., np.newaxis]
    
    # Run ED inference
    cluster_directions = ed_model.predict([event_X, event_U, event_V], verbose=0)
    
    # Normalize directions
    norms = np.linalg.norm(cluster_directions, axis=1, keepdims=True)
    cluster_directions = cluster_directions / norms
    
    # Get cluster energies
    cluster_energies = load_cluster_energies(cat_dir, cat_name, event_id, X_energies, X_event_ids)
    if cluster_energies is None or len(cluster_energies) != len(cluster_directions):
        return None
    
    # Run MCMC optimization
    mcmc_direction, final_ll, acceptance_rate = run_mcmc_optimization(
        cluster_directions, cluster_energies, pdf_interpolator
    )
    
    # Load true direction
    true_direction = load_true_direction(cat_dir, cat_name, event_id)
    if true_direction is None:
        return None
    
    # Compute angle
    cosine_angle = np.dot(mcmc_direction, true_direction)
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0)
    angle_deg = np.degrees(np.arccos(cosine_angle))
    
    return {
        'event_id': int(event_id),
        'n_clusters': len(cluster_directions),
        'cosine_angle': float(cosine_angle),
        'angle_deg': float(angle_deg),
        'mcmc_acceptance_rate': float(acceptance_rate),
        'mcmc_log_likelihood': float(final_ll),
        'true_direction': true_direction.tolist(),
        'mcmc_direction': mcmc_direction.tolist()
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cat-dir', required=True, help='Category directory (e.g., /path/to/cat000010)')
    parser.add_argument('--cat-name', required=True, help='Category name (e.g., cat000010)')
    parser.add_argument('--ed-model', required=True, help='Path to ED model')
    parser.add_argument('--energy-cosine-pdf', required=True, help='Path to energy-cosine PDF file')
    parser.add_argument('--output-dir', default='results/ed_mcmc_cats', help='Output directory for results')
    parser.add_argument('--max-events', type=int, default=None, help='Max events to process (for testing)')
    
    args = parser.parse_args()
    
    print(f"Processing category: {args.cat_name}")
    print(f"  Category directory: {args.cat_dir}")
    
    # Load 3-plane cluster images
    print("Loading cluster images...")
    X_images, X_event_ids, X_energies = load_cluster_images(args.cat_dir, args.cat_name, 'X')
    U_images, U_event_ids, U_energies = load_cluster_images(args.cat_dir, args.cat_name, 'U')
    V_images, V_event_ids, V_energies = load_cluster_images(args.cat_dir, args.cat_name, 'V')
    
    if X_images is None or U_images is None or V_images is None:
        print("✗ Failed to load cluster images")
        return
    
    print(f"  Loaded {len(X_images)} clusters (X), {len(U_images)} (U), {len(V_images)} (V)")
    
    # Get unique event IDs
    unique_events = np.unique(X_event_ids)
    if args.max_events:
        unique_events = unique_events[:args.max_events]
    
    print(f"  Processing {len(unique_events)} events")
    
    # Load ED model
    print("Loading ED model...")
    ed_model = load_ed_model(args.ed_model)
    print(f"  ✓ Model loaded: {ed_model.input_shape} → {ed_model.output_shape}")
    
    # Load energy-cosine PDF
    print("Loading energy-cosine PDF...")
    pdf_interpolator, energy_bins, cosine_bins = load_energy_cosine_pdf(args.energy_cosine_pdf)
    print(f"  ✓ PDF loaded: {len(energy_bins)} energy bins, {len(cosine_bins)} cosine bins")
    
    # Process events
    print("\nProcessing events...")
    results = []
    
    for i, event_id in enumerate(unique_events):
        if (i + 1) % 10 == 0:
            print(f"  Progress: {i+1}/{len(unique_events)} events")
        
        result = process_event(event_id, X_images, U_images, V_images, X_event_ids, U_event_ids, V_event_ids, X_energies, ed_model, 
                              pdf_interpolator, args.cat_dir, args.cat_name)
        
        if result is not None:
            results.append(result)
    
    print(f"\n✓ Successfully processed {len(results)}/{len(unique_events)} events")
    
    if not results:
        print("✗ No results to save")
        return
    
    # Compute summary statistics
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
    
    print("\nSummary statistics:")
    print(f"  68th percentile cos(angle): {summary['p68_cosine']:.4f}")
    print(f"  Mean cos(angle): {summary['mean_cosine']:.4f}")
    print(f"  Median cos(angle): {summary['median_cosine']:.4f}")
    
    # Save results
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
