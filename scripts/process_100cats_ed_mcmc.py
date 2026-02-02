#!/usr/bin/env python3
"""
Process 100 categories through ED model + MCMC and extract 68th percentile cosine metric.
Uses only ES main track clusters as inputs.
"""

import numpy as np
from pathlib import Path
import argparse
import uproot
import tensorflow as tf
from scipy.optimize import minimize
import matplotlib.pyplot as plt


def load_ed_model(model_path):
    """Load ED model."""
    return tf.keras.models.load_model(model_path, compile=False)


def load_energy_pdf(pdf_file):
    """Load energy-cosine PDF."""
    data = np.load(pdf_file)
    pdf_2d = data['pdf_2d']
    energy_bins = data['energy_bins']
    cosine_bin_centers = data['cosine_bin_centers']
    return pdf_2d, energy_bins, cosine_bin_centers


def process_category(cat_dir, ed_model, pdf_2d, energy_bins, cosine_bin_centers):
    """Process one category and return cosine values."""
    
    try:
        # Load neutrino direction
        tps_dir = cat_dir / 'tps'
        es_files = sorted(tps_dir.glob('es_*_tps.root'))
        
        if len(es_files) == 0:
            return None
        
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
            except:
                continue
        
        true_nu_px = np.mean(all_neutrino_px)
        true_nu_py = np.mean(all_neutrino_py)
        true_nu_pz = np.mean(all_neutrino_pz)
        
        nu_norm = np.sqrt(true_nu_px**2 + true_nu_py**2 + true_nu_pz**2)
        true_nu_dir = np.array([true_nu_px, true_nu_py, true_nu_pz]) / nu_norm
        
        # Load ES cluster data only
        cluster_data = {}
        for plane in ['U', 'V', 'X']:
            cluster_dir = cat_dir / f"{cat_dir.name}_cluster_images_tick3_ch2_min2_tot3_e2p0" / plane
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
        
        # Match cluster counts
        n_u = len(cluster_data['U']['metadata'])
        n_v = len(cluster_data['V']['metadata'])
        n_x = len(cluster_data['X']['metadata'])
        min_clusters = min(n_u, n_v, n_x)
        
        metadata = cluster_data['X']['metadata'][:min_clusters]
        
        # Filter for ES main track
        is_main_track = metadata[:, 2] == 1
        es_metadata = metadata[is_main_track]
        es_images_u = cluster_data['U']['images'][:min_clusters][is_main_track]
        es_images_v = cluster_data['V']['images'][:min_clusters][is_main_track]
        es_images_x = cluster_data['X']['images'][:min_clusters][is_main_track]
        
        if len(es_metadata) == 0:
            return None
        
        # Run ED model
        es_images_u_exp = np.expand_dims(es_images_u, axis=-1)
        es_images_v_exp = np.expand_dims(es_images_v, axis=-1)
        es_images_x_exp = np.expand_dims(es_images_x, axis=-1)
        
        predictions = ed_model.predict([es_images_u_exp, es_images_v_exp, es_images_x_exp], 
                                        batch_size=32, verbose=0)
        pred_dirs = predictions / np.linalg.norm(predictions, axis=1, keepdims=True)
        
        energies = es_metadata[:, 10]
        event_ids = es_metadata[:, 0]
        unique_events = np.unique(event_ids)
        
        all_cos_angles = []
        
        # MCMC for each event
        for event_id in unique_events:
            event_mask = event_ids == event_id
            event_pred_dirs = pred_dirs[event_mask]
            event_energies = energies[event_mask]
            
            def neg_log_likelihood(params):
                theta, phi = params
                
                reco_dir = np.array([
                    np.sin(theta) * np.cos(phi),
                    np.sin(theta) * np.sin(phi),
                    np.cos(theta)
                ])
                
                cos_angles = np.dot(event_pred_dirs, reco_dir)
                cos_angles = np.clip(cos_angles, -1, 1)
                
                log_likelihood = 0.0
                
                for energy, cos_angle in zip(event_energies, cos_angles):
                    energy_bin = np.searchsorted(energy_bins[:, 0], energy) - 1
                    energy_bin = np.clip(energy_bin, 0, len(pdf_2d) - 1)
                    
                    cos_bin = np.searchsorted(cosine_bin_centers, cos_angle)
                    cos_bin = np.clip(cos_bin, 0, len(cosine_bin_centers) - 1)
                    
                    pdf_val = pdf_2d[energy_bin, cos_bin]
                    
                    if pdf_val > 1e-10:
                        log_likelihood += np.log(pdf_val) * energy
                
                return -log_likelihood
            
            # Initial guess
            weights = event_energies / np.sum(event_energies)
            avg_dir = np.sum(event_pred_dirs * weights[:, np.newaxis], axis=0)
            avg_dir /= np.linalg.norm(avg_dir)
            
            theta0 = np.arccos(np.clip(avg_dir[2], -1, 1))
            phi0 = np.arctan2(avg_dir[1], avg_dir[0])
            
            result = minimize(
                neg_log_likelihood,
                x0=[theta0, phi0],
                method='Nelder-Mead',
                options={'maxiter': 500}
            )
            
            theta_opt, phi_opt = result.x
            reco_dir = np.array([
                np.sin(theta_opt) * np.cos(phi_opt),
                np.sin(theta_opt) * np.sin(phi_opt),
                np.cos(theta_opt)
            ])
            
            cos_angle = np.dot(reco_dir, true_nu_dir)
            all_cos_angles.append(cos_angle)
        
        return np.array(all_cos_angles)
    
    except Exception as e:
        return None


