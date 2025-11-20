#!/usr/bin/env python3
"""
Optimized EMCEE-based MCMC reconstruction for supernova pointing.
Uses 64 walkers with 2000 steps for better convergence.
"""

import numpy as np
from pathlib import Path
import argparse
from scipy.interpolate import RegularGridInterpolator
from scipy.stats import circstd
import emcee


def load_matched_cluster_images_3plane(cat_dir, cat_name):
    """Load cluster images matched across U, V, X planes file-by-file."""
    cluster_dir_base = Path(cat_dir) / f"{cat_name}_cluster_images_tick3_ch2_min2_tot3_e3p0"
    
    images_u_all = []
    images_v_all = []
    images_x_all = []
    metadata_all = []
    
    # Get list of files (use X plane as reference)
    cluster_dir_x = cluster_dir_base / 'X'
    npz_files_x = sorted(cluster_dir_x.glob("*.npz"))
    
    for npz_file_x in npz_files_x:
        filename = npz_file_x.name
        # Get corresponding files in U and V
        npz_file_u = cluster_dir_base / 'U' / filename.replace('planeX', 'planeU')
        npz_file_v = cluster_dir_base / 'V' / filename.replace('planeX', 'planeV')
        
        if not (npz_file_u.exists() and npz_file_v.exists()):
            continue
        
        # Load data from all 3 planes
        data_u = np.load(npz_file_u)
        data_v = np.load(npz_file_v)
        data_x = np.load(npz_file_x)
        
        images_u = data_u['images']
        images_v = data_v['images']
        images_x = data_x['images']
        metadata_u = data_u['metadata']
        metadata_v = data_v['metadata']
        metadata_x = data_x['metadata']
        
        # Filter for main tracks only
        is_main_u = metadata_u[:, 2] == 1
        is_main_v = metadata_v[:, 2] == 1
        is_main_x = metadata_x[:, 2] == 1
        
        images_u_main = images_u[is_main_u]
        images_v_main = images_v[is_main_v]
        images_x_main = images_x[is_main_x]
        metadata_u_main = metadata_u[is_main_u]
        metadata_v_main = metadata_v[is_main_v]
        metadata_x_main = metadata_x[is_main_x]
        
        # Match by cluster_id within this file
        cluster_ids_u = metadata_u_main[:, 0]
        cluster_ids_v = metadata_v_main[:, 0]
        cluster_ids_x = metadata_x_main[:, 0]
        
        common_ids = np.intersect1d(np.intersect1d(cluster_ids_u, cluster_ids_v), cluster_ids_x)
        
        # Get matched clusters
        for cid in common_ids:
            idx_u = np.where(cluster_ids_u == cid)[0][0]
            idx_v = np.where(cluster_ids_v == cid)[0][0]
            idx_x = np.where(cluster_ids_x == cid)[0][0]
            
            images_u_all.append(images_u_main[idx_u])
            images_v_all.append(images_v_main[idx_v])
            images_x_all.append(images_x_main[idx_x])
            metadata_all.append(metadata_x_main[idx_x])
    
    images_u_matched = np.array(images_u_all)
    images_v_matched = np.array(images_v_all)
    images_x_matched = np.array(images_x_all)
    metadata_matched = np.array(metadata_all)
    
    return images_u_matched, images_v_matched, images_x_matched, metadata_matched


def load_pdf(pdf_path):
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
    
    return interpolator


def loglike_with_pdf(args, pred_x, pred_y, pred_z, energies, pdf_interpolator):
    """Log-likelihood using PDF in spherical coordinates."""
    theta, phi = args
    
    # True direction in Cartesian
    true_x = np.sin(phi) * np.cos(theta)
    true_y = np.sin(phi) * np.sin(theta)
    true_z = np.cos(phi)
    
    # Cosine angles between true and predictions
    cos_angles = pred_x * true_x + pred_y * true_y + pred_z * true_z
    cos_angles = np.clip(cos_angles, -1, 1)
    
    # Evaluate PDF for each cluster
    points = np.column_stack([energies, cos_angles])
    pdf_values = pdf_interpolator(points)
    pdf_values = np.maximum(pdf_values, 1e-10)
    
    return np.sum(np.log(pdf_values))


