#!/usr/bin/env python3
"""
Scenario 2: ED NETWORK - SN Pointing Performance with perfect channel tagging
Feeds all TRUE ES main tracks through ED network (assumes perfect CT).
No MT inference, no CT inference - perfect channel identification assumed.

Loads exactly 325 ES + 3300 CC samples per category.
"""

import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import argparse
import json
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from python.sn_sample_utils import validate_cat_samples, get_sample_event_ids, save_scenario_results
from scipy.interpolate import RegularGridInterpolator
import tensorflow as tf


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
    """Load true neutrino direction from tpstream ROOT files."""
    import uproot
    import glob
    import numpy as np
    
    tpstreams_dir = Path(cat_dir) / "tpstreams"
    if not tpstreams_dir.exists():
        raise FileNotFoundError(f"tpstreams directory not found: {tpstreams_dir}")
    
    # Find all tpstream files (both ES and CC)
    tpstream_files = list(tpstreams_dir.glob("*_tpstream.root"))
    if not tpstream_files:
        raise FileNotFoundError(f"No tpstream files found in: {tpstreams_dir}")
    
    directions = {}
    
    # Load from all tpstream files
    for tpstream_path in tpstream_files:
        try:
            with uproot.open(tpstream_path) as f:
                mctruths = f['triggerAnaDumpTPs/mctruths']
                
                # Load the data
                pdg = mctruths['pdg'].array(library='np')
                px = mctruths['px'].array(library='np')
                py = mctruths['py'].array(library='np')
                pz = mctruths['pz'].array(library='np')
                event_ids = mctruths['Event'].array(library='np')
                
                # Find neutrinos (PDG codes: 12, 14, 16 for nu_e, nu_mu, nu_tau and their anti-particles)
                neutrino_mask = np.abs(pdg) == 12  # electron neutrinos
                neutrino_mask |= np.abs(pdg) == 14  # muon neutrinos  
                neutrino_mask |= np.abs(pdg) == 16  # tau neutrinos
                
                # Create direction vectors for neutrinos
                for i in np.where(neutrino_mask)[0]:
                    evt_id = int(event_ids[i])
                    p_x, p_y, p_z = px[i], py[i], pz[i]
                    norm = np.sqrt(p_x**2 + p_y**2 + p_z**2)
                    if norm > 0:
                        directions[evt_id] = np.array([p_x/norm, p_y/norm, p_z/norm])
        except Exception as e:
            print(f"Warning: Could not load {tpstream_path}: {e}")
            continue
    
    return directions


def load_true_electron_tracks(cat_dir, cat_name, event_ids):
    """
    Load TRUE main electron tracks (CC events only) for specified event IDs.
    Returns cluster images for ED inference, matched across all three planes.
    """
    # Use centralized loading function that matches clusters across planes
    from python.sn_sample_utils import load_filtered_cluster_images
    
    cluster_data = load_filtered_cluster_images(cat_dir, cat_name, event_ids)
    
    # Filter for CC events only (is_es_interaction == 0, column 3 in metadata)
    if len(cluster_data['X_metadata']) == 0:
        return {
            'X_images': np.array([]), 'X_events': np.array([]),
            'X_energies': np.array([]), 'X_metadata': np.array([]),
            'U_images': np.array([]), 'U_events': np.array([]),
            'V_images': np.array([]), 'V_events': np.array([]),
            'n_input_clusters': cluster_data.get('n_input_clusters', 0),
            'n_matched_clusters': 0
        }
    
    is_es = cluster_data['X_metadata'][:, 3].astype(int)  # Column 3: is_es_interaction
    cc_mask = is_es == 0  # CC events have is_es_interaction == 0
    
    return {
        'X_images': cluster_data['X_images'][cc_mask],
        'X_events': cluster_data['X_events'][cc_mask],
        'X_energies': cluster_data['X_metadata'][cc_mask, 11],  # Column 11: true_particle_energy
        'X_metadata': cluster_data['X_metadata'][cc_mask],
        'U_images': cluster_data['U_images'][cc_mask],
        'U_events': cluster_data['U_events'][cc_mask],
        'V_images': cluster_data['V_images'][cc_mask],
        'V_events': cluster_data['V_events'][cc_mask],
        'n_input_clusters': cluster_data.get('n_input_clusters', 0),
        'n_matched_clusters': cluster_data.get('n_matched_clusters', 0)
    }


