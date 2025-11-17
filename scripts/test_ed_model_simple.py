#!/usr/bin/env python3
"""
Test ED model predictions and compute 68th percentile cosine metric.
"""

import numpy as np
from pathlib import Path
import argparse
import uproot
import tensorflow as tf
from scipy.optimize import minimize


def load_ed_model(model_path):
    """Load ED model."""
    return tf.keras.models.load_model(model_path, compile=False)


def load_es_data_with_clusters(cat_dir):
    """Load ES event data and cluster information."""
    
    tps_dir = cat_dir / 'tps'
    es_files = sorted(tps_dir.glob('es_*_tps.root'))
    
    if len(es_files) == 0:
        return None
    
    # Load cluster data
    cluster_data = {}
    for plane in ['U', 'V', 'X']:
        cluster_dir = cat_dir / f"{cat_dir.name}_cluster_images_tick3_ch2_min2_tot3_e2p0" / plane
        # Only load ES files
        cluster_files = sorted(cluster_dir.glob('es_*_matched_plane*.npz'))
        
        if len(cluster_files) == 0:
            return None
        
        all_images = []
        all_metadata = []
        
        for cf in cluster_files:
            data = np.load(cf)
            all_images.append(data['images'])
            all_metadata.append(data['metadata'])
        
        cluster_data[plane] = {
            'images': np.vstack(all_images),
            'metadata': np.vstack(all_metadata)
        }
    
    # Match cluster counts across planes
    n_u = len(cluster_data['U']['metadata'])
    n_v = len(cluster_data['V']['metadata'])
    n_x = len(cluster_data['X']['metadata'])
    min_clusters = min(n_u, n_v, n_x)
    
    print(f"Found {len(es_files)} ES files and {min_clusters} matched clusters")
    
    # Load TPS data
    all_neutrino_px = []
    all_neutrino_py = []
    all_neutrino_pz = []
    
    for es_file in es_files:
        try:
            with uproot.open(es_file) as f:
                tree = f['tps']
                nu_px = tree['neutrino_px'].array(library='np')
                nu_py = tree['neutrino_py'].array(library='np')
                nu_pz = tree['neutrino_pz'].array(library='np')
                
                all_neutrino_px.extend(nu_px)
                all_neutrino_py.extend(nu_py)
                all_neutrino_pz.extend(nu_pz)
        except Exception as e:
            print(f"Error reading {es_file}: {e}")
            continue
    
    # Get average neutrino direction (should be constant per category)
    true_nu_px = np.mean(all_neutrino_px)
    true_nu_py = np.mean(all_neutrino_py)
    true_nu_pz = np.mean(all_neutrino_pz)
    
    nu_norm = np.sqrt(true_nu_px**2 + true_nu_py**2 + true_nu_pz**2)
    true_nu_dir = np.array([true_nu_px, true_nu_py, true_nu_pz]) / nu_norm
    
    return {
        'metadata': cluster_data['X']['metadata'][:min_clusters],
        'images_u': cluster_data['U']['images'][:min_clusters],
        'images_v': cluster_data['V']['images'][:min_clusters],
        'images_x': cluster_data['X']['images'][:min_clusters],
        'true_nu_dir': true_nu_dir,
        'n_es_files': len(es_files)
    }


def load_energy_pdf(pdf_file):
    """Load energy-cosine PDF."""
    
    data = np.load(pdf_file)
    pdf_2d = data['pdf_2d']
    energy_bins = data['energy_bins']
    cosine_bin_centers = data['cosine_bin_centers']
    
    return pdf_2d, energy_bins, cosine_bin_centers


