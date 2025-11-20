#!/usr/bin/env python3
"""
Complete 3-scenario analysis for cat000001 SN pointing performance.

Scenario 1: Best Case - Uses TRUE electron directions (from particle momentum)
Scenario 2: Perfect CT - Uses only ES main tracks with ED neural network
Scenario 3: Full Pipeline - Uses CT to select ES, then ED, then MCMC

All scenarios use:
- ALL files from cat000001 (not just one file per plane)
- MCMC for direction reconstruction
- True neutrino direction for comparison (metadata indices 15-17)
"""

import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import argparse
import json
import numpy as np
from pathlib import Path
import sys
from scipy.interpolate import RegularGridInterpolator
import tensorflow as tf

sys.path.insert(0, str(Path(__file__).parent.parent))

# ============================================================================
# DATA LOADING
# ============================================================================

def load_all_cluster_images(cat_dir, cat_name, plane='X'):
    """Load ALL cluster images from a category for one plane."""
    cluster_dir = Path(cat_dir) / f"{cat_name}_cluster_images_tick3_ch2_min2_tot3_e3p0" / plane
    
    if not cluster_dir.exists():
        raise FileNotFoundError(f"Cluster directory not found: {cluster_dir}")
    
    images_list = []
    metadata_list = []
    
    for npz_file in sorted(cluster_dir.glob('*.npz')):
        try:
            data = np.load(npz_file)
            images_list.append(data['images'])
            metadata_list.append(data['metadata'])
        except Exception as e:
            print(f"Warning: Could not load {npz_file}: {e}")
            continue
    
    if not images_list:
        raise ValueError(f"No cluster images loaded from {cluster_dir}")
    
    images = np.concatenate(images_list)
    metadata = np.concatenate(metadata_list)
    
    return images, metadata


def load_all_volume_images(cat_dir, cat_name, plane='X'):
    """Load ALL volume images from a category for one plane."""
    volume_dir = Path(cat_dir) / f"{cat_name}_volume_images_tick3_ch2_min2_tot3_e3p0" / plane
    
    if not volume_dir.exists():
        raise FileNotFoundError(f"Volume directory not found: {volume_dir}")
    
    images_list = []
    metadata_list = []
    
    for npz_file in sorted(volume_dir.glob('*.npz')):
        try:
            data = np.load(npz_file, allow_pickle=True)
            images_list.append(data['images'])
            metadata_list.append(data['metadata'])
        except Exception as e:
            print(f"Warning: Could not load {npz_file}: {e}")
            continue
    
    if not images_list:
        raise ValueError(f"No volume images loaded from {volume_dir}")
    
    images = np.concatenate(images_list).astype(np.float32)
    metadata = np.concatenate(metadata_list)
    
    return images, metadata


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
            print(f"Warning: Missing U or V plane for {filename}, skipping")
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


# ============================================================================
# MCMC FUNCTIONS
# ============================================================================

def compute_log_likelihood(direction, cluster_directions, cluster_energies, pdf_interpolator, weights=None):
    """Compute log-likelihood for MCMC with optional per-cluster weights."""
    direction = direction / np.linalg.norm(direction)
    
    cosines = np.sum(cluster_directions * direction, axis=1)
    cosines = np.clip(cosines, -1.0, 1.0)
    
    points = np.column_stack([cluster_energies, cosines])
    probs = pdf_interpolator(points)
    probs = np.maximum(probs, 1e-10)
    
    log_probs = np.log(probs)
    
    # Apply weights if provided (default is uniform weights of 1)
    if weights is not None:
        log_like = np.sum(weights * log_probs)
    else:
        log_like = np.sum(log_probs)
    
    return log_like


def run_mcmc_optimization(cluster_directions, cluster_energies, pdf_interpolator, 
                          n_trials=50, n_steps=1000, proposal_scale=0.1, weights=None, verbose=False):
    """
    Run MCMC optimization with single long chain from best of multiple random starts.
    Supports optional per-cluster weights.
    Returns best direction and full chain statistics.
    """
    best_direction = None
    best_log_like = -np.inf
    best_init_trial = 0
    trial_results = []
    
    # Phase 1: Try multiple random initializations with short burns
    for trial in range(n_trials):
        # Random initial direction
        theta = np.random.uniform(0, np.pi)
        phi = np.random.uniform(0, 2*np.pi)
        init_dir = np.array([
            np.sin(theta) * np.cos(phi),
            np.sin(theta) * np.sin(phi),
            np.cos(theta)
        ])
        
        current_dir = init_dir.copy()
        current_log_like = compute_log_likelihood(
            current_dir, cluster_directions, cluster_energies, pdf_interpolator, weights
        )
        
        # Short burn-in to find local maximum
        for step in range(100):
            proposal = current_dir + np.random.normal(0, proposal_scale, 3)
            proposal = proposal / np.linalg.norm(proposal)
            
            proposal_log_like = compute_log_likelihood(
                proposal, cluster_directions, cluster_energies, pdf_interpolator, weights
            )
            
            if proposal_log_like > current_log_like:
                current_dir = proposal
                current_log_like = proposal_log_like
            else:
                accept_prob = np.exp(proposal_log_like - current_log_like)
                if np.random.rand() < accept_prob:
                    current_dir = proposal
                    current_log_like = proposal_log_like
        
        trial_results.append((current_dir, current_log_like))
        
        if current_log_like > best_log_like:
            best_log_like = current_log_like
            best_direction = current_dir
            best_init_trial = trial
    
    # Phase 2: Run full MCMC chain from best initialization
    current_dir = best_direction.copy()
    current_log_like = best_log_like
    
    chain_directions = [current_dir]
    chain_log_likes = [current_log_like]
    
    # Adaptive proposal scale with damping
    accept_count = 0
    check_interval = 100
    initial_proposal_scale = proposal_scale
    total_steps = n_steps * 10
    
    for step in range(total_steps):  # Longer chain for better convergence
        # Apply damping: reduce step size over time using exponential decay
        # This helps convergence by making smaller moves as we approach optimum
        damping_factor = np.exp(-step / (total_steps * 0.5))  # Decay over half the chain
        damped_scale = proposal_scale * (0.3 + 0.7 * damping_factor)  # Keep minimum 30% of scale
        
        proposal = current_dir + np.random.normal(0, damped_scale, 3)
        proposal = proposal / np.linalg.norm(proposal)
        
        proposal_log_like = compute_log_likelihood(
            proposal, cluster_directions, cluster_energies, pdf_interpolator, weights
        )
        
        if proposal_log_like > current_log_like:
            current_dir = proposal
            current_log_like = proposal_log_like
            accept_count += 1
        else:
            accept_prob = np.exp(proposal_log_like - current_log_like)
            if np.random.rand() < accept_prob:
                current_dir = proposal
                current_log_like = proposal_log_like
                accept_count += 1
        
        chain_directions.append(current_dir)
        chain_log_likes.append(current_log_like)
        
        # Adapt base proposal scale every check_interval steps based on acceptance rate
        if (step + 1) % check_interval == 0:
            accept_rate = accept_count / check_interval
            if accept_rate < 0.2:
                proposal_scale *= 0.9
            elif accept_rate > 0.5:
                proposal_scale *= 1.1
            accept_count = 0
        
        if current_log_like > best_log_like:
            best_log_like = current_log_like
            best_direction = current_dir
    
    if verbose:
        print(f"  MCMC: {n_trials} initial trials, then {len(chain_log_likes)} chain steps")
        print(f"  Best log-likelihood: {best_log_like:.2f}, final proposal_scale: {proposal_scale:.4f}")
    
    # Return chain for visualization
    return best_direction, best_log_like, np.array(chain_directions), np.array(chain_log_likes)