def run_ed_inference(ed_model, X_images, U_images, V_images, batch_size=512):
    """
    Run ED model inference on cluster images.
    Returns predicted directions (theta, phi in radians).
    """
    n_clusters = len(X_images)
    
    # ED model expects 3 inputs: [X, U, V] images
    predictions = ed_model.predict([X_images, U_images, V_images], batch_size=batch_size, verbose=0)
    
    # predictions shape: (n_clusters, 2) - [theta, phi]
    theta = predictions[:, 0]
    phi = predictions[:, 1]
    
    # Convert to Cartesian unit vectors
    directions = np.zeros((n_clusters, 3))
    directions[:, 0] = np.sin(theta) * np.cos(phi)
    directions[:, 1] = np.sin(theta) * np.sin(phi)
    directions[:, 2] = np.cos(theta)
    
    return directions


def compute_log_likelihood(direction, cluster_directions, cluster_energies, pdf_interpolator):
    """Compute log-likelihood for MCMC."""
    direction = direction / np.linalg.norm(direction)
    
    cosines = np.sum(cluster_directions * direction, axis=1)
    cosines = np.clip(cosines, -1.0, 1.0)
    
    points = np.column_stack([cluster_energies, cosines])
    probs = pdf_interpolator(points)
    probs = np.maximum(probs, 1e-10)
    
    log_like = np.sum(np.log(probs))
    return log_like


def run_mcmc_optimization(cluster_directions, cluster_energies, pdf_interpolator, n_trials=50):
    """Run MCMC optimization with multiple random starts."""
    best_direction = None
    best_log_like = -np.inf
    
    for trial in range(n_trials):
        theta = np.random.uniform(0, np.pi)
        phi = np.random.uniform(0, 2*np.pi)
        init_dir = np.array([
            np.sin(theta) * np.cos(phi),
            np.sin(theta) * np.sin(phi),
            np.cos(theta)
        ])
        
        current_dir = init_dir.copy()
        current_log_like = compute_log_likelihood(current_dir, cluster_directions, cluster_energies, pdf_interpolator)
        
        n_steps = 1000
        proposal_scale = 0.1
        
        for step in range(n_steps):
            proposal = current_dir + np.random.normal(0, proposal_scale, 3)
            proposal = proposal / np.linalg.norm(proposal)
            
            proposal_log_like = compute_log_likelihood(proposal, cluster_directions, cluster_energies, pdf_interpolator)
            
            if proposal_log_like > current_log_like:
                current_dir = proposal
                current_log_like = proposal_log_like
            else:
                accept_prob = np.exp(proposal_log_like - current_log_like)
                if np.random.rand() < accept_prob:
                    current_dir = proposal
                    current_log_like = proposal_log_like
        
        if current_log_like > best_log_like:
            best_log_like = current_log_like
            best_direction = current_dir
    
    return best_direction, best_log_like


