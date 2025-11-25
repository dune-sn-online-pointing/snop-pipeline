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
    # Try two possible locations for cluster images
    cluster_dir_base = Path(cat_dir) / f"{cat_name}_cluster_images_tick3_ch2_min2_tot3_e3p0"
    if not cluster_dir_base.exists():
        # Try alternative location
        alt_cat_dir = f"/eos/project-e/ep-nu/evilla/sn-pointing/{cat_name}"
        cluster_dir_base = Path(alt_cat_dir) / f"{cat_name}_cluster_images_tick3_ch2_min2_tot3_e3p0"
    
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


def loglike_with_pdf(args, pred_x, pred_y, pred_z, energies, pdf_interpolator, weights=None):
    """Log-likelihood using PDF in spherical coordinates."""
    theta, phi = args
    
    # True direction in Cartesian (theta=polar from Z, phi=azimuthal from X)
    true_x = np.sin(theta) * np.cos(phi)
    true_y = np.sin(theta) * np.sin(phi)
    true_z = np.cos(theta)
    
    # Cosine angles between true and predictions
    cos_angles = pred_x * true_x + pred_y * true_y + pred_z * true_z
    cos_angles = np.clip(cos_angles, -1, 1)
    
    # Evaluate PDF for each cluster
    points = np.column_stack([energies, cos_angles])
    pdf_values = pdf_interpolator(points)
    pdf_values = np.maximum(pdf_values, 1e-10)
    
    log_pdf_values = np.log(pdf_values)
    
    # Apply weights if provided
    if weights is not None:
        log_pdf_values = log_pdf_values * weights
    
    return np.sum(log_pdf_values)


def logprior(args):
    """Log-prior with sin(θ) for uniform sampling on sphere."""
    theta, phi = args
    
    # Bounds: theta is polar [0, π], phi is azimuthal [-π, π]
    if not (0 <= theta <= np.pi):
        return -np.inf
    if not (-np.pi <= phi <= np.pi):
        return -np.inf
    
    # sin(θ) prior for uniform sphere sampling
    return np.log(np.sin(theta) + 1e-10)


def logpost(args, pred_x, pred_y, pred_z, energies, pdf_interpolator, weights=None):
    """Log-posterior."""
    lp = logprior(args)
    if not np.isfinite(lp):
        return -np.inf
    return lp + loglike_with_pdf(args, pred_x, pred_y, pred_z, energies, pdf_interpolator, weights=weights)