def compute_angular_resolution(reconstructed_dir, true_dir):
    """Compute angle between reconstructed and true direction in degrees."""
    reconstructed_dir = reconstructed_dir / np.linalg.norm(reconstructed_dir)
    true_dir = true_dir / np.linalg.norm(true_dir)
    
    cos_angle = np.clip(np.dot(reconstructed_dir, true_dir), -1.0, 1.0)
    angle_deg = np.rad2deg(np.arccos(cos_angle))
    
    return angle_deg


# ============================================================================
# SCENARIO 1: BEST CASE (TRUE ELECTRON DIRECTIONS)
# ============================================================================

def run_scenario1_best_case(cat_dir, cat_name, pdf_interpolator, verbose=True):
    """
    Scenario 1: Use TRUE electron directions from main tracks.
    This gives the best possible performance (physics limit).
    """
    if verbose:
        print("\n" + "="*70)
        print("SCENARIO 1: BEST CASE (True Electron Directions)")
        print("="*70)
    
    # Event loss tracking
    event_losses = {}
    
    # Load all cluster images
    images, metadata = load_all_cluster_images(cat_dir, cat_name, plane='X')
    event_losses['total_clusters'] = len(images)
    
    if verbose:
        print(f"\nLoaded {len(images)} total clusters")
    
    # Filter for ES main tracks only (is_main_track==1 AND is_es_interaction==1)
    is_main_track = metadata[:, 2] == 1
    is_es = metadata[:, 3] == 1
    es_main_mask = is_main_track & is_es
    main_track_metadata = metadata[es_main_mask]
    
    event_losses['not_main_track'] = (~is_main_track).sum()
    event_losses['not_es'] = (~is_es).sum()
    event_losses['es_main_tracks'] = len(main_track_metadata)
    
    if verbose:
        print(f"ES main tracks: {len(main_track_metadata)}")
    
    # Extract true electron directions (particle momentum, columns 7-9 in GeV/c)
    # Note: momentum is stored in GeV/c, already as direction components
    px = main_track_metadata[:, 7]
    py = main_track_metadata[:, 8]
    pz = main_track_metadata[:, 9]
    
    # Normalize to get unit direction vectors
    norms = np.sqrt(px**2 + py**2 + pz**2)
    valid = norms > 0
    
    event_losses['invalid_directions'] = (~valid).sum()
    
    if verbose:
        print(f"Valid directions: {valid.sum()} / {len(valid)}")
    
    electron_directions = np.column_stack([
        px[valid] / norms[valid],
        py[valid] / norms[valid],
        pz[valid] / norms[valid]
    ])
    
    # Filter to only valid directions
    main_track_metadata = main_track_metadata[valid]
    
    # Extract energies (column 11)
    energies = main_track_metadata[:, 11]
    
    # Apply 3 MeV energy cut
    energy_cut = energies >= 3.0
    event_losses['below_3mev'] = (~energy_cut).sum()
    electron_directions = electron_directions[energy_cut]
    energies = energies[energy_cut]
    main_track_metadata = main_track_metadata[energy_cut]
    event_losses['after_energy_cut'] = len(energies)
    
    if verbose:
        print(f"After 3 MeV cut: {len(energies)} clusters")
    
    # Extract true neutrino direction (columns 15-17)
    nu_px = main_track_metadata[:, 15]
    nu_py = main_track_metadata[:, 16]
    nu_pz = main_track_metadata[:, 17]
    
    nu_norms = np.sqrt(nu_px**2 + nu_py**2 + nu_pz**2)
    nu_valid = nu_norms > 0
    
    # Use the most common neutrino direction (should be same for all in burst)
    if nu_valid.sum() > 0:
        true_nu_dir = np.array([
            np.mean(nu_px[nu_valid] / nu_norms[nu_valid]),
            np.mean(nu_py[nu_valid] / nu_norms[nu_valid]),
            np.mean(nu_pz[nu_valid] / nu_norms[nu_valid])
        ])
        true_nu_dir = true_nu_dir / np.linalg.norm(true_nu_dir)
    else:
        raise ValueError("No valid neutrino directions found")
    
    if verbose:
        print(f"\nTrue neutrino direction: [{true_nu_dir[0]:.4f}, {true_nu_dir[1]:.4f}, {true_nu_dir[2]:.4f}]")
        print(f"Using {len(electron_directions)} electron directions for MCMC")
    
    # Run MCMC
    reconstructed_dir, log_like, all_dirs, all_likes = run_mcmc_optimization(
        electron_directions, energies, pdf_interpolator,
        n_trials=50, verbose=verbose
    )
    
    # Compute angular resolution
    angle_error = compute_angular_resolution(reconstructed_dir, true_nu_dir)
    
    if verbose:
        print(f"\nReconstructed direction: [{reconstructed_dir[0]:.4f}, {reconstructed_dir[1]:.4f}, {reconstructed_dir[2]:.4f}]")
        print(f"Angular error: {angle_error:.2f}°")
    
    # Compute cos(theta) for 68% quantile calculation
    cos_theta = np.dot(reconstructed_dir, true_nu_dir)
    
    return {
        'scenario': 'best_case',
        'n_clusters_used': len(electron_directions),
        'true_nu_direction': true_nu_dir,
        'reconstructed_direction': reconstructed_dir,
        'angular_error_deg': angle_error,
        'log_likelihood': log_like,
        'cos_theta': cos_theta,
        'mcmc_chain': all_dirs,
        'mcmc_log_likelihoods': all_likes,
        'all_trial_directions': all_dirs,
        'all_trial_log_likes': all_likes,
        'event_losses': event_losses
    }