def main():
    parser = argparse.ArgumentParser(description='Process 100 categories through ED+MCMC')
    parser.add_argument('--n-cats', type=int, default=100, help='Number of categories to process')
    parser.add_argument('--ed-model',
                       default='/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v50_100k_20251115_232348/checkpoints/model_epoch_38_val_loss_0.8709.keras',
                       help='ED model path')
    parser.add_argument('--pdf-file',
                       default='/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v50_100k_20251115_232348/cosine_energy_pdf.npz',
                       help='Energy-cosine PDF file')
    parser.add_argument('--output-dir', default='results/ed_mcmc_100cats', help='Output directory')
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print(f"PROCESSING {args.n_cats} CATEGORIES WITH ED MODEL + MCMC")
    print("="*70)
    
    # Load models
    print("\nLoading ED model...")
    ed_model = load_ed_model(args.ed_model)
    
    print("Loading PDF...")
    pdf_2d, energy_bins, cosine_bin_centers = load_energy_pdf(args.pdf_file)
    
    # Find categories
    base_path = Path('/eos/project-e/ep-nu/public/sn-pointing')
    cat_dirs = sorted([d for d in base_path.glob('cat*') if d.is_dir()])[:args.n_cats]
    
    print(f"\nFound {len(cat_dirs)} categories to process")
    print("\nProcessing categories...")
    
    all_cos_angles = []
    successful_cats = []
    
    for i, cat_dir in enumerate(cat_dirs):
        cat_name = cat_dir.name
        print(f"  [{i+1}/{len(cat_dirs)}] {cat_name}...", end=' ', flush=True)
        
        cos_angles = process_category(cat_dir, ed_model, pdf_2d, energy_bins, cosine_bin_centers)
        
        if cos_angles is not None and len(cos_angles) > 0:
            all_cos_angles.extend(cos_angles)
            successful_cats.append(cat_name)
            print(f"OK ({len(cos_angles)} events)")
        else:
            print("FAILED")
    
    all_cos_angles = np.array(all_cos_angles)
    
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)
    print(f"\nSuccessful categories: {len(successful_cats)}/{len(cat_dirs)}")
    print(f"Total events: {len(all_cos_angles)}")
    
    print(f"\nCosine distribution:")
    print(f"  Median:       {np.median(all_cos_angles):7.4f}")
    print(f"  Mean:         {np.mean(all_cos_angles):7.4f}")
    print(f"  Std:          {np.std(all_cos_angles):7.4f}")
    print(f"  68th %%:       {np.percentile(all_cos_angles, 68):7.4f}  ← KEY METRIC")
    print(f"  25th %%:       {np.percentile(all_cos_angles, 25):7.4f}")
    print(f"  75th %%:       {np.percentile(all_cos_angles, 75):7.4f}")
    
    # Convert to angles
    angles = np.degrees(np.arccos(np.clip(all_cos_angles, -1, 1)))
    
    print(f"\nAngle distribution:")
    print(f"  Median:       {np.median(angles):7.2f}°")
    print(f"  Mean:         {np.mean(angles):7.2f}°")
    print(f"  Std:          {np.std(angles):7.2f}°")
    print(f"  68th %%:       {np.percentile(angles, 68):7.2f}°")
    
    forward = np.sum(all_cos_angles > 0)
    backward = np.sum(all_cos_angles < 0)
    print(f"\nPointing:")
    print(f"  Forward (cos > 0):  {forward}/{len(all_cos_angles)} ({100*forward/len(all_cos_angles):.1f}%)")
    print(f"  Backward (cos < 0): {backward}/{len(all_cos_angles)} ({100*backward/len(all_cos_angles):.1f}%)")
    
    # Create plots
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Cosine distribution plot
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    ax = axes[0]
    ax.hist(all_cos_angles, bins=60, alpha=0.7, edgecolor='black', color='steelblue')
    ax.axvline(np.median(all_cos_angles), color='red', linestyle='--', linewidth=2, 
               label=f'Median = {np.median(all_cos_angles):.4f}')
    ax.axvline(np.percentile(all_cos_angles, 68), color='orange', linestyle='--', linewidth=2,
               label=f'68th %ile = {np.percentile(all_cos_angles, 68):.4f}')
    ax.set_xlabel('cos(θ) with true neutrino direction', fontsize=13, fontweight='bold')
    ax.set_ylabel('Count', fontsize=13, fontweight='bold')
    ax.set_title(f'Cosine Distribution (ED+MCMC, {len(successful_cats)} cats, {len(all_cos_angles)} events)', 
                 fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    
    # Add statistics box
    stats_text = f'Events: {len(all_cos_angles):,}\n'
    stats_text += f'Median: {np.median(all_cos_angles):.4f}\n'
    stats_text += f'68th %ile: {np.percentile(all_cos_angles, 68):.4f}\n'
    stats_text += f'Forward: {100*forward/len(all_cos_angles):.1f}%'
    
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
            verticalalignment='top', fontsize=11, fontweight='bold',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
            family='monospace')
    
    # Angle distribution plot
    ax = axes[1]
    ax.hist(angles, bins=60, alpha=0.7, edgecolor='black', color='coral')
    ax.axvline(np.median(angles), color='red', linestyle='--', linewidth=2,
               label=f'Median = {np.median(angles):.1f}°')
    ax.axvline(np.percentile(angles, 68), color='orange', linestyle='--', linewidth=2,
               label=f'68th %ile = {np.percentile(angles, 68):.1f}°')
    ax.set_xlabel('Angle (degrees) with true neutrino direction', fontsize=13, fontweight='bold')
    ax.set_ylabel('Count', fontsize=13, fontweight='bold')
    ax.set_title(f'Angle Distribution (ED+MCMC, {len(successful_cats)} cats, {len(all_cos_angles)} events)',
                 fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    output_file = output_dir / f'ed_mcmc_{len(successful_cats)}cats_cosine_distribution.png'
    plt.savefig(output_file, dpi=200, bbox_inches='tight')
    print(f"\nSaved plot: {output_file}")
    plt.close()
    
    # Save results
    results_file = output_dir / f'ed_mcmc_{len(successful_cats)}cats_results.npz'
    np.savez(results_file, 
             cos_angles=all_cos_angles,
             angles=angles,
             successful_cats=successful_cats)
    print(f"Saved results: {results_file}")
    
    print("\n" + "="*70)
    print("COMPARISON TO BASELINES")
    print("="*70)
    print(f"MCMC with TRUE e- dirs:   cos(θ) 68% = 0.9980  ← Best possible")
    print(f"MCMC with ED model:       cos(θ) 68% = {np.percentile(all_cos_angles, 68):.4f}  ← Current")
    print(f"Gap:                      Δcos(θ) = {0.9980 - np.percentile(all_cos_angles, 68):.4f}")
    print("\n" + "="*70 + "\n")


if __name__ == '__main__':
    main()