def process_event(event_id, cluster_data, ed_directions, pdf_interpolator, true_nu_direction):
    """Process one event: use ED directions + MCMC."""
    X_mask = cluster_data['X_events'] == event_id
    
    if not np.any(X_mask):
        return None
    
    cluster_energies = cluster_data['X_energies'][X_mask]
    cluster_directions = ed_directions[X_mask]
    
    # Filter out invalid directions
    valid_mask = np.linalg.norm(cluster_directions, axis=1) > 0
    cluster_energies = cluster_energies[valid_mask]
    cluster_directions = cluster_directions[valid_mask]
    
    if len(cluster_energies) == 0:
        return None
    
    # Normalize directions
    cluster_directions = cluster_directions / np.linalg.norm(cluster_directions, axis=1, keepdims=True)
    
    # Run MCMC
    best_direction, best_log_like = run_mcmc_optimization(cluster_directions, cluster_energies, pdf_interpolator)
    
    # Compute angular resolution
    if true_nu_direction is not None:
        cos_angle = np.dot(best_direction, true_nu_direction)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        angular_error_deg = np.degrees(np.arccos(cos_angle))
    else:
        angular_error_deg = None
    
    return {
        'event_id': int(event_id),
        'n_clusters': int(len(cluster_energies)),
        'best_direction': best_direction.tolist(),
        'best_log_like': float(best_log_like),
        'angular_error_deg': float(angular_error_deg) if angular_error_deg is not None else None,
        'true_nu_direction': true_nu_direction.tolist() if true_nu_direction is not None else None
    }