# ============================================================================
# SCENARIO 2: PERFECT CT (ES MAIN TRACKS + ED NETWORK)
# ============================================================================

def run_scenario2_perfect_ct(cat_dir, cat_name, ed_model_path, pdf_interpolator, verbose=True, save_intermediate=False):
    """
    Scenario 2: Use only ES main tracks (perfect channel tagging).
    Feed cluster images to ED neural network to get electron directions.
    """
    if verbose:
        print("\n" + "="*70)
        print("SCENARIO 2: PERFECT CT (ES Main Tracks + ED Network)")
        print("="*70)
    
    intermediate_data = {}
    event_losses = {}
    
    # Check ES file count
    cluster_dir_base = Path(cat_dir) / f"{cat_name}_cluster_images_tick3_ch2_min2_tot3_e3p0"
    cluster_dir_x = cluster_dir_base / 'X'
    if cluster_dir_x.exists():
        es_files = list(cluster_dir_x.glob('es_*.npz'))
        cc_files = list(cluster_dir_x.glob('cc_*.npz'))
        event_losses['n_es_files'] = len(es_files)
        event_losses['n_cc_files'] = len(cc_files)
        if verbose:
            print(f"\nFiles found: {len(es_files)} ES, {len(cc_files)} CC")
    
    # Load matched cluster images across all 3 planes
    images_u, images_v, images_x, metadata = load_matched_cluster_images_3plane(cat_dir, cat_name)
    event_losses['total_main_tracks_3plane'] = len(images_x)
    
    if verbose:
        print(f"\nLoaded {len(images_x)} matched main-track clusters across U, V, X planes")
    
    # Filter for ES interactions only
    is_es = metadata[:, 3] == 1
    
    es_images_u = images_u[is_es]
    es_images_v = images_v[is_es]
    es_images_x = images_x[is_es]
    es_metadata = metadata[is_es]
    
    event_losses['not_es'] = (~is_es).sum()
    event_losses['es_main_tracks'] = is_es.sum()
    
    if verbose:
        print(f"ES main tracks: {is_es.sum()} (expected ~400 from 10 ES files × 40 events)")
        print(f"  Matched main tracks across all planes: {len(metadata)}")
        print(f"  ES main tracks: {is_es.sum()}")
    
    if is_es.sum() == 0:
        raise ValueError("No ES main tracks found")
    
    # Load ED model
    if verbose:
        print(f"\nLoading ED model from: {ed_model_path}")
    
    ed_model = tf.keras.models.load_model(ed_model_path, compile=False)
    
    if verbose:
        print(f"ED model input shape: {ed_model.input_shape}")
        print(f"ED model output shape: {ed_model.output_shape}")
    
    # Prepare images for ED model: 3 inputs (U, V, X) with channel dimension
    es_images_u_input = es_images_u[..., np.newaxis]
    es_images_v_input = es_images_v[..., np.newaxis]
    es_images_x_input = es_images_x[..., np.newaxis]
    
    # Run ED inference
    if verbose:
        print(f"\nRunning ED inference on {len(es_images_x_input)} clusters...")
    
    ed_predictions = ed_model.predict([es_images_u_input, es_images_v_input, es_images_x_input], 
                                     batch_size=32, verbose=0)
    
    if verbose:
        print(f"ED predictions shape: {ed_predictions.shape}")
    
    # Extract electron directions from ED predictions
    # Assuming ED output is direction vectors (x, y, z) or needs processing
    # TODO: Verify exact output format of ED model
    if ed_predictions.shape[1] == 3:
        # Direct direction vectors
        electron_directions = ed_predictions
    else:
        # May be angle-based or other format - needs adaptation
        raise NotImplementedError(f"ED output shape {ed_predictions.shape} not yet handled")
    
    # Normalize directions
    norms = np.linalg.norm(electron_directions, axis=1, keepdims=True)
    electron_directions = electron_directions / (norms + 1e-10)
    
    # Extract energies and true neutrino direction
    energies = es_metadata[:, 11]  # Column 11: true_particle_energy
    
    # Apply 3 MeV energy cut
    energy_cut = energies >= 3.0
    event_losses['below_3mev'] = (~energy_cut).sum()
    electron_directions = electron_directions[energy_cut]
    energies = energies[energy_cut]
    es_metadata = es_metadata[energy_cut]
    event_losses['after_energy_cut'] = len(energies)
    
    if verbose:
        print(f"After 3 MeV cut: {len(energies)} clusters")
    
    nu_px = es_metadata[:, 15]
    nu_py = es_metadata[:, 16]
    nu_pz = es_metadata[:, 17]
    
    nu_norms = np.sqrt(nu_px**2 + nu_py**2 + nu_pz**2)
    nu_valid = nu_norms > 0
    
    if nu_valid.sum() > 0:
        true_nu_dir = np.array([
            np.mean(nu_px[nu_valid] / nu_norms[nu_valid]),
            np.mean(nu_py[nu_valid] / nu_norms[nu_valid]),
            np.mean(nu_pz[nu_valid] / nu_norms[nu_valid])
        ])
        true_nu_dir = true_nu_dir / np.linalg.norm(true_nu_dir)
    else:
        raise ValueError("No valid neutrino directions found")
    
    if verbose:
        print(f"\nTrue neutrino direction: [{true_nu_dir[0]:.4f}, {true_nu_dir[1]:.4f}, {true_nu_dir[2]:.4f}]")
        print(f"Using {len(electron_directions)} ED-predicted directions for MCMC")
    
    # Run MCMC
    reconstructed_dir, log_like, all_dirs, all_likes = run_mcmc_optimization(
        electron_directions, energies, pdf_interpolator,
        n_trials=50, verbose=verbose
    )
    
    # Compute angular resolution
    angle_error = compute_angular_resolution(reconstructed_dir, true_nu_dir)
    
    # Compute cos(theta) for 68% quantile calculation
    cos_theta = np.dot(reconstructed_dir, true_nu_dir)
    
    if verbose:
        print(f"\nReconstructed direction: [{reconstructed_dir[0]:.4f}, {reconstructed_dir[1]:.4f}, {reconstructed_dir[2]:.4f}]")
        print(f"Angular error: {angle_error:.2f}°")
    
    return {
        'scenario': 'perfect_ct',
        'n_es_main_tracks': event_losses.get('es_main_tracks', 0),
        'n_clusters_used': len(electron_directions),
        'true_nu_direction': true_nu_dir,
        'reconstructed_direction': reconstructed_dir,
        'angular_error_deg': angle_error,
        'log_likelihood': log_like,
        'cos_theta': cos_theta,
        'mcmc_chain': all_dirs,
        'mcmc_log_likelihoods': all_likes,
        'all_trial_directions': all_dirs,
        'all_trial_log_likes': all_likes,
        'event_losses': event_losses
    }