def compute_mcmc_with_ed_predictions(metadata, images_u, images_v, images_x, true_nu_dir, ed_model, pdf_2d, energy_bins, cosine_bin_centers):
    """
    Use MCMC to find neutrino direction using ED MODEL predictions.
    
    Metadata structure:
    - Position 0: event_id
    - Position 2: is_main_track
    - Position 3: is_es_interaction
    - Position 10: cluster_energy_mev
    """
    
    # Filter for ES main track clusters
    is_main_track = metadata[:, 2] == 1
    is_es = metadata[:, 3] == 1
    valid_mask = is_main_track & is_es
    
    es_metadata = metadata[valid_mask]
    es_images_u = images_u[valid_mask]
    es_images_v = images_v[valid_mask]
    es_images_x = images_x[valid_mask]
    
    if len(es_metadata) == 0:
        return None
    
    print(f"  Found {len(es_metadata)} ES main track clusters")
    
    # Run ED model predictions
    es_images_u_exp = np.expand_dims(es_images_u, axis=-1)
    es_images_v_exp = np.expand_dims(es_images_v, axis=-1)
    es_images_x_exp = np.expand_dims(es_images_x, axis=-1)
    
    predictions = ed_model.predict([es_images_u_exp, es_images_v_exp, es_images_x_exp], 
                                    batch_size=32, verbose=0)
    pred_dirs = predictions / np.linalg.norm(predictions, axis=1, keepdims=True)
    
    # Get energies
    energies = es_metadata[:, 10]
    
    # Group by event_id
    event_ids = es_metadata[:, 0]
    unique_events = np.unique(event_ids)
    
    print(f"  Processing {len(unique_events)} events")
    
    all_cos_angles = []
    all_angles = []
    
    for event_id in unique_events:
        event_mask = event_ids == event_id
        event_pred_dirs = pred_dirs[event_mask]
        event_energies = energies[event_mask]
        
        # Define negative log-likelihood function
        def neg_log_likelihood(params):
            theta, phi = params
            
            # Convert to direction
            reco_dir = np.array([
                np.sin(theta) * np.cos(phi),
                np.sin(theta) * np.sin(phi),
                np.cos(theta)
            ])
            
            # Compute angles to predicted electron directions
            cos_angles = np.dot(event_pred_dirs, reco_dir)
            cos_angles = np.clip(cos_angles, -1, 1)
            
            # Get PDF values
            log_likelihood = 0.0
            
            for i, (energy, cos_angle) in enumerate(zip(event_energies, cos_angles)):
                # Find energy bin
                energy_bin = np.searchsorted(energy_bins[:, 0], energy) - 1
                energy_bin = np.clip(energy_bin, 0, len(pdf_2d) - 1)
                
                # Find cosine bin
                cos_bin = np.searchsorted(cosine_bin_centers, cos_angle)
                cos_bin = np.clip(cos_bin, 0, len(cosine_bin_centers) - 1)
                
                # Get PDF value
                pdf_val = pdf_2d[energy_bin, cos_bin]
                
                if pdf_val > 1e-10:
                    log_likelihood += np.log(pdf_val) * energy
            
            return -log_likelihood
        
        # Initial guess: average direction (weighted by energy)
        weights = event_energies / np.sum(event_energies)
        avg_dir = np.sum(event_pred_dirs * weights[:, np.newaxis], axis=0)
        avg_dir /= np.linalg.norm(avg_dir)
        
        theta0 = np.arccos(np.clip(avg_dir[2], -1, 1))
        phi0 = np.arctan2(avg_dir[1], avg_dir[0])
        
        # Run optimization
        result = minimize(
            neg_log_likelihood,
            x0=[theta0, phi0],
            method='Nelder-Mead',
            options={'maxiter': 500}
        )
        
        # Extract result
        theta_opt, phi_opt = result.x
        reco_dir = np.array([
            np.sin(theta_opt) * np.cos(phi_opt),
            np.sin(theta_opt) * np.sin(phi_opt),
            np.cos(theta_opt)
        ])
        
        # Compute angle to true neutrino
        cos_angle = np.dot(reco_dir, true_nu_dir)
        angle = np.degrees(np.arccos(np.clip(cos_angle, -1, 1)))
        
        all_cos_angles.append(cos_angle)
        all_angles.append(angle)
    
    return np.array(all_angles), np.array(all_cos_angles)


