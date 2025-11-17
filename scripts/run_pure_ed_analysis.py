#!/usr/bin/env python3
"""
Pure ED analysis: Use only ES main track clusters, no MCMC optimization.
Just average the ED-predicted directions weighted by energy.
"""

import numpy as np
import tensorflow as tf
import uproot
import json
from pathlib import Path
from scipy.optimize import minimize
from scipy.interpolate import RegularGridInterpolator
import argparse


def load_ed_model(model_path):
    """Load ED model with TF2/Keras3 compatibility."""
    try:
        model = tf.keras.models.load_model(model_path, compile=False)
    except (ValueError, IOError):
        # Keras 3 or SavedModel format
        model_layer = tf.keras.layers.TFSMLayer(model_path, call_endpoint='serving_default')
        
        input_x = tf.keras.Input(shape=(128, 32, 1))
        input_u = tf.keras.Input(shape=(128, 32, 1))
        input_v = tf.keras.Input(shape=(128, 32, 1))
        
        outputs = model_layer(x=input_x, u=input_u, v=input_v)
        
        if isinstance(outputs, dict):
            output_keys = list(outputs.keys())
            output_key = [k for k in output_keys if 'output' in k.lower()] or output_keys
            direction = outputs[output_key[0]]
        else:
            direction = outputs
        
        model = tf.keras.Model(inputs=[input_x, input_u, input_v], outputs=direction)
    
    return model


def load_energy_cosine_pdf(pdf_path):
    """Load energy-cosine PDF."""
    data = np.load(pdf_path)
    pdf_2d = data['pdf_2d']
    energy_bins = data['energy_bins']
    cosine_bin_centers = data['cosine_bin_centers']
    
    energy_centers = energy_bins.mean(axis=1)
    
    interpolator = RegularGridInterpolator(
        (energy_centers, cosine_bin_centers),
        pdf_2d,
        bounds_error=False,
        fill_value=1e-10
    )
    
    return interpolator


def load_true_neutrino_direction(cat_dir, cat_name):
    """Load true neutrino direction from tps ROOT file."""
    tps_dir = Path(cat_dir) / 'tps'
    root_files = sorted(tps_dir.glob('*.root'))
    
    if not root_files:
        return None
    
    with uproot.open(root_files[0]) as f:
        tree = f['tps']
        nu_px = tree['neutrino_px'].array(library='np')
        nu_py = tree['neutrino_py'].array(library='np')
        nu_pz = tree['neutrino_pz'].array(library='np')
    
    true_px = np.mean(nu_px)
    true_py = np.mean(nu_py)
    true_pz = np.mean(nu_pz)
    
    true_norm = np.sqrt(true_px**2 + true_py**2 + true_pz**2)
    true_direction = np.array([true_px, true_py, true_pz]) / true_norm
    
    return true_direction


def load_cluster_data(cat_dir, cat_name, plane):
    """Load cluster images and metadata."""
    cluster_dir = Path(cat_dir) / f"{cat_name}_cluster_images_tick3_ch2_min2_tot3_e2p0" / plane
    
    if not cluster_dir.exists():
        return None, None
    
    npz_files = sorted(cluster_dir.glob("*.npz"))
    
    all_images = []
    all_metadata = []
    
    for npz_file in npz_files:
        data = np.load(npz_file)
        all_images.append(data['images'])
        all_metadata.append(data['metadata'])
    
    images = np.concatenate(all_images, axis=0)
    metadata = np.concatenate(all_metadata, axis=0)
    
    return images, metadata


def compute_pure_ed_direction(cluster_images_x, cluster_images_u, cluster_images_v, 
                               cluster_energies, ed_model):
    """
    Pure ED: Just predict directions and take energy-weighted average.
    No MCMC optimization.
    """
    n_clusters = len(cluster_images_x)
    
    # Predict cluster directions
    cluster_directions = []
    for i in range(n_clusters):
        img_x = np.expand_dims(cluster_images_x[i], axis=0)
        img_u = np.expand_dims(cluster_images_u[i], axis=0)
        img_v = np.expand_dims(cluster_images_v[i], axis=0)
        
        direction = ed_model.predict([img_x, img_u, img_v], verbose=0)[0]
        norm = np.linalg.norm(direction)
        if norm > 0:
            direction = direction / norm
        
        cluster_directions.append(direction)
    
    cluster_directions = np.array(cluster_directions)
    
    # Energy-weighted average
    weights = cluster_energies / np.sum(cluster_energies)
    weighted_direction = np.sum(cluster_directions * weights[:, np.newaxis], axis=0)
    
    # Normalize
    final_direction = weighted_direction / np.linalg.norm(weighted_direction)
    
    return final_direction, cluster_directions