# ============================================================================
# SCENARIO 7: PERFECT CT + ED, E > 10 MeV
# ============================================================================

def run_scenario7_e_gt_10mev(cat_dir, cat_name, ed_model_path, pdf_interpolator, verbose=True):
    """
    Scenario 7: Perfect channel tagging (ES main tracks only) + ED network.
    Apply energy cut: E > 10 MeV.
    """
    if verbose:
        print("\n" + "="*70)
        print("SCENARIO 7: PERFECT CT + ED, E > 10 MeV")
        print("="*70)
    
    # Load ES main track cluster images (same as scenario 2)
    images_u, images_v, images_x, metadata = load_matched_cluster_images_3plane(cat_dir, cat_name)
    
    # Filter for ES main tracks only
    is_es = metadata[:, 3] == 1
    es_images_u = images_u[is_es]
    es_images_v = images_v[is_es]
    es_images_x = images_x[is_es]
    es_metadata = metadata[is_es]
    
    if verbose:
        print(f"\nLoaded {len(es_images_x)} ES main track clusters")
    
    # Apply 10 MeV energy cut
    energies = es_metadata[:, 11]  # Column 11: true_particle_energy
    energy_cut = energies >= 10.0
    
    es_images_u = es_images_u[energy_cut]
    es_images_v = es_images_v[energy_cut]
    es_images_x = es_images_x[energy_cut]
    es_metadata = es_metadata[energy_cut]
    energies = energies[energy_cut]
    
    if verbose:
        print(f"After E > 10 MeV cut: {len(es_images_x)} clusters")
    
    if len(es_images_x) == 0:
        raise ValueError("No ES main tracks remaining after 10 MeV cut")
    
    # Load ED model and predict
    if verbose:
        print(f"\nLoading ED model from: {ed_model_path}")
    ed_model = tf.keras.models.load_model(ed_model_path, compile=False)
    
    es_images_u_input = es_images_u[..., np.newaxis]
    es_images_v_input = es_images_v[..., np.newaxis]
    es_images_x_input = es_images_x[..., np.newaxis]
    
    if verbose:
        print(f"Running ED inference...")
    ed_predictions = ed_model.predict([es_images_u_input, es_images_v_input, es_images_x_input], 
                                     batch_size=32, verbose=0)
    
    electron_directions = ed_predictions / np.linalg.norm(ed_predictions, axis=1, keepdims=True)
    
    # Get true neutrino direction
    true_nu_dir = es_metadata[0, 15:18]
    true_nu_dir = true_nu_dir / np.linalg.norm(true_nu_dir)
    
    if verbose:
        print(f"\nTrue neutrino direction: [{true_nu_dir[0]:.4f}, {true_nu_dir[1]:.4f}, {true_nu_dir[2]:.4f}]")
        print(f"Using {len(electron_directions)} electron directions for MCMC")
    
    # Run MCMC
    reconstructed_dir, log_like, all_dirs, all_likes = run_mcmc_optimization(
        electron_directions, energies, pdf_interpolator, n_trials=50, verbose=verbose
    )
    
    # Compute metrics
    angle_error = compute_angular_resolution(reconstructed_dir, true_nu_dir)
    cos_theta = np.dot(reconstructed_dir, true_nu_dir)
    
    if verbose:
        print(f"\nReconstructed direction: [{reconstructed_dir[0]:.4f}, {reconstructed_dir[1]:.4f}, {reconstructed_dir[2]:.4f}]")
        print(f"Angular error: {angle_error:.2f}°")
    
    return {
        'scenario': 'perfect_ct_e_gt_10mev',
        'n_es_main_tracks_total': int(energy_cut.sum() + (~energy_cut).sum()),
        'n_clusters_used': len(electron_directions),
        'energy_cut_mev': 10.0,
        'true_nu_direction': true_nu_dir,
        'reconstructed_direction': reconstructed_dir,
        'angular_error_deg': angle_error,
        'log_likelihood': log_like,
        'cos_theta': cos_theta,
        'mcmc_chain': all_dirs,
        'mcmc_log_likelihoods': all_likes,
        'all_trial_directions': all_dirs,
        'all_trial_log_likes': all_likes
    }


# ============================================================================
# SCENARIO 8: PERFECT CT + ED, E > 20 MeV
# ============================================================================

