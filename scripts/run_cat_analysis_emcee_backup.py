#!/usr/bin/env python3
"""
Full cat analysis using emcee ensemble sampler for MCMC reconstruction.

This is a complete alternative implementation to run_cat000001_full_analysis.py,
using emcee ensemble sampler with spherical coordinates and sin(phi) prior.

Output files will have '_emcee' suffix to distinguish from original method.
"""

import numpy as np
import argparse
from pathlib import Path
import sys
import emcee
from scipy.interpolate import RegularGridInterpolator
from scipy.stats import circstd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def load_pdf(pdf_path):
    """Load and create interpolator for energy-cosine PDF."""
    pdf_data = np.load(pdf_path)
    pdf_values = pdf_data['pdf_2d']
    energy_bin_edges = pdf_data['energy_bins']
    cosine_bins = pdf_data['cosine_bin_centers']
    
    # Compute energy bin centers from edges
    energy_bins = np.mean(energy_bin_edges, axis=1)
    
    pdf_interpolator = RegularGridInterpolator(
        (energy_bins, cosine_bins), 
        pdf_values, 
        method='linear',
        bounds_error=False,
        fill_value=1e-10
    )
    
    print(f"PDF loaded: {len(energy_bins)} energy bins, {len(cosine_bins)} cosine bins")
    return pdf_interpolator, energy_bins, cosine_bins


def loglike_with_pdf(args, pred_x, pred_y, pred_z, energies, pdf_interpolator):
    """
    Log likelihood with energy-dependent PDF.
    
    Parameters:
    -----------
    args : tuple (theta, phi)
        Spherical coordinates in radians
        theta in [-π, π], phi in [0, π]
    pred_x, pred_y, pred_z : arrays
        Normalized cluster direction vectors
    energies : array
        Cluster energies in MeV
    pdf_interpolator : callable
        PDF(energy, cos_angle)
    """
    theta, phi = args[0], args[1]
    
    # Reconstruct direction from spherical coords
    # Convention: x=sin(phi)*cos(theta), y=cos(phi), z=sin(phi)*sin(theta)
    reco_x = np.sin(phi) * np.cos(theta)
    reco_z = np.sin(phi) * np.sin(theta)
    reco_y = np.cos(phi)
    
    # Normalize (should be ~1 already)
    norm = np.sqrt(reco_x**2 + reco_y**2 + reco_z**2)
    reco_x /= norm
    reco_y /= norm
    reco_z /= norm
    
    # Compute cos(angle) with each cluster
    cos_angles = pred_x * reco_x + pred_y * reco_y + pred_z * reco_z
    cos_angles = np.clip(cos_angles, -1, 1)
    
    # Query PDF
    points = np.column_stack([energies, cos_angles])
    probabilities = pdf_interpolator(points)
    probabilities = np.maximum(probabilities, 1e-10)
    
    loglike = np.sum(np.log(probabilities))
    return loglike


def logprior(args):
    """
    Prior for uniform sampling on sphere: sin(phi).
    
    Parameters:
    -----------
    args : tuple (theta, phi)
        theta in [-π, π], phi in [0, π]
    """
    theta, phi = args[0], args[1]
    
    if theta < -np.pi or theta > np.pi:
        return -np.inf
    if phi < 0 or phi > np.pi:
        return -np.inf
    
    # sin(phi) prior for uniform sphere sampling
    return np.log(np.sin(phi) + 1e-10)


def logpost(args, pred_x, pred_y, pred_z, energies, pdf_interpolator):
    """Log posterior = prior + likelihood."""
    prior = logprior(args)
    if not np.isfinite(prior):
        return -np.inf
    
    likelihood = loglike_with_pdf(args, pred_x, pred_y, pred_z, energies, pdf_interpolator)
    return prior + likelihood


