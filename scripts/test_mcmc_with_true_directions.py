#!/usr/bin/env python3
"""
Test MCMC reconstruction using TRUE electron directions instead of ED model predictions.
This shows the best-case scenario performance if electron directions were perfectly known.
"""

import numpy as np
from pathlib import Path
import argparse
import uproot
from scipy.optimize import minimize


def load_es_data_with_clusters(cat_dir):
    """Load ES event data and cluster information."""
    
    tps_dir = cat_dir / 'tps'
    es_files = sorted(tps_dir.glob('es_*_tps.root'))
    
    if len(es_files) == 0:
        return None
    
    # Load cluster data
    cluster_dir = cat_dir / f"{cat_dir.name}_cluster_images_tick3_ch2_min2_tot3_e2p0" / "X"
    cluster_files = sorted(cluster_dir.glob('*.npz'))
    
    if len(cluster_files) == 0:
        print(f"No cluster files found in {cluster_dir}")
        return None
    
    print(f"Found {len(es_files)} ES files and {len(cluster_files)} cluster files")
    
    # Load cluster metadata
    all_metadata = []
    for cf in cluster_files:
        data = np.load(cf)
        metadata = data['metadata']
        all_metadata.append(metadata)
    
    all_metadata = np.vstack(all_metadata)
    
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
        'metadata': all_metadata,
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


def compute_mcmc_with_true_directions(metadata, true_nu_dir, pdf_2d, energy_bins, cosine_bin_centers):
    """
    Use MCMC to find neutrino direction using TRUE electron directions from metadata.
    
    Metadata structure:
    - Position 0: event_id
    - Position 1: is_marley
    - Position 2: is_main_track
    - Position 3: is_es_interaction
    - Positions 4-6: true_pos (x,y,z)
    - Positions 7-9: true_particle_mom (px,py,pz) <- TRUE ELECTRON DIRECTION
    - Position 10: cluster_energy_mev
    """
    
    # Filter for ES main track clusters
    is_main_track = metadata[:, 2] == 1
    is_es = metadata[:, 3] == 1
    valid_mask = is_main_track & is_es
    
    es_metadata = metadata[valid_mask]
    
    if len(es_metadata) == 0:
        return None
    
    print(f"  Found {len(es_metadata)} ES main track clusters")
    
    # Group by event_id
    event_ids = es_metadata[:, 0]
    unique_events = np.unique(event_ids)
    
    print(f"  Processing {len(unique_events)} events")
    
    all_cos_angles = []
    all_angles = []
    
    for event_id in unique_events:
        event_mask = event_ids == event_id
        event_clusters = es_metadata[event_mask]
        
        # Extract true electron directions
        true_px = event_clusters[:, 7]
        true_py = event_clusters[:, 8]
        true_pz = event_clusters[:, 9]
        
        # Normalize
        norms = np.sqrt(true_px**2 + true_py**2 + true_pz**2)
        valid_dir_mask = norms > 0
        
        if np.sum(valid_dir_mask) == 0:
            continue
        
        true_dirs = np.column_stack([
            true_px[valid_dir_mask] / norms[valid_dir_mask],
            true_py[valid_dir_mask] / norms[valid_dir_mask],
            true_pz[valid_dir_mask] / norms[valid_dir_mask]
        ])
        
        # Get energies
        energies = event_clusters[valid_dir_mask, 10]
        
        # Define negative log-likelihood function
        def neg_log_likelihood(params):
            theta, phi = params
            
            # Convert to direction
            reco_dir = np.array([
                np.sin(theta) * np.cos(phi),
                np.sin(theta) * np.sin(phi),
                np.cos(theta)
            ])
            
            # Compute angles to electron directions
            cos_angles = np.dot(true_dirs, reco_dir)
            cos_angles = np.clip(cos_angles, -1, 1)
            
            # Get PDF values
            log_likelihood = 0.0
            
            for i in range(len(energies)):
                energy = energies[i]
                cos_angle = cos_angles[i]
                
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
        weights = energies / np.sum(energies)
        avg_dir = np.sum(true_dirs * weights[:, np.newaxis], axis=0)
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
    parser = argparse.ArgumentParser(description='Test MCMC with true electron directions')
    parser.add_argument('--cat-name', default='cat000035', help='Category name')
    parser.add_argument('--pdf-file', default='cosine_energy_pdf.npz', help='Energy-cosine PDF file')
    args = parser.parse_args()
    
    cat_dir = Path('/eos/project-e/ep-nu/public/sn-pointing') / args.cat_name
    
    print(f"\nAnalyzing category: {args.cat_name}")
    print(f"Path: {cat_dir}")
    print("="*70)
    
    # Load data
    print("\nLoading data...")
    data = load_es_data_with_clusters(cat_dir)
    
    if data is None:
        print("Failed to load data")
        return
    
    print(f"True neutrino direction: {data['true_nu_dir']}")
    
    # Load PDF
    print(f"\nLoading energy-cosine PDF from {args.pdf_file}...")
    pdf_2d, energy_bins, cosine_bin_centers = load_energy_pdf(args.pdf_file)
    print(f"PDF shape: {pdf_2d.shape}")
    
    # Run MCMC with true directions
    print("\nRunning MCMC optimization with TRUE electron directions...")
    angles, cos_angles = compute_mcmc_with_true_directions(
        data['metadata'], data['true_nu_dir'], pdf_2d, energy_bins, cosine_bin_centers
    )
    
    if angles is None or len(angles) == 0:
        print("No valid events")
        return
    
    # Print results
    print("\n" + "="*70)
    print("RESULTS: MCMC WITH TRUE ELECTRON DIRECTIONS")
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
    print(f"Physics limit (ES scattering):     ~8° median")
    print(f"MCMC with TRUE e- directions:      {np.median(angles):.1f}° median")
    print(f"MCMC with ED model predictions:    ~113° median (from previous analysis)")
    
    # Distribution
    forward = np.sum(cos_angles > 0)
    backward = np.sum(cos_angles < 0)
    print(f"\nPointing distribution:")
    print(f"  Forward (cos > 0):  {forward}/{len(angles)} ({100*forward/len(angles):.1f}%)")
    print(f"  Backward (cos < 0): {backward}/{len(angles)} ({100*backward/len(angles):.1f}%)")
    
    print("\n" + "="*70 + "\n")


if __name__ == '__main__':
    main()