def run_scenario8_e_gt_20mev(cat_dir, cat_name, ed_model_path, pdf_interpolator, verbose=True):
    """
    Scenario 8: Perfect channel tagging (ES main tracks only) + ED network.
    Apply energy cut: E > 20 MeV.
    """
    if verbose:
        print("\n" + "="*70)
        print("SCENARIO 8: PERFECT CT + ED, E > 20 MeV")
        print("="*70)
    
    # Load ES main track cluster images
    images_u, images_v, images_x, metadata = load_matched_cluster_images_3plane(cat_dir, cat_name)
    
    # Filter for ES main tracks only
    is_es = metadata[:, 3] == 1
    es_images_u = images_u[is_es]
    es_images_v = images_v[is_es]
    es_images_x = images_x[is_es]
    es_metadata = metadata[is_es]
    
    if verbose:
        print(f"\nLoaded {len(es_images_x)} ES main track clusters")
    
    # Apply 20 MeV energy cut
    energies = es_metadata[:, 11]  # Column 11: true_particle_energy
    energy_cut = energies >= 20.0
    
    es_images_u = es_images_u[energy_cut]
    es_images_v = es_images_v[energy_cut]
    es_images_x = es_images_x[energy_cut]
    es_metadata = es_metadata[energy_cut]
    energies = energies[energy_cut]
    
    if verbose:
        print(f"After E > 20 MeV cut: {len(es_images_x)} clusters")
    
    if len(es_images_x) == 0:
        raise ValueError("No ES main tracks remaining after 20 MeV cut")
    
    # Load ED model and predict
    if verbose:
        print(f"\nLoading ED model from: {ed_model_path}")
    ed_model = tf.keras.models.load_model(ed_model_path, compile=False)
    
    es_images_u_input = es_images_u[..., np.newaxis]
    es_images_v_input = es_images_v[..., np.newaxis]
    es_images_x_input = es_images_x[..., np.newaxis]
    
    if verbose:
        print(f"Running ED inference...")
    ed_predictions = ed_model.predict([es_images_u_input, es_images_v_input, es_images_x_input], 
                                     batch_size=32, verbose=0)
    
    electron_directions = ed_predictions / np.linalg.norm(ed_predictions, axis=1, keepdims=True)
    
    # Get true neutrino direction
    true_nu_dir = es_metadata[0, 15:18]
    true_nu_dir = true_nu_dir / np.linalg.norm(true_nu_dir)
    
    if verbose:
        print(f"\nTrue neutrino direction: [{true_nu_dir[0]:.4f}, {true_nu_dir[1]:.4f}, {true_nu_dir[2]:.4f}]")
        print(f"Using {len(electron_directions)} electron directions for MCMC")
    
    # Run MCMC
    reconstructed_dir, log_like, all_dirs, all_likes = run_mcmc_optimization(
        electron_directions, energies, pdf_interpolator, n_trials=50, verbose=verbose
    )
    
    # Compute metrics
    angle_error = compute_angular_resolution(reconstructed_dir, true_nu_dir)
    cos_theta = np.dot(reconstructed_dir, true_nu_dir)
    
    if verbose:
        print(f"\nReconstructed direction: [{reconstructed_dir[0]:.4f}, {reconstructed_dir[1]:.4f}, {reconstructed_dir[2]:.4f}]")
        print(f"Angular error: {angle_error:.2f}°")
    
    return {
        'scenario': 'perfect_ct_e_gt_20mev',
        'n_es_main_tracks_total': int(energy_cut.sum() + (~energy_cut).sum()),
        'n_clusters_used': len(electron_directions),
        'energy_cut_mev': 20.0,
        'true_nu_direction': true_nu_dir,
        'reconstructed_direction': reconstructed_dir,
        'angular_error_deg': angle_error,
        'log_likelihood': log_like,
        'cos_theta': cos_theta,
        'mcmc_chain': all_dirs,
        'mcmc_log_likelihoods': all_likes,
        'all_trial_directions': all_dirs,
        'all_trial_log_likes': all_likes
    }


# ============================================================================
# SCENARIO 3: FULL PIPELINE (CT → ED → MCMC)
# ============================================================================