def logprior(args):
    """Log-prior with sin(φ) for uniform sampling on sphere."""
    theta, phi = args
    
    # Bounds
    if not (-np.pi <= theta <= np.pi):
        return -np.inf
    if not (0 <= phi <= np.pi):
        return -np.inf
    
    # sin(φ) prior for uniform sphere sampling
    return np.log(np.sin(phi) + 1e-10)


def logpost(args, pred_x, pred_y, pred_z, energies, pdf_interpolator):
    """Log-posterior."""
    lp = logprior(args)
    if not np.isfinite(lp):
        return -np.inf
    return lp + loglike_with_pdf(args, pred_x, pred_y, pred_z, energies, pdf_interpolator)


def run_emcee_mcmc(pred_x, pred_y, pred_z, energies, pdf_interpolator,
                   nwalkers=64, nsteps=2000, discard=400, verbose=True):
    """Run emcee ensemble sampler with optimized parameters."""
    ndim = 2
    
    # Initialize walkers near isotropic
    theta_init = np.random.uniform(-np.pi, np.pi, nwalkers)
    phi_init = np.arccos(np.random.uniform(-1, 1, nwalkers))
    p0 = np.column_stack([theta_init, phi_init])
    
    # Create sampler with StretchMove (best for this problem)
    sampler = emcee.EnsembleSampler(
        nwalkers, ndim, logpost,
        args=(pred_x, pred_y, pred_z, energies, pdf_interpolator),
        moves=emcee.moves.StretchMove()
    )
    
    # Run MCMC
    if verbose:
        print(f"Running emcee: {nwalkers} walkers × {nsteps} steps...")
    
    sampler.run_mcmc(p0, nsteps, progress=False)
    
    # Extract samples
    samples = sampler.get_chain(discard=discard, flat=False)
    flat_samples = sampler.get_chain(discard=discard, flat=True)
    log_prob = sampler.get_log_prob(discard=discard, flat=True)
    
    # Compute mean direction using circular statistics
    theta_samples = flat_samples[:, 0]
    phi_samples = flat_samples[:, 1]
    
    mean_theta = np.arctan2(np.sin(theta_samples).mean(), np.cos(theta_samples).mean())
    mean_phi = phi_samples.mean()
    
    # Uncertainties
    theta_std = circstd(theta_samples)
    phi_std = phi_samples.std()
    
    # 68% credible angle
    mean_x = np.sin(mean_phi) * np.cos(mean_theta)
    mean_y = np.sin(mean_phi) * np.sin(mean_theta)
    mean_z = np.cos(mean_phi)
    
    sample_x = np.sin(phi_samples) * np.cos(theta_samples)
    sample_y = np.sin(phi_samples) * np.sin(theta_samples)
    sample_z = np.cos(phi_samples)
    
    cos_angles = sample_x * mean_x + sample_y * mean_y + sample_z * mean_z
    cos_angles = np.clip(cos_angles, -1, 1)
    angles = np.degrees(np.arccos(cos_angles))
    omega_68 = np.percentile(angles, 68)
    
    acceptance = np.mean(sampler.acceptance_fraction)
    
    if verbose:
        print(f"Acceptance fraction: {100*acceptance:.1f}%")
        print(f"Mean direction: θ={np.degrees(mean_theta):.2f}°, φ={np.degrees(mean_phi):.2f}°")
        print(f"Uncertainties: Δθ={np.degrees(theta_std):.2f}°, Δφ={np.degrees(phi_std):.2f}°")
        print(f"68% credible angle: {omega_68:.2f}°")
    
    return {
        'theta': mean_theta,
        'phi': mean_phi,
        'theta_std': theta_std,
        'phi_std': phi_std,
        'omega_68': np.radians(omega_68),
        'samples': samples,
        'flat_samples': flat_samples,
        'log_prob': log_prob,
        'acceptance_fraction': acceptance
    }