def custom_proposal(state, random):
    """
    Custom proposal with boundary wrapping for spherical coordinates.
    
    Parameters:
    -----------
    state : array (nwalkers, 2)
        Current [theta, phi] for each walker
    random : RandomState
    
    Returns:
    --------
    new_state : array
        Proposed state
    factors : array
        Proposal factors (ones for symmetric)
    """
    new_state = np.copy(state)
    
    # Gaussian perturbation
    new_state[:, 0] = random.normal(state[:, 0], 0.1)
    new_state[:, 1] = random.normal(state[:, 1], 0.1)
    
    # Handle phi boundary reflections
    new_state[:, 0] = np.where(new_state[:, 1] > np.pi, new_state[:, 0] + np.pi, new_state[:, 0])
    new_state[:, 0] = np.where(new_state[:, 1] < 0, new_state[:, 0] + np.pi, new_state[:, 0])
    
    # Wrap theta to [-π, π]
    new_state[:, 0] = (new_state[:, 0] + np.pi) % (2 * np.pi) - np.pi
    
    # Reflect phi at boundaries
    new_state[:, 1] = np.where(new_state[:, 1] > np.pi, np.pi - (new_state[:, 1] - np.pi), new_state[:, 1])
    new_state[:, 1] = np.where(new_state[:, 1] < 0, -new_state[:, 1], new_state[:, 1])
    
    return new_state, np.ones(state.shape[0])


def run_emcee_mcmc(cluster_directions, cluster_energies, pdf_interpolator,
                   nwalkers=32, nsteps=1000, discard=200, verbose=True):
    """
    Run emcee ensemble sampler MCMC.
    
    Parameters:
    -----------
    cluster_directions : array (N, 3)
        Normalized cluster directions
    cluster_energies : array (N,)
        Cluster energies in MeV
    pdf_interpolator : callable
        PDF interpolator
    nwalkers : int
        Number of ensemble walkers
    nsteps : int
        Number of MCMC steps
    discard : int
        Burn-in steps to discard
    verbose : bool
        Print progress
    
    Returns:
    --------
    dict : Results including direction, uncertainties, samples
    """
    # Normalize directions
    norms = np.linalg.norm(cluster_directions, axis=1, keepdims=True)
    pred_x = cluster_directions[:, 0] / norms[:, 0]
    pred_y = cluster_directions[:, 1] / norms[:, 0]
    pred_z = cluster_directions[:, 2] / norms[:, 0]
    
    ndim = 2
    
    # Initialize walkers uniformly on sphere
    initial_pos = np.array([-np.pi, 0]) + np.random.rand(nwalkers, ndim) * np.array([2*np.pi, np.pi])
    
    # Create sampler
    sampler = emcee.EnsembleSampler(
        nwalkers, ndim, logpost,
        args=[pred_x, pred_y, pred_z, cluster_energies, pdf_interpolator],
        moves=[emcee.moves.MHMove(custom_proposal)]
    )
    
    # Run MCMC
    if verbose:
        print(f"  Running emcee: {nwalkers} walkers × {nsteps} steps...")
    
    sampler.run_mcmc(initial_pos, nsteps, progress=False)
    
    # Get samples
    samples = sampler.get_chain()  # (nsteps, nwalkers, ndim)
    flat_samples = sampler.get_chain(flat=True, discard=discard)
    
    acceptance_fraction = np.mean(sampler.acceptance_fraction)
    
    if verbose:
        print(f"  Mean acceptance fraction: {acceptance_fraction:.3f}")
    
    # Convert to Cartesian for averaging
    theta_samples = flat_samples[:, 0]
    phi_samples = flat_samples[:, 1]
    
    x_samples = np.sin(phi_samples) * np.cos(theta_samples)
    z_samples = np.sin(phi_samples) * np.sin(theta_samples)
    y_samples = np.cos(phi_samples)
    
    # Mean direction
    avg_x = np.mean(x_samples)
    avg_y = np.mean(y_samples)
    avg_z = np.mean(z_samples)
    
    norm = np.sqrt(avg_x**2 + avg_y**2 + avg_z**2)
    avg_x /= norm
    avg_y /= norm
    avg_z /= norm
    
    # Convert back to spherical
    avg_theta = np.arctan2(avg_z, avg_x)
    avg_phi = np.arccos(np.clip(avg_y, -1, 1))
    
    # Uncertainties
    theta_std = circstd(theta_samples, high=np.pi, low=-np.pi)
    phi_std = np.std(phi_samples)
    
    # 68% credible angle
    cos_angle_diff = avg_x * x_samples + avg_y * y_samples + avg_z * z_samples
    cos_angle_diff = np.clip(cos_angle_diff, -1, 1)
    angle_diff = np.arccos(cos_angle_diff)
    
    angle_sorted = np.sort(angle_diff)
    cumsum = np.cumsum(angle_sorted)
    cumsum = cumsum / cumsum[-1]
    idx_68 = np.where(cumsum > 0.68)[0][0]
    omega_68 = angle_sorted[idx_68]
    
    if verbose:
        print(f"  Result: θ={np.degrees(avg_theta):.2f}°, φ={np.degrees(avg_phi):.2f}°")
        print(f"  Uncertainties: Δθ={np.degrees(theta_std):.2f}°, Δφ={np.degrees(phi_std):.2f}°")
        print(f"  68% credible angle: {np.degrees(omega_68):.2f}°")
    
    return {
        'reconstructed_direction': np.array([avg_x, avg_y, avg_z]),
        'theta': avg_theta,
        'phi': avg_phi,
        'theta_std': theta_std,
        'phi_std': phi_std,
        'omega_68': omega_68,
        'samples': samples,
        'flat_samples': flat_samples,
        'acceptance_fraction': acceptance_fraction,
        'chain_log_likes': sampler.get_log_prob(flat=True, discard=discard)
    }