def run_scenario3_full_pipeline(cat_dir, cat_name, ct_model_path, ed_model_path, 
                                 pdf_interpolator, ct_threshold=0.5, weight_power=0, verbose=True):
    """
    Scenario 3/4/5: Full realistic pipeline with optional CT probability weighting.
    1. Load all main track volumes
    2. Run CT to select ES candidates
    3. Run ED on selected clusters
    4. Run MCMC on ED directions with optional CT weights
    
    Args:
        weight_power: 0 = no weights (scenario 3)
                     1 = linear CT weights (scenario 4)
                     2 = squared CT weights (scenario 5)
    """
    if verbose:
        print("\n" + "="*70)
        print("SCENARIO 3: FULL PIPELINE (CT → ED → MCMC)")
        print("="*70)
    
    # Load all volume images (needed for CT)
    volume_images, volume_metadata = load_all_volume_images(cat_dir, cat_name, plane='X')
    
    if verbose:
        print(f"\nLoaded {len(volume_images)} volumes")
    
    # Load CT model
    if verbose:
        print(f"\nLoading CT model from: {ct_model_path}")
    
    ct_model = tf.keras.models.load_model(ct_model_path, compile=False)
    
    if verbose:
        print(f"CT model input shape: {ct_model.input_shape}")
        print(f"CT model output shape: {ct_model.output_shape}")
    
    # Prepare volumes for CT model
    # Ensure correct shape and dtype
    if len(volume_images.shape) == 3:
        volume_images_input = volume_images[..., np.newaxis]
    else:
        volume_images_input = volume_images
    
    volume_images_input = volume_images_input.astype(np.float32)
    
    # Run CT inference
    if verbose:
        print(f"\nRunning CT inference...")
        print(f"Volume input shape: {volume_images_input.shape}, dtype: {volume_images_input.dtype}")
    
    ct_predictions = ct_model.predict(volume_images_input, batch_size=16, verbose=0)
    
    # CT model outputs [N, 2] with softmax: [P(ES), P(CC)]
    # Get ES probability (first column)
    if ct_predictions.shape[1] == 2:
        es_probs = ct_predictions[:, 0]  # P(ES)
    else:
        es_probs = ct_predictions.flatten()
    
    # Select ES candidates (ES prob > threshold)
    es_candidates = es_probs > ct_threshold
    
    # Store ES probabilities for weighting
    selected_es_probs = es_probs[es_candidates]
    
    if verbose:
        print(f"CT selected {es_candidates.sum()} ES candidates from {len(es_probs)} volumes")
        print(f"  True ES volumes: {sum([m['interaction_type'] == 'ES' for m in volume_metadata])}")
        print(f"  ES prob range: [{es_probs.min():.3f}, {es_probs.max():.3f}]")
    
    # Load corresponding cluster images for selected volumes
    # Need to match volumes to clusters - use event IDs
    selected_volume_metadata = volume_metadata[es_candidates]
    selected_events = set([m['event'] for m in selected_volume_metadata])
    
    # Create event->prob mapping for weights
    event_to_prob = {m['event']: prob for m, prob in zip(selected_volume_metadata, selected_es_probs)}
    
    # Load matched 3-plane cluster images
    images_u, images_v, images_x, cluster_metadata = load_matched_cluster_images_3plane(cat_dir, cat_name)
    
    # Filter clusters to match selected events
    cluster_events = cluster_metadata[:, 0].astype(int)
    selected_mask = np.array([e in selected_events for e in cluster_events])
    
    selected_images_u = images_u[selected_mask]
    selected_images_v = images_v[selected_mask]
    selected_images_x = images_x[selected_mask]
    selected_metadata = cluster_metadata[selected_mask]
    
    if verbose:
        print(f"\nMatched {len(selected_images_u)} 3-plane clusters for ED inference")
    
    if len(selected_images_u) == 0:
        raise ValueError("No clusters matched CT selection")
    
    # Load ED model and run inference
    if verbose:
        print(f"\nLoading ED model from: {ed_model_path}")
    
    ed_model = tf.keras.models.load_model(ed_model_path, compile=False)
    
    # Prepare 3-plane images for ED model
    images_u_input = selected_images_u[..., np.newaxis] if len(selected_images_u.shape) == 3 else selected_images_u
    images_v_input = selected_images_v[..., np.newaxis] if len(selected_images_v.shape) == 3 else selected_images_v
    images_x_input = selected_images_x[..., np.newaxis] if len(selected_images_x.shape) == 3 else selected_images_x
    
    if verbose:
        print(f"Running ED inference on {len(images_u_input)} clusters...")
    
    ed_predictions = ed_model.predict([images_u_input, images_v_input, images_x_input], batch_size=32, verbose=0)
    
    # Extract directions (same as scenario 2)
    if ed_predictions.shape[1] == 3:
        electron_directions = ed_predictions
    else:
        raise NotImplementedError(f"ED output shape {ed_predictions.shape} not yet handled")
    
    norms = np.linalg.norm(electron_directions, axis=1, keepdims=True)
    electron_directions = electron_directions / (norms + 1e-10)
    
    # Extract energies and true neutrino direction
    energies = selected_metadata[:, 11]
    
    # Apply 3 MeV energy cut
    energy_cut = energies >= 3.0
    electron_directions = electron_directions[energy_cut]
    energies = energies[energy_cut]
    selected_metadata = selected_metadata[energy_cut]
    
    # Create CT weights based on ES probabilities
    cluster_events_after_cut = selected_metadata[:, 0].astype(int)
    ct_weights = np.array([event_to_prob.get(e, 1.0) for e in cluster_events_after_cut])
    
    # Apply weight power: 0=no weights, 1=linear, 2=squared
    if weight_power == 0:
        ct_weights = None  # Uniform weights (all 1.0)
    elif weight_power == 1:
        pass  # Use probabilities as-is
    elif weight_power == 2:
        ct_weights = ct_weights ** 2  # Squared weights
    else:
        raise ValueError(f"weight_power must be 0, 1, or 2, got {weight_power}")
    
    if verbose:
        print(f"After 3 MeV cut: {len(energies)} clusters")
        if ct_weights is not None:
            print(f"Using CT weights^{weight_power}: range [{ct_weights.min():.3f}, {ct_weights.max():.3f}]")
    
    nu_px = selected_metadata[:, 15]
    nu_py = selected_metadata[:, 16]
    nu_pz = selected_metadata[:, 17]
    
    nu_norms = np.sqrt(nu_px**2 + nu_py**2 + nu_pz**2)
    nu_valid = nu_norms > 0
    
    if nu_valid.sum() > 0:
        true_nu_dir = np.array([
            np.mean(nu_px[nu_valid] / nu_norms[nu_valid]),
            np.mean(nu_py[nu_valid] / nu_norms[nu_valid]),
            np.mean(nu_pz[nu_valid] / nu_norms[nu_valid])
        ])
        true_nu_dir = true_nu_dir / np.linalg.norm(true_nu_dir)
    else:
        raise ValueError("No valid neutrino directions found")
    
    if verbose:
        print(f"\nTrue neutrino direction: [{true_nu_dir[0]:.4f}, {true_nu_dir[1]:.4f}, {true_nu_dir[2]:.4f}]")
        print(f"Using {len(electron_directions)} ED-predicted directions for MCMC")
    
    # Run MCMC with optional weights
    reconstructed_dir, log_like, all_dirs, all_likes = run_mcmc_optimization(
        electron_directions, energies, pdf_interpolator,
        n_trials=50, weights=ct_weights, verbose=verbose
    )
    
    # Compute angular resolution
    angle_error = compute_angular_resolution(reconstructed_dir, true_nu_dir)
    
    if verbose:
        print(f"\nReconstructed direction: [{reconstructed_dir[0]:.4f}, {reconstructed_dir[1]:.4f}, {reconstructed_dir[2]:.4f}]")
        print(f"Angular error: {angle_error:.2f}°")
    
    # Determine scenario name based on weight_power
    if weight_power == 0:
        scenario_name = 'full_pipeline'
    elif weight_power == 1:
        scenario_name = 'weighted_linear'
    elif weight_power == 2:
        scenario_name = 'weighted_squared'
    else:
        scenario_name = f'weighted_pow{weight_power}'
    
    # Compute cos(theta) for 68% quantile calculation
    cos_theta = np.dot(reconstructed_dir, true_nu_dir)
    
    return {
        'scenario': scenario_name,
        'n_volumes_total': len(volume_images),
        'n_ct_selected': es_candidates.sum(),
        'n_clusters_used': len(electron_directions),
        'ct_threshold': ct_threshold,
        'weight_power': weight_power,
        'ct_weights_range': [np.min(ct_weights), np.max(ct_weights)] if ct_weights is not None else None,
        'true_nu_direction': true_nu_dir,
        'reconstructed_direction': reconstructed_dir,
        'angular_error_deg': angle_error,
        'log_likelihood': log_like,
        'cos_theta': cos_theta,
        'mcmc_chain': all_dirs,
        'mcmc_log_likelihoods': all_likes,
        'all_trial_directions': all_dirs,
        'all_trial_log_likes': all_likes
    }


# ============================================================================
# SCENARIO 6: NO PDF (Pure Direction Alignment)
# ============================================================================

def compute_log_likelihood_no_pdf(direction, cluster_directions, weights=None):
    """
    Compute log-likelihood without PDF - just maximize agreement with predicted directions.
    Uses sum of cosines (dot products) as the likelihood.
    """
    direction = direction / np.linalg.norm(direction)
    
    cosines = np.sum(cluster_directions * direction, axis=1)
    cosines = np.clip(cosines, -1.0, 1.0)
    
    # Use cosines directly as "likelihood" (higher cosine = better alignment)
    # Convert to log scale: log(1 + cos) to keep it positive
    log_probs = np.log(1.0 + cosines)  # Range: log(0) to log(2) = 0 to 0.693
    
    if weights is not None:
        log_like = np.sum(weights * log_probs)
    else:
        log_like = np.sum(log_probs)
    
    return log_like