def run_scenario_emcee(cat_dir, cat_name, scenario, ed_model_path, pdf_interpolator,
                       nwalkers=64, nsteps=2000, discard=400, verbose=True):
    """Run any scenario using emcee MCMC."""
    import tensorflow as tf
    
    if verbose:
        print(f"\n{'='*70}")
        print(f"SCENARIO (EMCEE): {scenario.upper()}")
        print(f"{'='*70}\n")
    
    # Load matched cluster images
    images_u, images_v, images_x, metadata = load_matched_cluster_images_3plane(cat_dir, cat_name)
    
    if verbose:
        print(f"Loaded {len(images_u)} matched clusters across U, V, X planes")
    
    if len(images_u) == 0:
        raise ValueError("No matched clusters found")
    
    # Filter based on scenario
    if scenario == 'perfect_ct':
        # ES only
        is_valid = metadata[:, 3] == 1
    elif scenario == 'es_main_cc_shower':
        # ES main + CC shower
        is_es_main = (metadata[:, 3] == 1) & (metadata[:, 2] == 1)
        is_cc_shower = (metadata[:, 3] == 2) & (metadata[:, 2] == 0)
        is_valid = is_es_main | is_cc_shower
    elif scenario == 'es_main_cc_all':
        # ES main + all CC
        is_es_main = (metadata[:, 3] == 1) & (metadata[:, 2] == 1)
        is_cc = metadata[:, 3] == 2
        is_valid = is_es_main | is_cc
    elif scenario == 'es_all_cc_shower':
        # All ES + CC shower
        is_es = metadata[:, 3] == 1
        is_cc_shower = (metadata[:, 3] == 2) & (metadata[:, 2] == 0)
        is_valid = is_es | is_cc_shower
    elif scenario == 'es_all_cc_all':
        # All ES + all CC
        is_valid = (metadata[:, 3] == 1) | (metadata[:, 3] == 2)
    elif scenario == 'all_tracks_all_showers':
        # Everything
        is_valid = np.ones(len(metadata), dtype=bool)
    else:
        raise ValueError(f"Unknown scenario: {scenario}")
    
    if np.sum(is_valid) == 0:
        raise ValueError(f"No valid clusters found for scenario {scenario}")
    
    sel_images_u = images_u[is_valid]
    sel_images_v = images_v[is_valid]
    sel_images_x = images_x[is_valid]
    sel_metadata = metadata[is_valid]
    
    if verbose:
        print(f"Selected clusters: {len(sel_images_u)}")
    
    # Load ED model and predict
    ed_model = tf.keras.models.load_model(ed_model_path, compile=False)
    
    # Prepare images for ED model: 3 separate inputs with channel dimension
    sel_images_u_input = sel_images_u[..., np.newaxis]
    sel_images_v_input = sel_images_v[..., np.newaxis]
    sel_images_x_input = sel_images_x[..., np.newaxis]
    
    pred_directions = ed_model.predict([sel_images_u_input, sel_images_v_input, sel_images_x_input], 
                                       verbose=0, batch_size=32)
    
    # Normalize predictions
    norms = np.linalg.norm(pred_directions, axis=1, keepdims=True)
    pred_directions = pred_directions / norms
    
    pred_x = pred_directions[:, 0]
    pred_y = pred_directions[:, 1]
    pred_z = pred_directions[:, 2]
    
    # Extract energies
    energies = sel_metadata[:, 11]
    
    # Run emcee MCMC
    mcmc_result = run_emcee_mcmc(
        pred_x, pred_y, pred_z, energies, pdf_interpolator,
        nwalkers=nwalkers, nsteps=nsteps, discard=discard, verbose=verbose
    )
    
    # Convert best-fit to Cartesian
    theta = mcmc_result['theta']
    phi = mcmc_result['phi']
    
    best_x = np.sin(phi) * np.cos(theta)
    best_y = np.sin(phi) * np.sin(theta)
    best_z = np.cos(phi)
    
    # Compare with true direction
    true_nu_px = sel_metadata[0, 15]
    true_nu_py = sel_metadata[0, 16]
    true_nu_pz = sel_metadata[0, 17]
    
    true_norm = np.sqrt(true_nu_px**2 + true_nu_py**2 + true_nu_pz**2)
    true_nu_px /= true_norm
    true_nu_py /= true_norm
    true_nu_pz /= true_norm
    
    cos_theta = best_x * true_nu_px + best_y * true_nu_py + best_z * true_nu_pz
    cos_theta = np.clip(cos_theta, -1, 1)
    angular_error_rad = np.arccos(cos_theta)
    angular_error_deg = np.degrees(angular_error_rad)
    
    if verbose:
        print(f"\nAngular error: {angular_error_deg:.2f}°")
    
    return {
        'emcee_theta': theta,
        'emcee_phi': phi,
        'emcee_best_dir_x': best_x,
        'emcee_best_dir_y': best_y,
        'emcee_best_dir_z': best_z,
        'emcee_angular_error_deg': angular_error_deg,
        'emcee_cos_theta': cos_theta,
        'emcee_theta_std': mcmc_result['theta_std'],
        'emcee_phi_std': mcmc_result['phi_std'],
        'emcee_omega_68': mcmc_result['omega_68'],
        'emcee_acceptance_fraction': mcmc_result['acceptance_fraction'],
        'emcee_n_clusters_used': len(pred_x),
        'emcee_true_nu_px': true_nu_px,
        'emcee_true_nu_py': true_nu_py,
        'emcee_true_nu_pz': true_nu_pz
    }