def run_scenario_perfect_ct_emcee(cat_dir, cat_name, ed_model_path, pdf_interpolator,
                                   nwalkers=32, nsteps=1000, discard=200, verbose=True):
    """
    Run perfect_ct scenario using emcee MCMC.
    
    This loads ES main tracks, applies ED network, and reconstructs with emcee.
    """
    import uproot
    import tensorflow as tf
    
    if verbose:
        print("\n" + "="*70)
        print("SCENARIO 2 (EMCEE): PERFECT CT (ES Main Tracks + ED Network)")
        print("="*70)
    
    cat_path = Path(cat_dir)
    
    # Load ES files
    es_dir = cat_path / f"{cat_name}_matched_clusters_tick3_ch2_min2_tot3_e3p0"
    es_files = sorted(es_dir.glob("es_*.root"))
    
    if verbose:
        print(f"\nFiles found: {len(es_files)} ES")
    
    if len(es_files) == 0:
        raise ValueError(f"No ES files found in {es_dir}")
    
    # Load ED model
    ed_model = tf.keras.models.load_model(ed_model_path, compile=False)
    
    # Process ES clusters
    cluster_directions = []
    cluster_energies = []
    
    for es_file in es_files:
        try:
            with uproot.open(es_file) as f:
                tree = f['matched_clusters']
                
                # Load images
                img_U = tree['image_U'].array(library='np')
                img_V = tree['image_V'].array(library='np')
                img_X = tree['image_X'].array(library='np')
                
                # Load energies
                energies = tree['energy'].array(library='np')
                
                # Load metadata for filtering
                metadata = tree['metadata'].array(library='np')
                
                # Filter for ES main tracks
                is_es = metadata[:, 3] == 1
                is_main = metadata[:, 4] == 1
                
                mask = is_es & is_main
                
                if np.sum(mask) == 0:
                    continue
                
                # Stack images
                images = np.stack([
                    img_U[mask],
                    img_V[mask],
                    img_X[mask]
                ], axis=-1).astype(np.float32)
                
                # Predict directions
                predictions = ed_model.predict(images, batch_size=32, verbose=0)
                
                cluster_directions.append(predictions)
                cluster_energies.append(energies[mask])
                
        except Exception as e:
            if verbose:
                print(f"Warning: Failed to process {es_file.name}: {e}")
            continue
    
    if len(cluster_directions) == 0:
        raise ValueError("No valid ES main-track clusters found")
    
    cluster_directions = np.vstack(cluster_directions)
    cluster_energies = np.concatenate(cluster_energies)
    
    n_clusters = len(cluster_directions)
    if verbose:
        print(f"Loaded {n_clusters} ES main-track clusters")
    
    # Normalize directions
    norms = np.linalg.norm(cluster_directions, axis=1, keepdims=True)
    cluster_directions = cluster_directions / norms
    
    # Load true neutrino direction
    try:
        # Try to load from existing npz if available
        existing_file = cat_path / 'pipeline' / f'{cat_name}_scenario_perfect_ct.npz'
        if existing_file.exists():
            data = np.load(existing_file)
            true_nu_direction = data['perfect_ct_true_nu_direction']
        else:
            # Load from original data
            truth_file = cat_path / f'{cat_name}_truth.npz'
            truth_data = np.load(truth_file)
            true_nu_direction = truth_data['true_nu_direction']
    except:
        if verbose:
            print("Warning: Could not load true neutrino direction")
        true_nu_direction = np.array([0., 0., 1.])
    
    # Run emcee MCMC
    results = run_emcee_mcmc(
        cluster_directions, cluster_energies, pdf_interpolator,
        nwalkers=nwalkers, nsteps=nsteps, discard=discard, verbose=verbose
    )
    
    # Compute angular error
    reconstructed_dir = results['reconstructed_direction']
    cos_angle = np.dot(reconstructed_dir, true_nu_direction)
    cos_angle = np.clip(cos_angle, -1, 1)
    angular_error = np.degrees(np.arccos(cos_angle))
    
    if verbose:
        print(f"\nReconstruction:")
        print(f"  True direction:  [{true_nu_direction[0]:.4f}, {true_nu_direction[1]:.4f}, {true_nu_direction[2]:.4f}]")
        print(f"  Reco direction:  [{reconstructed_dir[0]:.4f}, {reconstructed_dir[1]:.4f}, {reconstructed_dir[2]:.4f}]")
        print(f"  Angular error:   {angular_error:.2f}°")
        print(f"  cos(θ):          {cos_angle:.4f}")
    
    # Prepare output
    output = {
        'reconstructed_direction': reconstructed_dir,
        'true_nu_direction': true_nu_direction,
        'angular_error_deg': angular_error,
        'cos_theta': cos_angle,
        'n_clusters_used': n_clusters,
        'n_es_main_tracks': n_clusters,
        'theta': results['theta'],
        'phi': results['phi'],
        'theta_std': results['theta_std'],
        'phi_std': results['phi_std'],
        'omega_68': results['omega_68'],
        'mcmc_chain': results['samples'],
        'mcmc_flat_samples': results['flat_samples'],
        'mcmc_log_likelihoods': results['chain_log_likes'],
        'acceptance_fraction': results['acceptance_fraction'],
        'nwalkers': nwalkers,
        'nsteps': nsteps,
        'discard': discard
    }
    
    return output