def run_mcmc_optimization_no_pdf(cluster_directions, weights=None, 
                                  n_trials=50, n_steps=10000, proposal_scale=0.1, verbose=False):
    """Run MCMC without PDF - optimize purely on direction alignment."""
    best_direction = None
    best_log_like = -np.inf
    
    # Phase 1: Random initializations
    if verbose:
        print(f"  MCMC: {n_trials} initial trials, then {n_steps+1} chain steps")
    
    for trial in range(n_trials):
        trial_dir = np.random.randn(3)
        trial_dir = trial_dir / np.linalg.norm(trial_dir)
        
        log_like = compute_log_likelihood_no_pdf(trial_dir, cluster_directions, weights)
        
        if log_like > best_log_like:
            best_log_like = log_like
            best_direction = trial_dir.copy()
    
    # Phase 2: Long MCMC chain from best initialization
    current_dir = best_direction.copy()
    current_log_like = best_log_like
    
    # Store only every 10th sample to save memory
    chain_dirs = [current_dir.copy()]
    chain_log_likes = [current_log_like]
    
    acceptance_count = 0
    initial_proposal_scale = proposal_scale
    
    for step in range(n_steps):
        # Apply damping: reduce step size over time for convergence
        damping_factor = np.exp(-step / (n_steps * 0.5))  # Decay over half the chain
        damped_scale = proposal_scale * (0.3 + 0.7 * damping_factor)  # Keep minimum 30% of scale
        
        proposal = current_dir + np.random.randn(3) * damped_scale
        proposal = proposal / np.linalg.norm(proposal)
        
        proposal_log_like = compute_log_likelihood_no_pdf(proposal, cluster_directions, weights)
        
        log_alpha = proposal_log_like - current_log_like
        
        if np.log(np.random.rand()) < log_alpha:
            current_dir = proposal
            current_log_like = proposal_log_like
            acceptance_count += 1
        
        # Store only every 10th sample to reduce memory
        if step % 10 == 0:
            chain_dirs.append(current_dir.copy())
            chain_log_likes.append(current_log_like)
        
        # Adaptive base proposal scaling
        if step > 0 and step % 100 == 0:
            acceptance_rate = acceptance_count / 100
            if acceptance_rate < 0.2:
                proposal_scale *= 0.9
            elif acceptance_rate > 0.5:
                proposal_scale *= 1.1
            acceptance_count = 0
    
    if verbose:
        print(f"  Best log-likelihood: {current_log_like:.2f}, final proposal_scale: {proposal_scale:.4f}")
    
    return current_dir, current_log_like, np.array(chain_dirs), np.array(chain_log_likes)


