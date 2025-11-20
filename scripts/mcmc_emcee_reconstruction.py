#!/usr/bin/env python3
"""
MCMC reconstruction using emcee ensemble sampler (original approach).

This implementation uses:
- Multiple walkers (ensemble sampling)
- Spherical coordinates (θ, φ)
- sin(φ) prior for uniform sampling on sphere
- Custom proposal with boundary wrapping
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import emcee
import corner
from scipy.stats import circmean, circstd


def loglike(args, pred_x, pred_y, pred_z, pdf_interpolator):
    """
    Log likelihood function with PDF.
    
    Parameters:
    -----------
    args : tuple
        (theta, phi) in radians
    pred_x, pred_y, pred_z : arrays
        Predicted cluster directions (normalized)
    pdf_interpolator : callable
        PDF interpolator function P(cos(angle) | energy)
    """
    reco_theta, reco_phi = args[0], args[1]
    
    # Construct reconstructed direction from spherical coords
    # Using convention: x = sin(phi)*cos(theta), y = cos(phi), z = sin(phi)*sin(theta)
    reco_x = np.sin(reco_phi) * np.cos(reco_theta)
    reco_z = np.sin(reco_phi) * np.sin(reco_theta)
    reco_y = np.cos(reco_phi)
    
    # Normalize (should already be normalized, but ensure)
    reco_norm = np.sqrt(reco_x**2 + reco_y**2 + reco_z**2)
    reco_x /= reco_norm
    reco_y /= reco_norm
    reco_z /= reco_norm
    
    # Compute cos(angle) between reco and each prediction
    cos_angle_diff = pred_x * reco_x + pred_y * reco_y + pred_z * reco_z
    cos_angle_diff = np.clip(cos_angle_diff, -1, 1)
    
    # Simple likelihood: -sum(angle^2) for testing
    # angle_diff = np.arccos(cos_angle_diff)
    # loglike = -np.sum(angle_diff**2)
    
    # PDF-based likelihood (not implemented yet - would need energies)
    # For now, use simple squared angle likelihood
    angle_diff = np.arccos(cos_angle_diff)
    loglike = -np.sum(angle_diff**2)
    
    return loglike


def loglike_with_pdf(args, pred_x, pred_y, pred_z, energies, pdf_interpolator):
    """
    Log likelihood function with energy-dependent PDF.
    
    Parameters:
    -----------
    args : tuple
        (theta, phi) in radians
    pred_x, pred_y, pred_z : arrays
        Predicted cluster directions (normalized)
    energies : array
        Cluster energies in MeV
    pdf_interpolator : callable
        PDF interpolator P(cos(angle), energy)
    """
    reco_theta, reco_phi = args[0], args[1]
    
    # Construct reconstructed direction
    reco_x = np.sin(reco_phi) * np.cos(reco_theta)
    reco_z = np.sin(reco_phi) * np.sin(reco_theta)
    reco_y = np.cos(reco_phi)
    
    reco_norm = np.sqrt(reco_x**2 + reco_y**2 + reco_z**2)
    reco_x /= reco_norm
    reco_y /= reco_norm
    reco_z /= reco_norm
    
    # Compute cos(angle)
    cos_angle_diff = pred_x * reco_x + pred_y * reco_y + pred_z * reco_z
    cos_angle_diff = np.clip(cos_angle_diff, -1, 1)
    
    # Query PDF
    points = np.column_stack([energies, cos_angle_diff])
    probabilities = pdf_interpolator(points)
    probabilities = np.maximum(probabilities, 1e-10)
    
    loglike = np.sum(np.log(probabilities))
    
    return loglike


def logprior(args):
    """
    Prior for uniform sampling on sphere: sin(phi).
    
    Parameters:
    -----------
    args : tuple
        (theta, phi) where theta in [-π, π], phi in [0, π]
    """
    theta, phi = args[0], args[1]
    
    # Check bounds
    if theta < -np.pi or theta > np.pi:
        return -np.inf
    if phi < 0 or phi > np.pi:
        return -np.inf
    
    # sin(phi) prior for uniform sampling on sphere
    return np.log(np.sin(phi) + 1e-10)  # Add small constant to avoid log(0)


def logpost(args, pred_x, pred_y, pred_z, energies, pdf_interpolator, use_pdf=True):
    """Log posterior = prior + likelihood."""
    prior = logprior(args)
    if not np.isfinite(prior):
        return -np.inf
    
    if use_pdf and pdf_interpolator is not None:
        likelihood = loglike_with_pdf(args, pred_x, pred_y, pred_z, energies, pdf_interpolator)
    else:
        likelihood = loglike(args, pred_x, pred_y, pred_z, pdf_interpolator)
    
    return prior + likelihood


def custom_proposal(state, random):
    """
    Custom proposal function with boundary wrapping for spherical coordinates.
    
    Parameters:
    -----------
    state : array, shape (nwalkers, 2)
        Current state [theta, phi] for each walker
    random : RandomState
        Random number generator
    
    Returns:
    --------
    new_state : array
        Proposed new state
    factors : array
        Proposal factors (all ones for symmetric proposal)
    """
    new_state = np.copy(state)
    
    # Propose new theta and phi with Gaussian perturbation
    new_state[:, 0] = random.normal(state[:, 0], 0.1)
    new_state[:, 1] = random.normal(state[:, 1], 0.1)
    
    # Handle phi boundary reflections
    # If phi > π, reflect: phi -> π - (phi - π) and shift theta by π
    new_state[:, 0] = np.where(new_state[:, 1] > np.pi, new_state[:, 0] + np.pi, new_state[:, 0])
    new_state[:, 0] = np.where(new_state[:, 1] < 0, new_state[:, 0] + np.pi, new_state[:, 0])
    
    # Wrap theta to [-π, π]
    new_state[:, 0] = (new_state[:, 0] + np.pi) % (2 * np.pi) - np.pi
    
    # Reflect phi at boundaries
    new_state[:, 1] = np.where(new_state[:, 1] > np.pi, np.pi - (new_state[:, 1] - np.pi), new_state[:, 1])
    new_state[:, 1] = np.where(new_state[:, 1] < 0, -new_state[:, 1], new_state[:, 1])
    
    return new_state, np.ones(state.shape[0])


def run_emcee_reconstruction(cluster_directions, cluster_energies, pdf_interpolator=None,
                             nwalkers=32, nsteps=1000, discard=200, use_pdf=True):
    """
    Run MCMC reconstruction using emcee ensemble sampler.
    
    Parameters:
    -----------
    cluster_directions : array, shape (N, 3)
        Unit direction vectors for each cluster
    cluster_energies : array, shape (N,)
        Energy for each cluster in MeV
    pdf_interpolator : callable, optional
        PDF interpolator for likelihood
    nwalkers : int
        Number of walkers (ensemble size)
    nsteps : int
        Number of MCMC steps
    discard : int
        Number of initial steps to discard as burn-in
    use_pdf : bool
        Whether to use PDF in likelihood
    
    Returns:
    --------
    dict : Results including mean direction, uncertainties, and samples
    """
    # Normalize cluster directions
    norms = np.linalg.norm(cluster_directions, axis=1, keepdims=True)
    pred_x = cluster_directions[:, 0] / norms[:, 0]
    pred_y = cluster_directions[:, 1] / norms[:, 0]
    pred_z = cluster_directions[:, 2] / norms[:, 0]
    
    ndim = 2
    
    # Initialize walkers uniformly on sphere
    # theta in [-π, π], phi in [0, π]
    initial_pos = np.array([-np.pi, 0]) + np.random.rand(nwalkers, ndim) * np.array([2*np.pi, np.pi])
    
    # Create sampler
    sampler = emcee.EnsembleSampler(
        nwalkers, ndim, logpost, 
        args=[pred_x, pred_y, pred_z, cluster_energies, pdf_interpolator, use_pdf],
        moves=[emcee.moves.MHMove(custom_proposal)]
    )
    
    # Run MCMC
    print(f"\nRunning emcee with {nwalkers} walkers for {nsteps} steps...")
    sampler.run_mcmc(initial_pos, nsteps, progress=False)
    
    # Get samples
    samples = sampler.get_chain()  # shape: (nsteps, nwalkers, ndim)
    flat_samples = sampler.get_chain(flat=True, discard=discard)  # shape: (nsteps-discard)*nwalkers, ndim
    
    # Compute acceptance fraction
    acceptance_fraction = np.mean(sampler.acceptance_fraction)
    print(f"Mean acceptance fraction: {acceptance_fraction:.3f}")
    
    # Convert samples to Cartesian coordinates for averaging
    theta_samples = flat_samples[:, 0]
    phi_samples = flat_samples[:, 1]
    
    x_walker = np.sin(phi_samples) * np.cos(theta_samples)
    z_walker = np.sin(phi_samples) * np.sin(theta_samples)
    y_walker = np.cos(phi_samples)
    
    # Get mean direction by averaging Cartesian components
    avg_x = np.mean(x_walker)
    avg_y = np.mean(y_walker)
    avg_z = np.mean(z_walker)
    
    # Normalize
    norm = np.sqrt(avg_x**2 + avg_y**2 + avg_z**2)
    avg_x /= norm
    avg_y /= norm
    avg_z /= norm
    
    # Convert back to spherical
    avg_theta = np.arctan2(avg_z, avg_x)
    avg_phi = np.arccos(np.clip(avg_y, -1, 1))
    
    # Compute uncertainties using circular statistics for theta
    final_theta_std = circstd(theta_samples, high=np.pi, low=-np.pi)
    final_phi_std = np.std(phi_samples)
    
    # Compute 68% credible angle (angular resolution)
    cos_angle_diff = (avg_x * x_walker + avg_y * y_walker + avg_z * z_walker)
    cos_angle_diff = np.clip(cos_angle_diff, -1, 1)
    angle_diff = np.arccos(cos_angle_diff)
    
    angle_diff_sorted = np.sort(angle_diff)
    cumsum_angle_diff = np.cumsum(angle_diff_sorted)
    cumsum_angle_diff = cumsum_angle_diff / cumsum_angle_diff[-1]
    correct_quantile_index = np.where(cumsum_angle_diff > 0.68)[0][0]
    omega_resolution = angle_diff_sorted[correct_quantile_index]
    
    print(f"\nResults:")
    print(f"  Mean direction: θ={np.degrees(avg_theta):.2f}°, φ={np.degrees(avg_phi):.2f}°")
    print(f"  Cartesian: ({avg_x:.4f}, {avg_y:.4f}, {avg_z:.4f})")
    print(f"  Uncertainties: Δθ={np.degrees(final_theta_std):.2f}°, Δφ={np.degrees(final_phi_std):.2f}°")
    print(f"  68% credible angle: {np.degrees(omega_resolution):.2f}°")
    
    results = {
        'reconstructed_direction': np.array([avg_x, avg_y, avg_z]),
        'theta': avg_theta,
        'phi': avg_phi,
        'theta_std': final_theta_std,
        'phi_std': final_phi_std,
        'omega_resolution': omega_resolution,
        'samples': samples,
        'flat_samples': flat_samples,
        'acceptance_fraction': acceptance_fraction,
        'sampler': sampler
    }
    
    return results


def test_on_cat(cat_name='cat000062', scenario='perfect_ct', 
                base_path='/eos/project-e/ep-nu/evilla/sn-pointing',
                nwalkers=32, nsteps=1000, discard=200):
    """
    Test emcee reconstruction on a specific cat and compare with current method.
    """
    from scipy.interpolate import RegularGridInterpolator
    
    print(f"\n{'='*80}")
    print(f"Testing emcee reconstruction on {cat_name} ({scenario})")
    print(f"{'='*80}")
    
    # Load existing results from current method
    result_file = Path(base_path) / cat_name / 'pipeline' / f'{cat_name}_scenario_{scenario}.npz'
    if not result_file.exists():
        print(f"ERROR: Result file not found: {result_file}")
        return None
    
    data = np.load(result_file, allow_pickle=True)
    
    # Get data
    true_direction = data[f'{scenario}_true_nu_direction']
    current_reconstructed = data[f'{scenario}_reconstructed_direction']
    current_angular_error = float(data[f'{scenario}_angular_error_deg'])
    n_clusters = int(data[f'{scenario}_n_clusters_used'])
    
    print(f"\nLoaded data:")
    print(f"  True direction: ({true_direction[0]:.4f}, {true_direction[1]:.4f}, {true_direction[2]:.4f})")
    print(f"  Current method result: {current_angular_error:.2f}° error")
    print(f"  N clusters: {n_clusters}")
    
    # We need to regenerate cluster directions since they're not stored
    # For now, use a simpler test: load from cluster data
    print("\nNote: Using simplified test - would need full cluster data for exact comparison")
    
    # Create dummy cluster data for testing
    # In practice, would load actual cluster directions and energies
    np.random.seed(42)
    cluster_directions = np.random.randn(n_clusters, 3)
    cluster_directions /= np.linalg.norm(cluster_directions, axis=1, keepdims=True)
    
    # Bias toward true direction to simulate real data
    cluster_directions = 0.7 * true_direction + 0.3 * cluster_directions
    cluster_directions /= np.linalg.norm(cluster_directions, axis=1, keepdims=True)
    
    cluster_energies = np.random.uniform(5, 50, n_clusters)
    
    # Load PDF
    pdf_path = Path('/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz')
    pdf_data = np.load(pdf_path)
    pdf_values = pdf_data['pdf_2d']
    energy_bins = np.mean(pdf_data['energy_bins'], axis=1)
    cosine_bins = pdf_data['cosine_bin_centers']
    
    pdf_interpolator = RegularGridInterpolator(
        (energy_bins, cosine_bins), 
        pdf_values, 
        method='linear',
        bounds_error=False,
        fill_value=1e-10
    )
    
    # Run emcee reconstruction
    results = run_emcee_reconstruction(
        cluster_directions, cluster_energies, pdf_interpolator,
        nwalkers=nwalkers, nsteps=nsteps, discard=discard, use_pdf=True
    )
    
    # Compute angular error for emcee result
    cos_angle = np.dot(results['reconstructed_direction'], true_direction)
    cos_angle = np.clip(cos_angle, -1, 1)
    emcee_angular_error = np.degrees(np.arccos(cos_angle))
    
    print(f"\n{'='*80}")
    print(f"COMPARISON:")
    print(f"{'='*80}")
    print(f"Current method: {current_angular_error:.2f}° error")
    print(f"Emcee method:   {emcee_angular_error:.2f}° error")
    print(f"Difference:     {emcee_angular_error - current_angular_error:.2f}°")
    
    if emcee_angular_error < current_angular_error:
        print(f"\n✅ Emcee method is BETTER by {current_angular_error - emcee_angular_error:.2f}°")
    else:
        print(f"\n❌ Emcee method is WORSE by {emcee_angular_error - current_angular_error:.2f}°")
    
    # Create visualization
    output_dir = Path(base_path) / cat_name / 'pipeline'
    
    # Walker traces
    samples = results['samples']
    fig, axes = plt.subplots(figsize=(14, 8), ncols=1, nrows=2)
    
    for k in range(min(nwalkers, 20)):  # Plot up to 20 walkers
        axes[0].plot(samples[:, k, 0], alpha=0.3, linewidth=0.5)
        axes[1].plot(samples[:, k, 1], alpha=0.3, linewidth=0.5)
    
    axes[0].set_ylabel("θ (radians)", fontsize=11)
    axes[0].set_xlabel("Step number", fontsize=11)
    axes[0].axhline(results['theta'], color='red', linestyle='--', linewidth=2, alpha=0.7, label='Mean')
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()
    
    axes[1].set_ylabel("φ (radians)", fontsize=11)
    axes[1].set_xlabel("Step number", fontsize=11)
    axes[1].axhline(results['phi'], color='red', linestyle='--', linewidth=2, alpha=0.7, label='Mean')
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()
    
    plt.suptitle(f'Emcee Walker Traces: {cat_name} ({scenario})\n'
                 f'{nwalkers} walkers, {nsteps} steps, angular error: {emcee_angular_error:.2f}°',
                 fontsize=13, weight='bold')
    plt.tight_layout()
    
    walker_path = output_dir / f'emcee_walkers_{cat_name}_{scenario}.png'
    plt.savefig(walker_path, dpi=150, bbox_inches='tight')
    print(f"\n✓ Saved walker plot: {walker_path}")
    plt.close()
    
    # Corner plot
    fig = corner.corner(
        results['flat_samples'],
        labels=['θ (rad)', 'φ (rad)'],
        quantiles=[0.16, 0.5, 0.84],
        show_titles=True,
        title_fmt='.3f',
        bins=40,
        color='steelblue'
    )
    
    fig.suptitle(f'Emcee Posterior: {cat_name} ({scenario})\n'
                 f'Angular error: {emcee_angular_error:.2f}°, 68% credible: {np.degrees(results["omega_resolution"]):.2f}°',
                 fontsize=13, weight='bold', y=1.0)
    
    corner_path = output_dir / f'emcee_corner_{cat_name}_{scenario}.png'
    plt.savefig(corner_path, dpi=150, bbox_inches='tight')
    print(f"✓ Saved corner plot: {corner_path}")
    plt.close()
    
    return results


if __name__ == '__main__':
    import sys
    
    # Test on cat000062
    results = test_on_cat(
        cat_name='cat000062',
        scenario='perfect_ct',
        nwalkers=32,
        nsteps=1000,
        discard=200
    )