def main():
    parser = argparse.ArgumentParser(description='Run cat analysis with emcee MCMC')
    parser.add_argument('--cat-dir', type=str, help='Category directory')
    parser.add_argument('--cat-name', type=str, required=True, help='Category name (e.g., cat000001)')
    parser.add_argument('--pdf-path', type=str, required=True, help='Path to PDF npz file')
    parser.add_argument('--ed-model', type=str, required=True, help='Path to ED model')
    parser.add_argument('--scenarios', type=str, nargs='+', default=['perfect_ct'],
                        choices=['perfect_ct'], help='Scenarios to run')
    parser.add_argument('--use-eos-structure', action='store_true',
                        help='Save to EOS pipeline structure')
    parser.add_argument('--nwalkers', type=int, default=32, help='Number of emcee walkers')
    parser.add_argument('--nsteps', type=int, default=1000, help='Number of MCMC steps')
    parser.add_argument('--discard', type=int, default=200, help='Burn-in steps to discard')
    
    args = parser.parse_args()
    
    # Determine cat directory
    if args.cat_dir:
        cat_dir = Path(args.cat_dir)
    else:
        cat_dir = Path('/eos/project-e/ep-nu/evilla/sn-pointing') / args.cat_name
    
    if not cat_dir.exists():
        print(f"ERROR: Cat directory not found: {cat_dir}")
        sys.exit(1)
    
    # Load PDF
    print(f"\nLoading PDF from: {args.pdf_path}")
    pdf_interpolator, _, _ = load_pdf(args.pdf_path)
    
    # Run scenarios
    results = {}
    
    if 'perfect_ct' in args.scenarios:
        results['perfect_ct'] = run_scenario_perfect_ct_emcee(
            cat_dir, args.cat_name, args.ed_model, pdf_interpolator,
            nwalkers=args.nwalkers, nsteps=args.nsteps, discard=args.discard,
            verbose=True
        )
    
    # Save results
    if args.use_eos_structure:
        output_dir = cat_dir / 'pipeline'
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f'{args.cat_name}_scenario_emcee.npz'
    else:
        output_dir = Path('results')
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f'{args.cat_name}_emcee_results.npz'
    
    # Prepare data for saving
    save_dict = {}
    for scenario, data in results.items():
        for key, value in data.items():
            save_dict[f'{scenario}_emcee_{key}'] = value
    
    np.savez(output_file, **save_dict)
    print(f"\n✓ Results saved to: {output_file}")


if __name__ == '__main__':
    main()