def run_scenario6_no_pdf(cat_dir, cat_name, ct_model_path, ed_model_path, 
                         ct_threshold=0.5, weight_power=0, verbose=True, save_intermediate=False):
    """
    Scenario 6: Full pipeline WITHOUT PDF.
    Uses only direction alignment (cosines) without energy-dependent PDF.
    This tests whether the PDF actually helps or hurts performance.
    """
    if verbose:
        print("\n" + "="*70)
        print("SCENARIO 6: NO PDF (Pure Direction Alignment)")
        print("="*70)
    
    # Load volumes and get CT predictions (same as scenario 3)
    volume_images, volume_metadata = load_all_volume_images(cat_dir, cat_name, plane='X')
    
    if verbose:
        print(f"\nLoaded {len(volume_images)} volumes")
    
    # Load CT model
    if verbose:
        print(f"\nLoading CT model from: {ct_model_path}")
    ct_model = tf.keras.models.load_model(ct_model_path, compile=False)
    
    # Prepare volumes for CT model
    if len(volume_images.shape) == 3:
        volume_images_input = volume_images[..., np.newaxis]
    else:
        volume_images_input = volume_images
    volume_images_input = volume_images_input.astype(np.float32)
    
    # Get CT predictions
    ct_predictions = ct_model.predict(volume_images_input, batch_size=16, verbose=0)
    
    if ct_predictions.shape[1] == 2:
        es_probs = ct_predictions[:, 0]  # P(ES)
    else:
        es_probs = ct_predictions.flatten()
    
    es_candidates = es_probs > ct_threshold
    selected_es_probs = es_probs[es_candidates]
    
    if verbose:
        print(f"CT threshold: {ct_threshold}")
        print(f"ES candidates: {es_candidates.sum()} / {len(es_candidates)}")
    
    if es_candidates.sum() == 0:
        raise ValueError("No ES candidates found after CT")
    
    # Load cluster images for ES candidates
    cluster_images_es, cluster_metadata_es = load_matched_cluster_images_3plane(
        cat_dir, cat_name, volume_metadata[es_candidates]
    )
    
    if verbose:
        print(f"Loaded {len(cluster_images_es)} ES cluster images")
    
    # Apply 3 MeV energy cut
    energies = cluster_metadata_es[:, 2]
    energy_cut = energies >= 3.0
    
    cluster_images_filtered = cluster_images_es[energy_cut]
    cluster_metadata_filtered = cluster_metadata_es[energy_cut]
    energies = energies[energy_cut]
    es_probs_filtered = selected_es_probs[energy_cut]
    
    if verbose:
        print(f"After 3 MeV cut: {len(cluster_images_filtered)} clusters")
    
    if len(cluster_images_filtered) == 0:
        raise ValueError("No clusters remain after 3 MeV cut")
    
    # Load ED model and predict directions
    if verbose:
        print(f"\nLoading ED model from: {ed_model_path}")
    ed_model = tf.keras.models.load_model(ed_model_path, compile=False)
    
    ed_predictions = ed_model.predict(cluster_images_filtered, batch_size=32, verbose=0)
    electron_directions = ed_predictions / np.linalg.norm(ed_predictions, axis=1, keepdims=True)
    
    # Get true neutrino direction
    true_nu_dir = cluster_metadata_filtered[0, 15:18]
    true_nu_dir = true_nu_dir / np.linalg.norm(true_nu_dir)
    
    if verbose:
        print(f"\nTrue neutrino direction: [{true_nu_dir[0]:.4f}, {true_nu_dir[1]:.4f}, {true_nu_dir[2]:.4f}]")
        print(f"Using {len(electron_directions)} ED-predicted directions for MCMC (NO PDF)")
    
    # Prepare weights if needed
    ct_weights = None
    if weight_power > 0:
        ct_weights = np.power(es_probs_filtered, weight_power)
    
    # Run MCMC WITHOUT PDF
    reconstructed_dir, log_like, all_dirs, all_likes = run_mcmc_optimization_no_pdf(
        electron_directions, weights=ct_weights,
        n_trials=50, verbose=verbose
    )
    
    # Compute angular resolution
    angle_error = compute_angular_resolution(reconstructed_dir, true_nu_dir)
    cos_theta = np.dot(reconstructed_dir, true_nu_dir)
    
    if verbose:
        print(f"\nReconstructed direction: [{reconstructed_dir[0]:.4f}, {reconstructed_dir[1]:.4f}, {reconstructed_dir[2]:.4f}]")
        print(f"Angular error: {angle_error:.2f}°")
    
    # Determine scenario name
    if weight_power == 0:
        scenario_name = 'no_pdf'
    elif weight_power == 1:
        scenario_name = 'no_pdf_weighted_linear'
    elif weight_power == 2:
        scenario_name = 'no_pdf_weighted_squared'
    else:
        scenario_name = f'no_pdf_weighted_pow{weight_power}'
    
    return {
        'scenario': scenario_name,
        'n_volumes_total': len(volume_images),
        'n_ct_selected': es_candidates.sum(),
        'n_clusters_used': len(electron_directions),
        'ct_threshold': ct_threshold,
        'weight_power': weight_power,
        'ct_weights_range': [np.min(ct_weights), np.max(ct_weights)] if ct_weights is not None else None,
        'true_nu_direction': true_nu_dir,
        'reconstructed_direction': reconstructed_dir,
        'angular_error_deg': angle_error,
        'log_likelihood': log_like,
        'cos_theta': cos_theta,
        'mcmc_chain': all_dirs[-100:],  # Store only last 100 samples to save memory
        'mcmc_log_likelihoods': all_likes[-100:],
        'all_trial_directions': all_dirs[-100:],
        'all_trial_log_likes': all_likes[-100:]
    }


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Run full 3-scenario analysis for cat000001')
    parser.add_argument('--cat-dir', type=str, 
                        default='/eos/project-e/ep-nu/evilla/sn-pointing/cat000001',
                        help='Category directory')
    parser.add_argument('--cat-name', type=str, default='cat000001',
                        help='Category name')
    parser.add_argument('--pdf-path', type=str,
                        required=True,
                        help='Path to energy-cosine PDF .npz file')
    parser.add_argument('--ed-model', type=str,
                        default='/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras',
                        help='Path to ED model .keras file')
    parser.add_argument('--ct-model', type=str,
                        default='/eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras',
                        help='Path to CT model .keras file')
    parser.add_argument('--output', type=str, 
                        default='results/cat000001_full_analysis_results.npz',
                        help='Output file for results')
    parser.add_argument('--scenarios', type=str, nargs='+',
                        default=['best_case', 'perfect_ct', 'full_pipeline'],
                        choices=['best_case', 'perfect_ct', 'full_pipeline', 'weighted_linear', 'weighted_squared', 'no_pdf', 'perfect_ct_e_gt_10mev', 'perfect_ct_e_gt_20mev'],
                        help='Which scenarios to run (full_pipeline=S3, weighted_linear=S4, weighted_squared=S5)')
    parser.add_argument('--use-eos-structure', action='store_true',
                        help='Save to EOS pipeline structure: /eos/.../catXXXXXX/pipeline/')
    parser.add_argument('--save-intermediate', action='store_true',
                        help='Save intermediate data (CT predictions, cluster indices, etc.)')
    
    args = parser.parse_args()
    
    # Load PDF
    print(f"\nLoading energy-cosine PDF from: {args.pdf_path}")
    pdf_interpolator, energy_centers, cosine_bins = load_energy_cosine_pdf(args.pdf_path)
    print(f"PDF loaded: {len(energy_centers)} energy bins, {len(cosine_bins)} cosine bins")
    
    results = {}
    
    # Run requested scenarios
    if 'best_case' in args.scenarios:
        results['best_case'] = run_scenario1_best_case(
            args.cat_dir, args.cat_name, pdf_interpolator
        )
    
    if 'perfect_ct' in args.scenarios:
        results['perfect_ct'] = run_scenario2_perfect_ct(
            args.cat_dir, args.cat_name, args.ed_model, pdf_interpolator
        )
    
    if 'full_pipeline' in args.scenarios:
        results['full_pipeline'] = run_scenario3_full_pipeline(
            args.cat_dir, args.cat_name, args.ct_model, args.ed_model, pdf_interpolator,
            weight_power=0  # No weights
        )
    
    if 'weighted_linear' in args.scenarios:
        results['weighted_linear'] = run_scenario3_full_pipeline(
            args.cat_dir, args.cat_name, args.ct_model, args.ed_model, pdf_interpolator,
            weight_power=1  # Linear CT weights
        )
    
    if 'weighted_squared' in args.scenarios:
        results['weighted_squared'] = run_scenario3_full_pipeline(
            args.cat_dir, args.cat_name, args.ct_model, args.ed_model, pdf_interpolator,
            weight_power=2  # Squared CT weights
        )
    
    if 'no_pdf' in args.scenarios:
        results['no_pdf'] = run_scenario6_no_pdf(
            args.cat_dir, args.cat_name, args.ct_model, args.ed_model,
            weight_power=0  # No PDF, no weights
        )
    
    if 'perfect_ct_e_gt_10mev' in args.scenarios:
        results['perfect_ct_e_gt_10mev'] = run_scenario7_e_gt_10mev(
            args.cat_dir, args.cat_name, args.ed_model, pdf_interpolator
        )
    
    if 'perfect_ct_e_gt_20mev' in args.scenarios:
        results['perfect_ct_e_gt_20mev'] = run_scenario8_e_gt_20mev(
            args.cat_dir, args.cat_name, args.ed_model, pdf_interpolator
        )
    
    # Determine output directory structure
    if args.use_eos_structure:
        # Save to EOS: /eos/.../catXXXXXX/pipeline/
        pipeline_dir = Path(args.cat_dir) / 'pipeline'
        pipeline_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n{'='*70}")
        print(f"Using EOS structure: {pipeline_dir}")
        print(f"{'='*70}")
        
        # Save each scenario as separate file
        for scenario, result in results.items():
            scenario_output = pipeline_dir / f"{args.cat_name}_scenario_{scenario}.npz"
            
            save_dict = {}
            for key, value in result.items():
                save_dict[f"{scenario}_{key}"] = value
            
            np.savez_compressed(scenario_output, **save_dict)
            print(f"Saved {scenario}: {scenario_output}")
    else:
        # Save to workspace results/ (original behavior)
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to saveable format
        save_dict = {}
        for scenario, result in results.items():
            for key, value in result.items():
                save_dict[f"{scenario}_{key}"] = value
        
        np.savez_compressed(output_path, **save_dict)
        print(f"\n{'='*70}")
        print(f"Results saved to: {output_path}")
        print(f"{'='*70}")
    
    # Print summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    for scenario, result in results.items():
        print(f"\n{scenario.upper()}:")
        print(f"  Clusters used: {result.get('n_clusters_used', 'N/A')}")
        print(f"  Angular error: {result['angular_error_deg']:.2f}°")
        print(f"  Log-likelihood: {result['log_likelihood']:.2f}")


if __name__ == '__main__':
    main()