def run_emcee_mcmc(pred_x, pred_y, pred_z, energies, pdf_interpolator,
                   nwalkers=64, nsteps=2000, discard=400, weights=None, verbose=True):
    """Run emcee ensemble sampler with optimized parameters."""
    ndim = 2
    
    # Initialize walkers near isotropic
    theta_init = np.random.uniform(-np.pi, np.pi, nwalkers)
    phi_init = np.arccos(np.random.uniform(-1, 1, nwalkers))
    p0 = np.column_stack([theta_init, phi_init])
    
    # Create sampler with StretchMove (best for this problem)
    sampler = emcee.EnsembleSampler(
        nwalkers, ndim, logpost,
        args=(pred_x, pred_y, pred_z, energies, pdf_interpolator, weights),
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
    mean_x = np.sin(mean_theta) * np.cos(mean_phi)
    mean_y = np.sin(mean_theta) * np.sin(mean_phi)
    mean_z = np.cos(mean_theta)
    
    sample_x = np.sin(theta_samples) * np.cos(phi_samples)
    sample_y = np.sin(theta_samples) * np.sin(phi_samples)
    sample_z = np.cos(theta_samples)
    
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


def run_scenario_emcee(cat_dir, cat_name, scenario, ed_model_path, ct_model_path, pdf_interpolator,
                       nwalkers=64, nsteps=2000, discard=400, verbose=True):
    """
    Run scenario using emcee MCMC or simple averaging.
    
    Scenarios:
    1. best_case: Use true electron directions + MCMC
    2. perfect_ct: ES main tracks + ED network + MCMC
    3. full_pipeline: All clusters + CT network + ED network + MCMC (no weights)
    4. weighted_ct: All clusters + CT network (with weights) + ED network + MCMC
    5. perfect_ct_e_gt_10mev: ES main tracks + ED network + MCMC, E > 10 MeV cut
    6. perfect_ct_e_gt_5mev: ES main tracks + ED network + MCMC, E > 5 MeV cut
    7. simple_average: ES main tracks + ED network, simple average (no MCMC)
    8. weighted_average: ES main tracks + ED network, energy-weighted average (no MCMC)
    9. simple_average_ct: All clusters + CT network (threshold 0.8) + ED network, simple average (no MCMC)
    """
    import tensorflow as tf
    
    if verbose:
        print(f"\n{'='*70}")
        print(f"SCENARIO (EMCEE): {scenario.upper()}")
        print(f"{'='*70}\n")
    
    # Load matched cluster images
    images_u, images_v, images_x, metadata = load_matched_cluster_images_3plane(cat_dir, cat_name)
    
    if verbose:
        print(f"Loaded {len(images_u)} matched main-track clusters across U, V, X planes")
    
    if len(images_u) == 0:
        raise ValueError("No matched clusters found")
    
    # SCENARIO-SPECIFIC FILTERING AND PROCESSING
    ct_weights = None
    
    if scenario == 'best_case':
        # Scenario 1: Use TRUE electron directions (from metadata columns 7-9)
        # Only ES main tracks
        is_es = metadata[:, 3] == 1
        sel_metadata = metadata[is_es]
        
        if verbose:
            print(f"Selected {len(sel_metadata)} ES main tracks")
        
        # Extract TRUE electron directions
        px = sel_metadata[:, 7]
        py = sel_metadata[:, 8]
        pz = sel_metadata[:, 9]
        
        # Normalize
        norms = np.sqrt(px**2 + py**2 + pz**2)
        pred_x = px / norms
        pred_y = py / norms
        pred_z = pz / norms
        
        # Extract energies (apply 3 MeV cut)
        energies = sel_metadata[:, 11]
        energy_cut = energies >= 3.0
        pred_x = pred_x[energy_cut]
        pred_y = pred_y[energy_cut]
        pred_z = pred_z[energy_cut]
        energies = energies[energy_cut]
        sel_metadata = sel_metadata[energy_cut]
        
        if verbose:
            print(f"After E > 3 MeV cut: {len(energies)} clusters")
    
    elif scenario in ['perfect_ct', 'perfect_ct_e_gt_10mev', 'perfect_ct_e_gt_5mev']:
        # Scenarios 2, 5, 6: ES main tracks + ED network
        is_es = metadata[:, 3] == 1
        sel_images_u = images_u[is_es]
        sel_images_v = images_v[is_es]
        sel_images_x = images_x[is_es]
        sel_metadata = metadata[is_es]
        
        if verbose:
            print(f"Selected {len(sel_images_u)} ES main tracks")
        
        # Load ED model and predict
        if verbose:
            print(f"Loading ED model from: {ed_model_path}")
        ed_model = tf.keras.models.load_model(ed_model_path, compile=False)
        
        sel_images_u_input = sel_images_u[..., np.newaxis]
        sel_images_v_input = sel_images_v[..., np.newaxis]
        sel_images_x_input = sel_images_x[..., np.newaxis]
        
        if verbose:
            print("Running ED inference...")
        pred_directions = ed_model.predict([sel_images_u_input, sel_images_v_input, sel_images_x_input], 
                                          verbose=0, batch_size=32)
        
        norms = np.linalg.norm(pred_directions, axis=1, keepdims=True)
        pred_directions = pred_directions / norms
        
        pred_x = pred_directions[:, 0]
        pred_y = pred_directions[:, 1]
        pred_z = pred_directions[:, 2]
        
        # Apply energy cuts based on scenario
        energies = sel_metadata[:, 11]
        if scenario == 'perfect_ct_e_gt_10mev':
            energy_cut = energies >= 10.0
            if verbose:
                print(f"Applying E > 10 MeV cut")
        elif scenario == 'perfect_ct_e_gt_5mev':
            energy_cut = energies >= 5.0
            if verbose:
                print(f"Applying E > 5 MeV cut")
        else:
            energy_cut = energies >= 3.0
        
        pred_x = pred_x[energy_cut]
        pred_y = pred_y[energy_cut]
        pred_z = pred_z[energy_cut]
        energies = energies[energy_cut]
        sel_metadata = sel_metadata[energy_cut]
        
        if verbose:
            print(f"After energy cut: {len(energies)} clusters")
    
    elif scenario in ['full_pipeline', 'weighted_ct']:
        # Scenarios 3, 4: All clusters + CT network + ED network
        # Use ALL main-track clusters (no filtering by interaction type)
        sel_images_u = images_u
        sel_images_v = images_v
        sel_images_x = images_x
        sel_metadata = metadata
        
        if verbose:
            print(f"Using all {len(sel_images_u)} main-track clusters")
        
        # Load CT model to filter
        if ct_model_path is None:
            raise ValueError(f"Scenario {scenario} requires --ct-model")
        
        if verbose:
            print(f"Loading CT model from: {ct_model_path}")
        ct_model = tf.keras.models.load_model(ct_model_path, compile=False)
        
        # For CT model, we need volume images (not cluster images)
        # We'll use the cluster images as proxy and run CT on them
        # This is a simplification - ideally we'd load proper volume images
        volume_images_input = sel_images_x[..., np.newaxis]
        
        if verbose:
            print("Running CT inference...")
        ct_predictions = ct_model.predict(volume_images_input, verbose=0, batch_size=16)
        
        # CT outputs [N, 2]: [P(ES), P(CC)]
        if ct_predictions.shape[1] == 2:
            es_probs = ct_predictions[:, 0]
        else:
            es_probs = ct_predictions.flatten()
        
        # Select ES candidates (ES prob > 0.8)
        es_candidates = es_probs > 0.8
        
        if verbose:
            print(f"CT selected {es_candidates.sum()} ES candidates from {len(es_probs)} clusters")
            print(f"  ES prob range: [{es_probs.min():.3f}, {es_probs.max():.3f}]")
        
        # Filter to ES candidates
        sel_images_u = sel_images_u[es_candidates]
        sel_images_v = sel_images_v[es_candidates]
        sel_images_x = sel_images_x[es_candidates]
        sel_metadata = sel_metadata[es_candidates]
        selected_es_probs = es_probs[es_candidates]
        
        # Load ED model and predict
        if verbose:
            print(f"Loading ED model from: {ed_model_path}")
        ed_model = tf.keras.models.load_model(ed_model_path, compile=False)
        
        sel_images_u_input = sel_images_u[..., np.newaxis]
        sel_images_v_input = sel_images_v[..., np.newaxis]
        sel_images_x_input = sel_images_x[..., np.newaxis]
        
        if verbose:
            print(f"Running ED inference on {len(sel_images_u)} clusters...")
        pred_directions = ed_model.predict([sel_images_u_input, sel_images_v_input, sel_images_x_input], 
                                          verbose=0, batch_size=32)
        
        norms = np.linalg.norm(pred_directions, axis=1, keepdims=True)
        pred_directions = pred_directions / norms
        
        pred_x = pred_directions[:, 0]
        pred_y = pred_directions[:, 1]
        pred_z = pred_directions[:, 2]
        
        # Apply 3 MeV energy cut
        energies = sel_metadata[:, 11]
        energy_cut = energies >= 3.0
        pred_x = pred_x[energy_cut]
        pred_y = pred_y[energy_cut]
        pred_z = pred_z[energy_cut]
        energies = energies[energy_cut]
        sel_metadata = sel_metadata[energy_cut]
        selected_es_probs = selected_es_probs[energy_cut]
        
        # For weighted_ct scenario, use ES probabilities as weights
        if scenario == 'weighted_ct':
            ct_weights = selected_es_probs
            if verbose:
                print(f"Using CT weights (ES probabilities)")
        
        if verbose:
            print(f"After E > 3 MeV cut: {len(energies)} clusters")
    
    elif scenario == 'simple_average_ct':
        # Scenario 9: All clusters + CT network (threshold 0.8) + ED network, simple average (no MCMC)
        sel_images_u = images_u
        sel_images_v = images_v
        sel_images_x = images_x
        sel_metadata = metadata
        
        if verbose:
            print(f"Using all {len(sel_images_u)} main-track clusters")
        
        # Load CT model to filter
        if ct_model_path is None:
            raise ValueError(f"Scenario {scenario} requires --ct-model")
        
        if verbose:
            print(f"Loading CT model from: {ct_model_path}")
        ct_model = tf.keras.models.load_model(ct_model_path, compile=False)
        
        volume_images_input = sel_images_x[..., np.newaxis]
        
        if verbose:
            print("Running CT inference...")
        ct_predictions = ct_model.predict(volume_images_input, verbose=0, batch_size=16)
        
        # CT outputs [N, 2]: [P(ES), P(CC)]
        if ct_predictions.shape[1] == 2:
            es_probs = ct_predictions[:, 0]
        else:
            es_probs = ct_predictions.flatten()
        
        # Select ES candidates (ES prob > 0.8)
        es_candidates = es_probs > 0.8
        
        if verbose:
            print(f"CT selected {es_candidates.sum()} ES candidates from {len(es_probs)} clusters")
            print(f"  ES prob range: [{es_probs.min():.3f}, {es_probs.max():.3f}]")
        
        # Filter to ES candidates
        sel_images_u = sel_images_u[es_candidates]
        sel_images_v = sel_images_v[es_candidates]
        sel_images_x = sel_images_x[es_candidates]
        sel_metadata = sel_metadata[es_candidates]
        
        # Load ED model and predict
        if verbose:
            print(f"Loading ED model from: {ed_model_path}")
        import keras
        ed_model = keras.saving.load_model(ed_model_path, compile=False)
        
        sel_images_u_input = sel_images_u[..., np.newaxis]
        sel_images_v_input = sel_images_v[..., np.newaxis]
        sel_images_x_input = sel_images_x[..., np.newaxis]
        
        if verbose:
            print(f"Running ED inference on {len(sel_images_u)} clusters...")
        pred_directions = ed_model.predict([sel_images_u_input, sel_images_v_input, sel_images_x_input],
                                          verbose=0, batch_size=32)
        
        norms = np.linalg.norm(pred_directions, axis=1, keepdims=True)
        pred_directions = pred_directions / norms
        
        pred_x = pred_directions[:, 0]
        pred_y = pred_directions[:, 1]
        pred_z = pred_directions[:, 2]
        
        # Apply 3 MeV energy cut
        energies = sel_metadata[:, 11]
        energy_cut = energies >= 3.0
        pred_x = pred_x[energy_cut]
        pred_y = pred_y[energy_cut]
        pred_z = pred_z[energy_cut]
        energies = energies[energy_cut]
        sel_metadata = sel_metadata[energy_cut]
        
        if verbose:
            print(f"After E > 3 MeV cut: {len(energies)} clusters")
        
        # Simple average: equal weights
        weights = np.ones(len(energies))
        
        # Weighted average of x, y, z components
        weight_sum = weights.sum()
        avg_x = np.sum(weights * pred_x) / weight_sum
        avg_y = np.sum(weights * pred_y) / weight_sum
        avg_z = np.sum(weights * pred_z) / weight_sum
        
        # Normalize
        norm = np.sqrt(avg_x**2 + avg_y**2 + avg_z**2)
        avg_x /= norm
        avg_y /= norm
        avg_z /= norm
        
        # Convert to spherical
        avg_theta = np.degrees(np.arccos(np.clip(avg_z, -1, 1)))
        avg_phi = np.degrees(np.arctan2(avg_y, avg_x))
        
        if verbose:
            print(f"Average direction: θ={avg_theta:.2f}°, φ={avg_phi:.2f}°")
        
        # Get true direction (columns 15-17)
        true_nu_px = sel_metadata[0, 15]
        true_nu_py = sel_metadata[0, 16]
        true_nu_pz = sel_metadata[0, 17]
        
        # Normalize
        true_norm = np.sqrt(true_nu_px**2 + true_nu_py**2 + true_nu_pz**2)
        true_nu_px /= true_norm
        true_nu_py /= true_norm
        true_nu_pz /= true_norm
        
        # Calculate error
        cos_angle = np.clip(avg_x * true_nu_px + avg_y * true_nu_py + avg_z * true_nu_pz, -1, 1)
        angular_error = np.degrees(np.arccos(cos_angle))
        
        if verbose:
            print(f"\nAngular error: {angular_error:.2f}°\n")
        
        # Return result (no MCMC)
        return {
            'theta': avg_theta,
            'phi': avg_phi,
            'best_dir_x': avg_x,
            'best_dir_y': avg_y,
            'best_dir_z': avg_z,
            'angular_error': angular_error,
            'cos_theta': cos_angle,
            'theta_std': 0.0,
            'phi_std': 0.0,
            'omega_68': 0.0,
            'acceptance_fraction': 1.0,
            'n_clusters_used': len(energies),
            'n_es_clusters': int(np.sum(sel_metadata[:, 3] == 1)),
            'n_cc_clusters': int(np.sum(sel_metadata[:, 3] == 0)),
            'true_nu_px': true_nu_px,
            'true_nu_py': true_nu_py,
            'true_nu_pz': true_nu_pz,
            'chain': None,
            'log_prob': None
        }
    
    elif scenario == 'weighted_average_ct':
        # Scenario 10: All clusters + CT weights + ED network, energy-weighted average (no threshold, no MCMC)
        sel_images_u = images_u
        sel_images_v = images_v
        sel_images_x = images_x
        sel_metadata = metadata
        
        if verbose:
            print(f"Using all {len(sel_images_u)} main-track clusters")
        
        # Load CT model to get weights
        if ct_model_path is None:
            raise ValueError(f"Scenario {scenario} requires --ct-model")
        
        if verbose:
            print(f"Loading CT model from: {ct_model_path}")
        ct_model = tf.keras.models.load_model(ct_model_path, compile=False)
        
        # For CT model, we need volume images
        volume_images_input = sel_images_x[..., np.newaxis]
        
        if verbose:
            print("Running CT inference...")
        ct_predictions = ct_model.predict(volume_images_input, verbose=0, batch_size=16)
        
        # CT outputs [N, 2]: [P(ES), P(CC)]
        if ct_predictions.shape[1] == 2:
            es_probs = ct_predictions[:, 0]
        else:
            es_probs = ct_predictions.flatten()
        
        if verbose:
            print(f"CT ES prob range: [{es_probs.min():.3f}, {es_probs.max():.3f}]")
            print(f"Using all {len(es_probs)} clusters with CT weights (no threshold)")
        
        # Load ED model and predict
        if verbose:
            print(f"Loading ED model from: {ed_model_path}")
        ed_model = tf.keras.models.load_model(ed_model_path, compile=False)
        
        sel_images_u_input = sel_images_u[..., np.newaxis]
        sel_images_v_input = sel_images_v[..., np.newaxis]
        sel_images_x_input = sel_images_x[..., np.newaxis]
        
        if verbose:
            print("Running ED inference...")
        ed_predictions = ed_model.predict(
            [sel_images_u_input, sel_images_v_input, sel_images_x_input],
            verbose=0,
            batch_size=16
        )
        
        pred_x = ed_predictions[:, 0]
        pred_y = ed_predictions[:, 1]
        pred_z = ed_predictions[:, 2]
        
        # Apply 3 MeV energy cut
        energies = sel_metadata[:, 11]
        energy_cut = energies >= 3.0
        pred_x = pred_x[energy_cut]
        pred_y = pred_y[energy_cut]
        pred_z = pred_z[energy_cut]
        energies = energies[energy_cut]
        sel_metadata = sel_metadata[energy_cut]
        es_probs = es_probs[energy_cut]
        
        if verbose:
            print(f"After E > 3 MeV cut: {len(energies)} clusters")
        
        # Compute combined weights: energy * CT_weight
        energy_weights = energies / np.sum(energies)
        combined_weights = energy_weights * es_probs
        combined_weights = combined_weights / np.sum(combined_weights)  # Normalize
        
        if verbose:
            print(f"Using combined weights (energy * CT ES prob)")
            print(f"  Combined weight range: [{combined_weights.min():.6f}, {combined_weights.max():.6f}]")
        
        # Weighted average direction
        avg_x = np.sum(pred_x * combined_weights)
        avg_y = np.sum(pred_y * combined_weights)
        avg_z = np.sum(pred_z * combined_weights)
        
        # Normalize
        norm = np.sqrt(avg_x**2 + avg_y**2 + avg_z**2)
        reco_direction = np.array([avg_x, avg_y, avg_z]) / norm
        
        # Compute angular error
        true_nu_px = sel_metadata[0, 15]
        true_nu_py = sel_metadata[0, 16]
        true_nu_pz = sel_metadata[0, 17]
        true_norm = np.sqrt(true_nu_px**2 + true_nu_py**2 + true_nu_pz**2)
        true_direction = np.array([true_nu_px, true_nu_py, true_nu_pz]) / true_norm
        
        cos_theta = np.dot(reco_direction, true_direction)
        cos_theta = np.clip(cos_theta, -1.0, 1.0)
        angular_error_deg = np.degrees(np.arccos(cos_theta))
        
        if verbose:
            print(f"Reconstructed direction: [{reco_direction[0]:.4f}, {reco_direction[1]:.4f}, {reco_direction[2]:.4f}]")
            print(f"Angular error: {angular_error_deg:.2f} degrees")
        
        # Count ES and CC clusters
        n_es_clusters = int(np.sum(sel_metadata[:, 3] == 1))
        n_cc_clusters = int(np.sum(sel_metadata[:, 3] == 0))
        
        if verbose:
            print(f"ES clusters: {n_es_clusters}, CC clusters: {n_cc_clusters}")
        
        # Save results and return early (no MCMC)
        results = {
            f'{scenario}_reco_direction': reco_direction,
            f'{scenario}_angular_error_deg': angular_error_deg,
            f'{scenario}_cos_theta': cos_theta,
            f'{scenario}_n_clusters_used': len(energies),
            f'{scenario}_avg_energy': float(np.mean(energies)),
            'n_es_clusters': n_es_clusters,
            'n_cc_clusters': n_cc_clusters,
            'total_clusters': len(energies),
            'chain': None,
            'log_prob': None
        }
        
        return results
    

    else:
        raise ValueError(f"Unknown scenario: {scenario}")
if len(energies) == 0:
        raise ValueError(f"No clusters remaining for scenario {scenario}")
    
    # Run emcee MCMC (weights can be None for unweighted scenarios)
    if ct_weights is not None and verbose:
        print(f"Running weighted MCMC with {len(ct_weights)} weights")
    
    mcmc_result = run_emcee_mcmc(
        pred_x, pred_y, pred_z, energies, pdf_interpolator,
        nwalkers=nwalkers, nsteps=nsteps, discard=discard, 
        weights=ct_weights, verbose=verbose
    )
    
    # Convert best-fit to Cartesian
    theta = mcmc_result['theta']
    phi = mcmc_result['phi']
    
    best_x = np.sin(theta) * np.cos(phi)
    best_y = np.sin(theta) * np.sin(phi)
    best_z = np.cos(theta)
    
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
        'emcee_n_es_clusters': int(np.sum(sel_metadata[:, 3] == 1)),
        'emcee_n_cc_clusters': int(np.sum(sel_metadata[:, 3] == 0)),
        'emcee_true_nu_px': true_nu_px,
        'emcee_true_nu_py': true_nu_py,
        'emcee_true_nu_pz': true_nu_pz
    }


def main():
    parser = argparse.ArgumentParser(description='EMCEE-based supernova reconstruction with 6 scenarios')
    parser.add_argument('--cat-name', required=True, help='Cat name (e.g., cat000001)')
    parser.add_argument('--cat-dir', required=True, help='Cat directory')
    parser.add_argument('--ed-model', required=True, help='ED model path')
    parser.add_argument('--ct-model', default=None, help='CT model path (required for full_pipeline, weighted_ct)')
    parser.add_argument('--pdf-file', required=True, help='PDF file path')
    parser.add_argument('--scenarios', nargs='+', 
                        default=['best_case', 'perfect_ct', 'full_pipeline'], 
                        help='Scenarios: best_case, perfect_ct, full_pipeline, weighted_ct, perfect_ct_e_gt_10mev, perfect_ct_e_gt_5mev, simple_average, weighted_average, simple_average_ct')
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
                args.cat_dir, args.cat_name, scenario, args.ed_model, args.ct_model, pdf_interpolator,
                nwalkers=args.nwalkers, nsteps=args.nsteps, discard=args.discard, verbose=True
            )
        except Exception as e:
            print(f"\n✗ {scenario} failed: {e}")
            import traceback
            traceback.print_exc()
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