def compute_mcmc_direction(cluster_directions, cluster_energies, pdf_interpolator):
    """MCMC optimization for comparison."""
    def neg_log_likelihood(candidate_dir):
        candidate_norm = np.linalg.norm(candidate_dir)
        if candidate_norm < 1e-10:
            return 1e10
        candidate_dir_unit = candidate_dir / candidate_norm
        
        cosines = np.dot(cluster_directions, candidate_dir_unit)
        cosines = np.clip(cosines, -1.0, 1.0)
        
        points = np.column_stack([cluster_energies, cosines])
        pdf_values = pdf_interpolator(points)
        
        log_likelihood = np.sum(np.log(np.maximum(pdf_values, 1e-10)))
        
        return -log_likelihood
    
    initial_dir = np.mean(cluster_directions, axis=0)
    initial_norm = np.linalg.norm(initial_dir)
    if initial_norm > 0:
        initial_dir = initial_dir / initial_norm
    else:
        initial_dir = np.array([0, 0, 1])
    
    result = minimize(neg_log_likelihood, initial_dir, method='BFGS', options={'maxiter': 1000})
    
    final_direction = result.x / np.linalg.norm(result.x)
    
    return final_direction


def main():
    parser = argparse.ArgumentParser(description='Pure ED analysis on ES main track clusters')
    parser.add_argument('--cat-dir', required=True)
    parser.add_argument('--cat-name', required=True)
    parser.add_argument('--ed-model', required=True)
    parser.add_argument('--energy-cosine-pdf', required=True)
    parser.add_argument('--output-dir', default='results/pure_ed_cats')
    parser.add_argument('--with-mcmc', action='store_true', help='Also run MCMC for comparison')
    
    args = parser.parse_args()
    
    print(f"\n{'='*60}")
    print(f"PURE ED ANALYSIS (ES Main Track Only)")
    print(f"Category: {args.cat_name}")
    print(f"{'='*60}\n")
    
    # Load models
    print("Loading ED model...")
    ed_model = load_ed_model(args.ed_model)
    
    if args.with_mcmc:
        print("Loading energy-cosine PDF...")
        pdf_interpolator = load_energy_cosine_pdf(args.energy_cosine_pdf)
    
    print("Loading true neutrino direction...")
    true_neutrino_direction = load_true_neutrino_direction(args.cat_dir, args.cat_name)
    print(f"  True: {true_neutrino_direction}")
    
    # Load cluster data
    print(f"\nLoading cluster data...")
    images_x, metadata_x = load_cluster_data(args.cat_dir, args.cat_name, 'X')
    images_u, metadata_u = load_cluster_data(args.cat_dir, args.cat_name, 'U')
    images_v, metadata_v = load_cluster_data(args.cat_dir, args.cat_name, 'V')
    
    print(f"  Total clusters: {images_x.shape[0]}")
    
    # Metadata positions:
    # 0: event_id, 2: is_main_track, 3: is_es_interaction, 10: cluster_energy_mev
    
    # Filter for ES main track clusters
    is_main = metadata_x[:, 2] > 0.5
    is_es = metadata_x[:, 3] > 0.5
    es_main_mask = is_main & is_es
    
    print(f"  ES main track clusters: {np.sum(es_main_mask)}")
    
    # Get unique events
    event_ids = np.unique(metadata_x[es_main_mask, 0]).astype(int)
    print(f"  Events with ES main tracks: {len(event_ids)}")
    
    # Process each event
    results = []
    
    for i, event_id in enumerate(event_ids):
        if (i + 1) % 10 == 0 or (i + 1) == len(event_ids):
            print(f"\rProcessing event {i+1}/{len(event_ids)}...", end='', flush=True)
        
        # Get ES main track clusters for this event in X plane
        event_mask_x = (metadata_x[:, 0] == event_id) & es_main_mask
        
        # Get matching clusters in U and V by event_id (they should also be ES main track)
        event_mask_u = (metadata_u[:, 0] == event_id) & (metadata_u[:, 2] > 0.5) & (metadata_u[:, 3] > 0.5)
        event_mask_v = (metadata_v[:, 0] == event_id) & (metadata_v[:, 2] > 0.5) & (metadata_v[:, 3] > 0.5)
        
        event_images_x = images_x[event_mask_x]
        event_images_u = images_u[event_mask_u]
        event_images_v = images_v[event_mask_v]
        
        event_energies = np.abs(metadata_x[event_mask_x, 10])
        
        n_clusters_x = len(event_images_x)
        n_clusters_u = len(event_images_u)
        n_clusters_v = len(event_images_v)
        
        # Use minimum count to ensure all planes have data
        n_clusters = min(n_clusters_x, n_clusters_u, n_clusters_v)
        
        if n_clusters == 0:
            continue
        
        # Truncate to match sizes
        event_images_x = event_images_x[:n_clusters]
        event_images_u = event_images_u[:n_clusters]
        event_images_v = event_images_v[:n_clusters]
        event_energies = event_energies[:n_clusters]
        
        # Pure ED: energy-weighted average
        ed_direction, cluster_dirs = compute_pure_ed_direction(
            event_images_x, event_images_u, event_images_v,
            event_energies, ed_model
        )
        
        # Compare to true
        cos_ed = np.dot(ed_direction, true_neutrino_direction)
        angle_ed = np.degrees(np.arccos(np.clip(cos_ed, -1, 1)))
        
        result = {
            'event_id': int(event_id),
            'n_clusters': n_clusters,
            'ed_direction': ed_direction.tolist(),
            'ed_cosine': float(cos_ed),
            'ed_angle_deg': float(angle_ed),
        }
        
        # Optional: MCMC for comparison
        if args.with_mcmc:
            mcmc_direction = compute_mcmc_direction(cluster_dirs, event_energies, pdf_interpolator)
            cos_mcmc = np.dot(mcmc_direction, true_neutrino_direction)
            angle_mcmc = np.degrees(np.arccos(np.clip(cos_mcmc, -1, 1)))
            
            result.update({
                'mcmc_direction': mcmc_direction.tolist(),
                'mcmc_cosine': float(cos_mcmc),
                'mcmc_angle_deg': float(angle_mcmc),
            })
        
        result['true_direction'] = true_neutrino_direction.tolist()
        results.append(result)
    
    print("\n")
    
    # Summary statistics
    ed_cosines = [r['ed_cosine'] for r in results]
    ed_angles = [r['ed_angle_deg'] for r in results]
    
    summary = {
        'cat_name': args.cat_name,
        'n_events': len(results),
        'ed_median_cosine': float(np.median(ed_cosines)),
        'ed_median_angle_deg': float(np.median(ed_angles)),
        'ed_mean_cosine': float(np.mean(ed_cosines)),
        'ed_p68_angle_deg': float(np.percentile(ed_angles, 68)),
    }
    
    if args.with_mcmc:
        mcmc_cosines = [r['mcmc_cosine'] for r in results]
        mcmc_angles = [r['mcmc_angle_deg'] for r in results]
        summary.update({
            'mcmc_median_cosine': float(np.median(mcmc_cosines)),
            'mcmc_median_angle_deg': float(np.median(mcmc_angles)),
            'mcmc_mean_cosine': float(np.mean(mcmc_cosines)),
            'mcmc_p68_angle_deg': float(np.percentile(mcmc_angles, 68)),
        })
    
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
    
    print(f"{'='*60}")
    print(f"RESULTS:")
    print(f"  Events: {len(results)}")
    print(f"\nPure ED (energy-weighted average):")
    print(f"  Median cos: {summary['ed_median_cosine']:.3f}")
    print(f"  Median angle: {summary['ed_median_angle_deg']:.1f}°")
    print(f"  68th percentile: {summary['ed_p68_angle_deg']:.1f}°")
    
    if args.with_mcmc:
        print(f"\nMCMC (with energy-cosine PDF):")
        print(f"  Median cos: {summary['mcmc_median_cosine']:.3f}")
        print(f"  Median angle: {summary['mcmc_median_angle_deg']:.1f}°")
        print(f"  68th percentile: {summary['mcmc_p68_angle_deg']:.1f}°")
    
    print(f"\n✓ Saved to: {output_file}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