def main():
    parser = argparse.ArgumentParser(description='Optimized EMCEE-based supernova reconstruction')
    parser.add_argument('--cat-name', required=True, help='Cat name (e.g., cat000001)')
    parser.add_argument('--cat-dir', required=True, help='Cat directory')
    parser.add_argument('--ed-model', required=True, help='ED model path')
    parser.add_argument('--pdf-file', required=True, help='PDF file path')
    parser.add_argument('--scenarios', nargs='+', default=['perfect_ct'], 
                        help='Scenarios to run')
    parser.add_argument('--nwalkers', type=int, default=64, help='Number of walkers')
    parser.add_argument('--nsteps', type=int, default=2000, help='Number of steps')
    parser.add_argument('--discard', type=int, default=400, help='Burn-in steps')
    parser.add_argument('--use-eos-structure', action='store_true', help='Save to EOS structure')
    
    args = parser.parse_args()
    
    print(f"{'='*70}")
    print(f"EMCEE RECONSTRUCTION FOR {args.cat_name}")
    print(f"{'='*70}")
    
    # Load PDF
    print(f"\nLoading PDF from: {args.pdf_file}")
    pdf_interpolator = load_pdf(args.pdf_file)
    print(f"PDF loaded")
    
    # Run scenarios
    results = {}
    for scenario in args.scenarios:
        try:
            results[scenario] = run_scenario_emcee(
                args.cat_dir, args.cat_name, scenario, args.ed_model, pdf_interpolator,
                nwalkers=args.nwalkers, nsteps=args.nsteps, discard=args.discard, verbose=True
            )
        except Exception as e:
            print(f"\n✗ {scenario} failed: {e}")
            continue
    
    # Save results
    if args.use_eos_structure:
        pipeline_dir = Path(args.cat_dir) / 'pipeline'
        pipeline_dir.mkdir(parents=True, exist_ok=True)
        
        for scenario, result in results.items():
            output_file = pipeline_dir / f"{args.cat_name}_scenario_{scenario}_emcee.npz"
            
            save_dict = {}
            for key, value in result.items():
                save_dict[f"{scenario}_{key}"] = value
            
            np.savez_compressed(output_file, **save_dict)
            print(f"\n✓ Saved: {output_file}")
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
