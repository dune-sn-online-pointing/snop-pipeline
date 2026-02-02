#!/usr/bin/env python3
"""
Test ED model predictions on multiple categories and compute 68th percentile cosine metric.
"""

import numpy as np
from pathlib import Path
import argparse
import uproot
import tensorflow as tf
from scipy.optimize import minimize


def load_ed_model(model_path):
    """Load ED model with TF2/Keras3 compatibility."""
    return tf.keras.models.load_model(model_path, compile=False)


def load_category_data(cat_dir, ed_model, pdf_2d, energy_bins, cosine_bin_centers):
    """Load and process one category."""
    
    try:
        # Load neutrino direction from TPS files
        tps_dir = cat_dir / 'tps'
        es_files = sorted(tps_dir.glob('es_*_tps.root'))
        
        if len(es_files) == 0:
            print(f"  No ES files found")
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
            except Exception as e:
                continue
        
        true_nu_px = np.mean(all_neutrino_px)
        true_nu_py = np.mean(all_neutrino_py)
        true_nu_pz = np.mean(all_neutrino_pz)
        
        nu_norm = np.sqrt(true_nu_px**2 + true_nu_py**2 + true_nu_pz**2)
        true_nu_dir = np.array([true_nu_px, true_nu_py, true_nu_pz]) / nu_norm
        
        # Load cluster data
        cluster_data = {}
        for plane in ['U', 'V', 'X']:
            cluster_dir = cat_dir / f"{cat_dir.name}_cluster_images_tick3_ch2_min2_tot3_e2p0" / plane
            cluster_files = sorted(cluster_dir.glob('*.npz'))
            
            if len(cluster_files) == 0:
                print(f"  No cluster files found for plane {plane}")
                return None
            
            all_images = []
            all_metadata = []
            
            for cf in cluster_files:
                data = np.load(cf)
                images = data['images']
                metadata = data['metadata']
                
                all_images.append(images)
                all_metadata.append(metadata)
            
            cluster_data[plane] = {
                'images': np.vstack(all_images),
                'metadata': np.vstack(all_metadata)
            }
        
        # Get matching indices across planes
        n_u = len(cluster_data['U']['metadata'])
        n_v = len(cluster_data['V']['metadata'])
        n_x = len(cluster_data['X']['metadata'])
        
        min_clusters = min(n_u, n_v, n_x)
        
        # Truncate to minimum and filter for ES main track
        x_metadata = cluster_data['X']['metadata'][:min_clusters]
    is_main_track = x_metadata[:, 2] == 1
    is_es = x_metadata[:, 3] == 1
    valid_mask = is_main_track & is_es
    
    if np.sum(valid_mask) == 0:
        return None
    
    # Extract ES clusters
    es_images_u = cluster_data['U']['images'][:min_clusters][valid_mask]
    es_images_v = cluster_data['V']['images'][:min_clusters][valid_mask]
    es_images_x = cluster_data['X']['images'][:min_clusters][valid_mask]
    es_metadata = x_metadata[valid_mask]
    
    n_clusters = len(es_images_u)
    
    # Run ED model predictions
    images_3plane = np.stack([es_images_u, es_images_v, es_images_x], axis=-1)
    images_3plane = np.expand_dims(images_3plane, axis=-1)
    
    predictions = ed_model.predict(images_3plane, batch_size=32, verbose=0)
    pred_dirs = predictions / np.linalg.norm(predictions, axis=1, keepdims=True)
    
    # Get energies
    energies = es_metadata[:, 10]
    
    # Group by event
    event_ids = es_metadata[:, 0]
    unique_events = np.unique(event_ids)
    
    all_cos_angles = []
    
    for event_id in unique_events:
        event_mask = event_ids == event_id
        event_pred_dirs = pred_dirs[event_mask]
        event_energies = energies[event_mask]
        
        # MCMC optimization
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
            
            for i in range(len(event_energies)):
                energy = event_energies[i]
                cos_angle = cos_angles[i]
                
                energy_bin = np.searchsorted(energy_bins[:, 0], energy) - 1
                energy_bin = np.clip(energy_bin, 0, len(pdf_2d) - 1)
                
                cos_bin = np.searchsorted(cosine_bin_centers, cos_angle)
                cos_bin = np.clip(cos_bin, 0, len(cosine_bin_centers) - 1)
                
                pdf_val = pdf_2d[energy_bin, cos_bin]
                
                if pdf_val > 1e-10:
                    log_likelihood += np.log(pdf_val) * energy
            
            return -log_likelihood
        
        # Initial guess: energy-weighted average
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
    
        return {
            'cos_angles': np.array(all_cos_angles),
            'true_nu_dir': true_nu_dir,
            'n_events': len(unique_events),
            'n_clusters': n_clusters
        }
    
    except Exception as e:
        print(f"  Error: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description='Test ED model on multiple categories')
    parser.add_argument('--cats', nargs='+', default=['cat000035', 'cat000020', 'cat000026'], 
                       help='Category names to test')
    parser.add_argument('--ed-model', 
                       default='/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v50_100k_20251115_232348/checkpoints/model_epoch_38_val_loss_0.8709.keras',
                       help='ED model path')
    parser.add_argument('--pdf-file',
                       default='/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v50_100k_20251115_232348/cosine_energy_pdf.npz',
                       help='Energy-cosine PDF file')
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("TESTING ED MODEL ON MULTIPLE CATEGORIES")
    print("="*70)
    
    # Load models
    print(f"\nLoading ED model...")
    ed_model = load_ed_model(args.ed_model)
    
    print(f"Loading PDF...")
    data = np.load(args.pdf_file)
    pdf_2d = data['pdf_2d']
    energy_bins = data['energy_bins']
    cosine_bin_centers = data['cosine_bin_centers']
    
    # Test each category
    results = {}
    
    for cat_name in args.cats:
        print(f"\n{'='*70}")
        print(f"Processing {cat_name}...")
        print(f"{'='*70}")
        
        cat_dir = Path('/eos/project-e/ep-nu/public/sn-pointing') / cat_name
        
        result = load_category_data(cat_dir, ed_model, pdf_2d, energy_bins, cosine_bin_centers)
        
        if result is None:
            print(f"  FAILED")
            continue
        
        results[cat_name] = result
        
        cos_angles = result['cos_angles']
        
        print(f"\n  Events: {result['n_events']}")
        print(f"  Clusters: {result['n_clusters']}")
        print(f"  True neutrino direction: {result['true_nu_dir']}")
        print(f"\n  Results (MCMC with ED model):")
        print(f"    Median cos(θ):      {np.median(cos_angles):7.4f}")
        print(f"    68th %ile cos(θ):   {np.percentile(cos_angles, 68):7.4f}  ← KEY METRIC")
        print(f"    Mean cos(θ):        {np.mean(cos_angles):7.4f}")
        print(f"    Forward (cos>0):    {np.sum(cos_angles>0)}/{len(cos_angles)} ({100*np.mean(cos_angles>0):.1f}%)")
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"\n{'Category':<15} {'Events':<10} {'68th %ile cos(θ)':<20} {'Median cos(θ)':<20} {'Forward %'}")
    print("-"*70)
    
    for cat_name, result in results.items():
        cos_angles = result['cos_angles']
        print(f"{cat_name:<15} {result['n_events']:<10} {np.percentile(cos_angles, 68):7.4f}             "
              f"{np.median(cos_angles):7.4f}             {100*np.mean(cos_angles>0):5.1f}%")
    
    # Overall statistics
    all_cos = np.concatenate([r['cos_angles'] for r in results.values()])
    
    print("\n" + "="*70)
    print(f"OVERALL ({len(results)} categories, {len(all_cos)} events)")
    print("="*70)
    print(f"\n  68th percentile cos(θ):  {np.percentile(all_cos, 68):7.4f}  ← KEY METRIC")
    print(f"  Median cos(θ):           {np.median(all_cos):7.4f}")
    print(f"  Mean cos(θ):             {np.mean(all_cos):7.4f}")
    print(f"  Forward pointing:        {np.sum(all_cos>0)}/{len(all_cos)} ({100*np.mean(all_cos>0):.1f}%)")
    
    print("\n" + "="*70)
    print("BASELINE COMPARISON")
    print("="*70)
    print(f"  MCMC with TRUE e- dirs:   cos(θ) 68% = 0.9980  ← Best possible")
    print(f"  MCMC with ED model:       cos(θ) 68% = {np.percentile(all_cos, 68):.4f}  ← Current")
    print(f"  Gap to close:             Δcos(θ) = {0.9980 - np.percentile(all_cos, 68):.4f}")
    print("\n" + "="*70 + "\n")


if __name__ == '__main__':
    main()