def main():
    parser = argparse.ArgumentParser(description='ED network SN analysis with perfect channel tagging')
    parser.add_argument('--cat-dir', required=True, help='Category directory')
    parser.add_argument('--cat-name', required=True, help='Category name (e.g., cat000001)')
    parser.add_argument('--ed-model', required=True, help='Path to ED model')
    parser.add_argument('--energy-cosine-pdf', required=True, help='Path to energy-cosine PDF .npz')
    parser.add_argument('--output-dir', required=True, help='Output directory')
    parser.add_argument('--n-es', type=int, default=325, help='Number of ES samples (default: 325)')
    parser.add_argument('--n-cc', type=int, default=3300, help='Number of CC samples (default: 3300)')
    parser.add_argument('--batch-size', type=int, default=512, help='ED inference batch size')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    
    args = parser.parse_args()
    
    # Validate samples
    print(f"\n{'='*70}")
    print(f"SCENARIO 2: ED NETWORK (PERFECT TAGGING) - {args.cat_name}")
    print(f"{'='*70}\n")
    
    is_valid, actual_es, actual_cc = validate_cat_samples(args.cat_dir, args.cat_name, args.n_es, args.n_cc)
    
    print(f"Sample validation:")
    print(f"  Required: {args.n_es} ES, {args.n_cc} CC")
    print(f"  Available: {actual_es} ES, {actual_cc} CC")
    print(f"  Status: {'PASS' if is_valid else 'FAIL'}\n")
    
    if not is_valid:
        print("Insufficient samples. Skipping category.")
        return
    
    # Get selected event IDs
    selected_events = get_sample_event_ids(args.cat_dir, args.cat_name, args.n_es, args.n_cc, args.seed)
    cc_event_ids = selected_events['cc']
    
    print(f"Selected {len(cc_event_ids)} CC events for analysis\n")
    
    # Load ED model
    print("Loading ED model...")
    ed_model = load_ed_model(args.ed_model)
    
    # Load energy-cosine PDF
    print("Loading energy-cosine PDF...")
    pdf_interpolator, _, _ = load_energy_cosine_pdf(args.energy_cosine_pdf)
    
    # Load true neutrino directions
    print("Loading true neutrino directions...")
    try:
        true_nu_dirs = load_true_neutrino_direction(args.cat_dir, args.cat_name)
    except Exception as e:
        print(f"Warning: Could not load true neutrino directions: {e}")
        true_nu_dirs = {}
    
    # Load true electron tracks for CC events
    print("Loading true electron tracks...")
    cluster_data = load_true_electron_tracks(args.cat_dir, args.cat_name, cc_event_ids)
    
    # Log cluster statistics
    print(f"Cluster loading statistics:")
    print(f"  Input clusters (X plane): {cluster_data.get('n_input_clusters', 'N/A')}")
    print(f"    Main clusters: {cluster_data.get('n_input_main_clusters', 'N/A')}")
    print(f"    Non-main clusters: {cluster_data.get('n_input_non_main_clusters', 'N/A')}")
    print(f"  Matched across 3 planes: {cluster_data.get('n_matched_clusters', 'N/A')}")
    print(f"    Main clusters: {cluster_data.get('n_matched_main_clusters', 'N/A')}")
    print(f"    Non-main clusters: {cluster_data.get('n_matched_non_main_clusters', 'N/A')}")
    
    n_clusters = len(cluster_data['X_images'])
    print(f"\nCC clusters for analysis: {n_clusters}\n")
    
    if n_clusters == 0:
        print("No clusters found. Exiting.")
        return
    
    # Run ED inference
    print("Running ED inference on all CC tracks...")
    ed_directions = run_ed_inference(
        ed_model,
        cluster_data['X_images'],
        cluster_data['U_images'],
        cluster_data['V_images'],
        batch_size=args.batch_size
    )
    print(f"ED inference complete\n")
    
    # Process each event
    unique_events = np.unique(cluster_data['X_events'])
    print(f"Processing {len(unique_events)} unique CC events with MCMC...")
    
    results = []
    for i, event_id in enumerate(unique_events):
        if (i+1) % 100 == 0:
            print(f"  Processed {i+1}/{len(unique_events)} events")
        
        true_nu_dir = true_nu_dirs.get(event_id, None)
        result = process_event(event_id, cluster_data, ed_directions, pdf_interpolator, true_nu_dir)
        
        if result is not None:
            results.append(result)
    
    print(f"Successfully processed {len(results)} events\n")
    
    # Compute aggregate metrics
    if len(results) > 0:
        angular_errors = [r['angular_error_deg'] for r in results if r['angular_error_deg'] is not None]
        n_clusters_list = [r['n_clusters'] for r in results]
        
        metrics = {
            'scenario': 'ed_network',
            'cat_name': args.cat_name,
            'n_es_selected': args.n_es,
            'n_cc_selected': args.n_cc,
            'n_events_processed': len(results),
            'n_events_with_angular_error': len(angular_errors),
            'cluster_statistics': {
                'n_input_clusters': cluster_data.get('n_input_clusters', 0),
                'n_input_main_clusters': cluster_data.get('n_input_main_clusters', 0),
                'n_input_non_main_clusters': cluster_data.get('n_input_non_main_clusters', 0),
                'n_matched_clusters': cluster_data.get('n_matched_clusters', 0),
                'n_matched_main_clusters': cluster_data.get('n_matched_main_clusters', 0),
                'n_matched_non_main_clusters': cluster_data.get('n_matched_non_main_clusters', 0),
            },
            'angular_resolution': {
                'median_deg': float(np.median(angular_errors)) if angular_errors else None,
                'mean_deg': float(np.mean(angular_errors)) if angular_errors else None,
                'p68_deg': float(np.percentile(angular_errors, 68)) if angular_errors else None,
                'p90_deg': float(np.percentile(angular_errors, 90)) if angular_errors else None,
                'p95_deg': float(np.percentile(angular_errors, 95)) if angular_errors else None,
            },
            'n_clusters_per_event': {
                'mean': float(np.mean(n_clusters_list)),
                'median': float(np.median(n_clusters_list)),
                'min': int(np.min(n_clusters_list)),
                'max': int(np.max(n_clusters_list)),
            },
            'per_event_results': results
        }
        
        # Save results
        output_file = save_scenario_results(args.output_dir, args.cat_name, 'ed_network', metrics)
        print(f"Results saved to: {output_file}")
        
        # Print summary
        print(f"\n{'='*70}")
        print("SUMMARY")
        print(f"{'='*70}")
        print(f"Events processed: {len(results)}")
        if angular_errors:
            print(f"Angular resolution (ED network, perfect tagging):")
            print(f"  Median: {metrics['angular_resolution']['median_deg']:.2f}°")
            print(f"  Mean: {metrics['angular_resolution']['mean_deg']:.2f}°")
            print(f"  68th percentile: {metrics['angular_resolution']['p68_deg']:.2f}°")
            print(f"  90th percentile: {metrics['angular_resolution']['p90_deg']:.2f}°")
        print(f"{'='*70}\n")
    else:
        print("No events successfully processed.")


if __name__ == '__main__':
    main()