def main():
    parser = argparse.ArgumentParser(description='Test ED model with MCMC')
    parser.add_argument('--cat-name', default='cat000035', help='Category name')
    parser.add_argument('--ed-model',
                       default='/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v50_100k_20251115_232348/checkpoints/model_epoch_38_val_loss_0.8709.keras',
                       help='ED model path')
    parser.add_argument('--pdf-file',
                       default='/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v50_100k_20251115_232348/cosine_energy_pdf.npz',
                       help='Energy-cosine PDF file')
    args = parser.parse_args()
    
    cat_dir = Path('/eos/project-e/ep-nu/public/sn-pointing') / args.cat_name
    
    print(f"\nAnalyzing category: {args.cat_name}")
    print(f"Path: {cat_dir}")
    print("="*70)
    
    # Load ED model
    print(f"\nLoading ED model...")
    ed_model = load_ed_model(args.ed_model)
    
    # Load data
    print("\nLoading data...")
    data = load_es_data_with_clusters(cat_dir)
    
    if data is None:
        print("Failed to load data")
        return
    
    print(f"True neutrino direction: {data['true_nu_dir']}")
    
    # Load PDF
    print(f"\nLoading energy-cosine PDF...")
    pdf_2d, energy_bins, cosine_bin_centers = load_energy_pdf(args.pdf_file)
    print(f"PDF shape: {pdf_2d.shape}")
    
    # Run MCMC with ED predictions
    print("\nRunning MCMC optimization with ED MODEL predictions...")
    angles, cos_angles = compute_mcmc_with_ed_predictions(
        data['metadata'], data['images_u'], data['images_v'], data['images_x'],
        data['true_nu_dir'], ed_model, pdf_2d, energy_bins, cosine_bin_centers
    )
    
    if angles is None or len(angles) == 0:
        print("No valid events")
        return
    
    # Print results
    print("\n" + "="*70)
    print("RESULTS: MCMC WITH ED MODEL PREDICTIONS")
    print("="*70)
    print(f"\nEvents analyzed: {len(angles)}")
    print(f"\nCosine to true neutrino direction:")
    print(f"  Median:      {np.median(cos_angles):7.4f}")
    print(f"  Mean:        {np.mean(cos_angles):7.4f}")
    print(f"  68th %%:      {np.percentile(cos_angles, 68):7.4f}  ← KEY METRIC")
    print(f"\nAngle to true neutrino direction:")
    print(f"  Median:      {np.median(angles):7.2f}°")
    print(f"  Mean:        {np.mean(angles):7.2f}°")
    print(f"  Std:         {np.std(angles):7.2f}°")
    print(f"  68th %%:      {np.percentile(angles, 68):7.2f}°")
    print(f"  Min:         {np.min(angles):7.2f}°")
    print(f"  Max:         {np.max(angles):7.2f}°")
    
    # Compare with physics limit
    print("\n" + "="*70)
    print("COMPARISON")
    print("="*70)
    print(f"MCMC with TRUE e- dirs:      cos(θ) 68% = 0.9980")
    print(f"MCMC with ED model:          cos(θ) 68% = {np.percentile(cos_angles, 68):.4f}")
    print(f"Gap:                         Δcos(θ) = {0.9980 - np.percentile(cos_angles, 68):.4f}")
    
    # Distribution
    forward = np.sum(cos_angles > 0)
    backward = np.sum(cos_angles < 0)
    print(f"\nPointing distribution:")
    print(f"  Forward (cos > 0):  {forward}/{len(angles)} ({100*forward/len(angles):.1f}%)")
    print(f"  Backward (cos < 0): {backward}/{len(angles)} ({100*backward/len(angles):.1f}%)")
    
    print("\n" + "="*70 + "\n")


if __name__ == '__main__':
    main()
