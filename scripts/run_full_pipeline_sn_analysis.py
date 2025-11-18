#!/usr/bin/env python3
"""
Scenario 3: FULL PIPELINE - SN Pointing Performance with realistic reconstruction
Runs complete MT → CT → ED chain. Only ES-tagged clusters fed to ED.
Realistic performance with channel identification and electron detection.

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


def load_mt_model(model_path):
    """Load MT model."""
    model = tf.keras.models.load_model(model_path, compile=False)
    return model


def load_ct_model(model_path):
    """Load CT model."""
    model = tf.keras.models.load_model(model_path, compile=False)
    return model


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


def load_all_clusters(cat_dir, cat_name, event_ids):
    """Load ALL clusters (ES+CC) for specified event IDs, matched across all three planes."""
    # Use centralized loading function that matches clusters across planes
    from python.sn_sample_utils import load_filtered_cluster_images
    
    return load_filtered_cluster_images(cat_dir, cat_name, event_ids)


def run_mt_inference(mt_model, X_images, U_images, V_images, mt_threshold=0.5, batch_size=512):
    """
    Run MT inference on all clusters.
    Returns: mask of clusters predicted as main tracks (score >= threshold)
    """
    n_clusters = len(X_images)
    
    # MT model expects only X cluster images
    predictions = mt_model.predict(X_images, batch_size=batch_size, verbose=0)
    
    # predictions shape: (n_clusters, 1) - probability of being main track
    mt_scores = predictions[:, 0]
    mt_mask = mt_scores >= mt_threshold
    
    return mt_mask, mt_scores


def run_ct_inference(ct_model, X_images_mt, U_images_mt, V_images_mt, ct_threshold=0.5, batch_size=512):
    """
    Run CT inference on MT-identified clusters.
    Returns: mask of clusters predicted as ES (channel tag = electron)
    """
    if len(X_images_mt) == 0:
        return np.array([]), np.array([])
    
    # CT model expects only X volume images
    predictions = ct_model.predict(X_images_mt, batch_size=batch_size, verbose=0)
    
    # predictions shape: (n_clusters, 1) - probability of being ES
    ct_scores = predictions[:, 0]
    es_mask = ct_scores >= ct_threshold
    
    return es_mask, ct_scores


def run_ed_inference(ed_model, X_images_es, U_images_es, V_images_es, batch_size=512):
    """
    Run ED inference on ES-tagged clusters.
    Returns: predicted directions (Cartesian unit vectors)
    """
    if len(X_images_es) == 0:
        return np.array([])
    
    # ED model expects 3 inputs: [X, U, V] images
    predictions = ed_model.predict([X_images_es, U_images_es, V_images_es], batch_size=batch_size, verbose=0)
    
    # predictions shape: (n_clusters, 2) - [theta, phi]
    theta = predictions[:, 0]
    phi = predictions[:, 1]
    
    # Convert to Cartesian unit vectors
    n_es = len(theta)
    directions = np.zeros((n_es, 3))
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


def process_event(event_id, es_events, es_energies, es_directions, pdf_interpolator, true_nu_direction):
    """Process one event: use ES-tagged ED directions + MCMC."""
    event_mask = es_events == event_id
    
    if not np.any(event_mask):
        return None
    
    cluster_energies = es_energies[event_mask]
    cluster_directions = es_directions[event_mask]
    
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
        'n_es_clusters': int(len(cluster_energies)),
        'best_direction': best_direction.tolist(),
        'best_log_like': float(best_log_like),
        'angular_error_deg': float(angular_error_deg) if angular_error_deg is not None else None,
        'true_nu_direction': true_nu_direction.tolist() if true_nu_direction is not None else None
    }


def main():
    parser = argparse.ArgumentParser(description='Full pipeline SN analysis (MT→CT→ED)')
    parser.add_argument('--cat-dir', required=True, help='Category directory')
    parser.add_argument('--cat-name', required=True, help='Category name (e.g., cat000001)')
    parser.add_argument('--mt-model', required=True, help='Path to MT model')
    parser.add_argument('--ct-model', required=True, help='Path to CT model')
    parser.add_argument('--ed-model', required=True, help='Path to ED model')
    parser.add_argument('--energy-cosine-pdf', required=True, help='Path to energy-cosine PDF .npz')
    parser.add_argument('--output-dir', required=True, help='Output directory')
    parser.add_argument('--n-es', type=int, default=325, help='Number of ES samples (default: 325)')
    parser.add_argument('--n-cc', type=int, default=3300, help='Number of CC samples (default: 3300)')
    parser.add_argument('--mt-threshold', type=float, default=0.5, help='MT threshold')
    parser.add_argument('--ct-threshold', type=float, default=0.5, help='CT threshold')
    parser.add_argument('--batch-size', type=int, default=512, help='Inference batch size')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    
    args = parser.parse_args()
    
    # Validate samples
    print(f"\n{'='*70}")
    print(f"SCENARIO 3: FULL PIPELINE (MT→CT→ED) - {args.cat_name}")
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
    all_event_ids = selected_events['es'] | selected_events['cc']
    
    print(f"Selected {args.n_es} ES + {args.n_cc} CC = {len(all_event_ids)} total events\n")
    
    # Load models
    print("Loading MT model...")
    mt_model = load_mt_model(args.mt_model)
    print("Loading CT model...")
    ct_model = load_ct_model(args.ct_model)
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
    
    # Load all clusters
    print("Loading all clusters...")
    cluster_data = load_all_clusters(args.cat_dir, args.cat_name, all_event_ids)
    
    # Log cluster statistics
    print(f"Cluster loading statistics:")
    print(f"  Input clusters (X plane): {cluster_data.get('n_input_clusters', 'N/A')}")
    print(f"    Main clusters: {cluster_data.get('n_input_main_clusters', 'N/A')}")
    print(f"    Non-main clusters: {cluster_data.get('n_input_non_main_clusters', 'N/A')}")
    print(f"  Matched across 3 planes: {cluster_data.get('n_matched_clusters', 'N/A')}")
    print(f"    Main clusters: {cluster_data.get('n_matched_main_clusters', 'N/A')}")
    print(f"    Non-main clusters: {cluster_data.get('n_matched_non_main_clusters', 'N/A')}")
    
    n_clusters = len(cluster_data['X_images'])
    print(f"\nTotal clusters for MT inference: {n_clusters}\n")
    
    if n_clusters == 0:
        print("No clusters found. Exiting.")
        return
    
    # Step 1: MT inference
    print("Step 1: Running MT inference...")
    mt_mask, mt_scores = run_mt_inference(
        mt_model,
        cluster_data['X_images'],
        cluster_data['U_images'],
        cluster_data['V_images'],
        mt_threshold=args.mt_threshold,
        batch_size=args.batch_size
    )
    n_mt = np.sum(mt_mask)
    print(f"  Identified {n_mt}/{n_clusters} clusters as main tracks ({100*n_mt/n_clusters:.1f}%)\n")
    
    if n_mt == 0:
        print("No main tracks identified. Exiting.")
        return
    
    # Step 2: CT inference on MT-identified clusters
    print("Step 2: Running CT inference on MT clusters...")
    es_mask_relative, ct_scores = run_ct_inference(
        ct_model,
        cluster_data['X_images'][mt_mask],
        cluster_data['U_images'][mt_mask],
        cluster_data['V_images'][mt_mask],
        ct_threshold=args.ct_threshold,
        batch_size=args.batch_size
    )
    
    # Map back to original cluster indices
    mt_indices = np.where(mt_mask)[0]
    es_indices = mt_indices[es_mask_relative]
    es_mask_absolute = np.zeros(n_clusters, dtype=bool)
    es_mask_absolute[es_indices] = True
    
    n_es = np.sum(es_mask_absolute)
    print(f"  Identified {n_es}/{n_mt} MT clusters as ES ({100*n_es/n_mt:.1f}% of MT, {100*n_es/n_clusters:.1f}% of all)\n")
    
    if n_es == 0:
        print("No ES clusters identified. Exiting.")
        return
    
    # Step 3: ED inference on ES-tagged clusters
    print("Step 3: Running ED inference on ES clusters...")
    ed_directions = run_ed_inference(
        ed_model,
        cluster_data['X_images'][es_mask_absolute],
        cluster_data['U_images'][es_mask_absolute],
        cluster_data['V_images'][es_mask_absolute],
        batch_size=args.batch_size
    )
    print(f"  ED inference complete for {n_es} clusters\n")
    
    # Prepare data for MCMC
    es_events = cluster_data['X_events'][es_mask_absolute]
    es_metadata = cluster_data['X_metadata'][es_mask_absolute]
    es_energies = es_metadata[:, 10]  # Column 10: particle energy
    
    # Process each event
    unique_events = np.unique(es_events)
    print(f"Step 4: Processing {len(unique_events)} events with ES clusters using MCMC...")
    
    results = []
    for i, event_id in enumerate(unique_events):
        if (i+1) % 100 == 0:
            print(f"  Processed {i+1}/{len(unique_events)} events")
        
        true_nu_dir = true_nu_dirs.get(event_id, None)
        result = process_event(event_id, es_events, es_energies, ed_directions, pdf_interpolator, true_nu_dir)
        
        if result is not None:
            results.append(result)
    
    print(f"Successfully processed {len(results)} events\n")
    
    # Compute aggregate metrics
    if len(results) > 0:
        angular_errors = [r['angular_error_deg'] for r in results if r['angular_error_deg'] is not None]
        n_es_clusters_list = [r['n_es_clusters'] for r in results]
        
        metrics = {
            'scenario': 'full_pipeline',
            'cat_name': args.cat_name,
            'n_es_selected': args.n_es,
            'n_cc_selected': args.n_cc,
            'cluster_statistics': {
                'n_input_clusters': cluster_data.get('n_input_clusters', 0),
                'n_input_main_clusters': cluster_data.get('n_input_main_clusters', 0),
                'n_input_non_main_clusters': cluster_data.get('n_input_non_main_clusters', 0),
                'n_matched_clusters': cluster_data.get('n_matched_clusters', 0),
                'n_matched_main_clusters': cluster_data.get('n_matched_main_clusters', 0),
                'n_matched_non_main_clusters': cluster_data.get('n_matched_non_main_clusters', 0),
            },
            'n_total_clusters': int(n_clusters),
            'n_mt_clusters': int(n_mt),
            'n_es_clusters': int(n_es),
            'mt_efficiency': float(n_mt / n_clusters),
            'ct_efficiency': float(n_es / n_mt) if n_mt > 0 else 0.0,
            'overall_efficiency': float(n_es / n_clusters),
            'n_events_processed': len(results),
            'n_events_with_angular_error': len(angular_errors),
            'angular_resolution': {
                'median_deg': float(np.median(angular_errors)) if angular_errors else None,
                'mean_deg': float(np.mean(angular_errors)) if angular_errors else None,
                'p68_deg': float(np.percentile(angular_errors, 68)) if angular_errors else None,
                'p90_deg': float(np.percentile(angular_errors, 90)) if angular_errors else None,
                'p95_deg': float(np.percentile(angular_errors, 95)) if angular_errors else None,
            },
            'n_es_clusters_per_event': {
                'mean': float(np.mean(n_es_clusters_list)),
                'median': float(np.median(n_es_clusters_list)),
                'min': int(np.min(n_es_clusters_list)),
                'max': int(np.max(n_es_clusters_list)),
            },
            'per_event_results': results
        }
        
        # Save results
        output_file = save_scenario_results(args.output_dir, args.cat_name, 'full_pipeline', metrics)
        print(f"Results saved to: {output_file}")
        
        # Print summary
        print(f"\n{'='*70}")
        print("SUMMARY")
        print(f"{'='*70}")
        print(f"Pipeline efficiency:")
        print(f"  MT: {metrics['mt_efficiency']:.1%} ({n_mt}/{n_clusters} clusters)")
        print(f"  CT: {metrics['ct_efficiency']:.1%} ({n_es}/{n_mt} MT clusters)")
        print(f"  Overall: {metrics['overall_efficiency']:.1%} ({n_es}/{n_clusters} clusters)")
        print(f"\nEvents processed: {len(results)}")
        if angular_errors:
            print(f"Angular resolution (full pipeline):")
            print(f"  Median: {metrics['angular_resolution']['median_deg']:.2f}°")
            print(f"  Mean: {metrics['angular_resolution']['mean_deg']:.2f}°")
            print(f"  68th percentile: {metrics['angular_resolution']['p68_deg']:.2f}°")
            print(f"  90th percentile: {metrics['angular_resolution']['p90_deg']:.2f}°")
        print(f"{'='*70}\n")
    else:
        print("No events successfully processed.")


if __name__ == '__main__':
    main()
