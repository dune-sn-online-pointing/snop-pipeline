#!/usr/bin/env python3
"""
Test MCMC convergence by running same category with different configurations
and plotting walker evolution
"""
import numpy as np
import matplotlib.pyplot as plt
import emcee
import sys
import os

# Suppress TensorFlow warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

def load_pdf(pdf_path):
    """Load and interpolate the angular error PDF"""
    from scipy.interpolate import RegularGridInterpolator
    data = np.load(pdf_path)
    cos_bins = data['cos_bins']
    energy_bins = data['energy_bins']
    pdf = data['pdf']
    cos_centers = (cos_bins[:-1] + cos_bins[1:]) / 2
    energy_centers = (energy_bins[:-1] + energy_bins[1:]) / 2
    return RegularGridInterpolator(
        (cos_centers, energy_centers), pdf,
        bounds_error=False, fill_value=1e-10
    )

def log_likelihood(params, cluster_dirs, cluster_energies, pdf_interpolator):
    """Calculate log likelihood for given neutrino direction"""
    theta_nu, phi_nu = params
    
    # Convert to Cartesian
    sin_theta = np.sin(theta_nu)
    nu_dir = np.array([
        sin_theta * np.cos(phi_nu),
        sin_theta * np.sin(phi_nu),
        np.cos(theta_nu)
    ])
    
    # Calculate cos(angle) between neutrino and each electron
    cos_angles = np.dot(cluster_dirs, nu_dir)
    cos_angles = np.clip(cos_angles, -1, 1)
    
    # Evaluate PDF
    points = np.column_stack([cos_angles, cluster_energies])
    pdf_vals = pdf_interpolator(points)
    pdf_vals = np.maximum(pdf_vals, 1e-10)
    
    return np.sum(np.log(pdf_vals))

def log_prior(params):
    """Uniform prior on sphere"""
    theta_nu, phi_nu = params
    if 0 <= theta_nu <= np.pi and -np.pi <= phi_nu <= np.pi:
        return np.log(np.sin(theta_nu))  # Jacobian for spherical coordinates
    return -np.inf

def log_probability(params, cluster_dirs, cluster_energies, pdf_interpolator):
    """Combined log probability"""
    lp = log_prior(params)
    if not np.isfinite(lp):
        return -np.inf
    return lp + log_likelihood(params, cluster_dirs, cluster_energies, pdf_interpolator)

def run_mcmc_test(cat_name, nwalkers, nsteps, burnin):
    """Run MCMC for a category and return chains + results"""
    
    print(f"\n{'='*70}")
    print(f"Running {nwalkers} walkers × {nsteps} steps (burnin={burnin})")
    print(f"{'='*70}\n")
    
    # Load data
    cat_dir = f'/eos/project-e/ep-nu/evilla/sn-pointing/{cat_name}/'
    matched_file = f'{cat_dir}/{cat_name}_matched_clusters_tick3_ch2_min2_tot3_e3p0/{cat_name}_matched_clusters_collection.npz'
    
    data = np.load(matched_file)
    true_nu_dir = data['true_nu_dir'][0]
    
    # Load PDF
    pdf_path = '/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz'
    pdf_interpolator = load_pdf(pdf_path)
    
    # Get matched clusters with E > 5 MeV and CT score > 0.8
    matched_mask = (data['matched_main_track_u_idx'] >= 0) & \
                   (data['matched_main_track_v_idx'] >= 0) & \
                   (data['matched_main_track_x_idx'] >= 0)
    
    energies = data['matched_main_track_energy'][matched_mask]
    dirs_x = data['matched_main_track_direction_x'][matched_mask]
    dirs_y = data['matched_main_track_direction_y'][matched_mask]
    dirs_z = data['matched_main_track_direction_z'][matched_mask]
    
    # Apply energy cut
    e_mask = energies > 5.0
    cluster_energies = energies[e_mask]
    cluster_dirs = np.column_stack([dirs_x[e_mask], dirs_y[e_mask], dirs_z[e_mask]])
    
    print(f"Using {len(cluster_energies)} ES clusters (E > 5 MeV)")
    print(f"True neutrino direction: ({true_nu_dir[0]:.3f}, {true_nu_dir[1]:.3f}, {true_nu_dir[2]:.3f})")
    
    # Convert true direction to spherical
    true_theta = np.arccos(np.clip(true_nu_dir[2], -1, 1))
    true_phi = np.arctan2(true_nu_dir[1], true_nu_dir[0])
    print(f"True (θ, φ) = ({np.degrees(true_theta):.1f}°, {np.degrees(true_phi):.1f}°)")
    
    # Initialize walkers
    initial_theta = np.random.uniform(0.1, np.pi-0.1, nwalkers)
    initial_phi = np.random.uniform(-np.pi, np.pi, nwalkers)
    initial_pos = np.column_stack([initial_theta, initial_phi])
    
    # Run MCMC
    sampler = emcee.EnsembleSampler(
        nwalkers, 2, log_probability,
        args=(cluster_dirs, cluster_energies, pdf_interpolator)
    )
    
    print(f"\nRunning MCMC...")
    sampler.run_mcmc(initial_pos, nsteps, progress=True)
    
    # Get chains
    chains = sampler.get_chain()  # shape: (nsteps, nwalkers, 2)
    acceptance = np.mean(sampler.acceptance_fraction)
    print(f"\nAcceptance fraction: {acceptance:.1%}")
    
    # Analyze after burnin
    flat_samples = sampler.get_chain(discard=burnin, flat=True)
    theta_samples = flat_samples[:, 0]
    phi_samples = flat_samples[:, 1]
    
    # Best fit
    best_theta = np.median(theta_samples)
    best_phi = np.median(phi_samples)
    
    # Convert to Cartesian
    sin_theta = np.sin(best_theta)
    best_dir = np.array([
        sin_theta * np.cos(best_phi),
        sin_theta * np.sin(best_phi),
        np.cos(best_theta)
    ])
    
    # Calculate error
    cos_angle = np.dot(best_dir, true_nu_dir)
    error_deg = np.degrees(np.arccos(np.clip(cos_angle, -1, 1)))
    
    print(f"Best fit (θ, φ) = ({np.degrees(best_theta):.1f}°, {np.degrees(best_phi):.1f}°)")
    print(f"Angular error: {error_deg:.2f}°")
    
    return {
        'chains': chains,
        'acceptance': acceptance,
        'error_deg': error_deg,
        'true_theta': true_theta,
        'true_phi': true_phi,
        'best_theta': best_theta,
        'best_phi': best_phi,
        'n_clusters': len(cluster_energies)
    }

def plot_comparison(cat_name, results_64w, results_10w):
    """Create comparison plots"""
    
    fig = plt.figure(figsize=(16, 12))
    
    # Extract data
    chains_64w = results_64w['chains']
    chains_10w = results_10w['chains']
    
    # Plot 1: Theta evolution (all walkers)
    ax1 = plt.subplot(3, 3, 1)
    for i in range(chains_64w.shape[1]):
        ax1.plot(np.degrees(chains_64w[:, i, 0]), 'b-', alpha=0.1, lw=0.5)
    ax1.axhline(np.degrees(results_64w['true_theta']), color='r', ls='--', lw=2, label='True')
    ax1.axhline(np.degrees(results_64w['best_theta']), color='g', ls='--', lw=2, label='Best fit')
    ax1.set_ylabel('θ (degrees)')
    ax1.set_title(f'64 walkers × 2000 steps\nAccept={results_64w["acceptance"]:.1%}, Error={results_64w["error_deg"]:.1f}°')
    ax1.legend(loc='upper right', fontsize=8)
    ax1.grid(alpha=0.3)
    
    ax2 = plt.subplot(3, 3, 2)
    for i in range(chains_10w.shape[1]):
        ax2.plot(np.degrees(chains_10w[:, i, 0]), 'b-', alpha=0.3, lw=1)
    ax2.axhline(np.degrees(results_10w['true_theta']), color='r', ls='--', lw=2, label='True')
    ax2.axhline(np.degrees(results_10w['best_theta']), color='g', ls='--', lw=2, label='Best fit')
    ax2.set_title(f'10 walkers × 10000 steps\nAccept={results_10w["acceptance"]:.1%}, Error={results_10w["error_deg"]:.1f}°')
    ax2.legend(loc='upper right', fontsize=8)
    ax2.grid(alpha=0.3)
    
    # Plot 2: Phi evolution (all walkers)
    ax3 = plt.subplot(3, 3, 4)
    for i in range(chains_64w.shape[1]):
        ax3.plot(np.degrees(chains_64w[:, i, 1]), 'b-', alpha=0.1, lw=0.5)
    ax3.axhline(np.degrees(results_64w['true_phi']), color='r', ls='--', lw=2)
    ax3.axhline(np.degrees(results_64w['best_phi']), color='g', ls='--', lw=2)
    ax3.set_ylabel('φ (degrees)')
    ax3.grid(alpha=0.3)
    
    ax4 = plt.subplot(3, 3, 5)
    for i in range(chains_10w.shape[1]):
        ax4.plot(np.degrees(chains_10w[:, i, 1]), 'b-', alpha=0.3, lw=1)
    ax4.axhline(np.degrees(results_10w['true_phi']), color='r', ls='--', lw=2)
    ax4.axhline(np.degrees(results_10w['best_phi']), color='g', ls='--', lw=2)
    ax4.grid(alpha=0.3)
    
    # Plot 3: Mean walker positions
    ax5 = plt.subplot(3, 3, 7)
    mean_theta_64w = np.degrees(np.mean(chains_64w[:, :, 0], axis=1))
    std_theta_64w = np.degrees(np.std(chains_64w[:, :, 0], axis=1))
    steps = np.arange(len(mean_theta_64w))
    ax5.plot(steps, mean_theta_64w, 'b-', lw=2, label='Mean')
    ax5.fill_between(steps, mean_theta_64w - std_theta_64w, mean_theta_64w + std_theta_64w, 
                     color='b', alpha=0.3, label='±1σ')
    ax5.axhline(np.degrees(results_64w['true_theta']), color='r', ls='--', lw=2)
    ax5.set_xlabel('Step')
    ax5.set_ylabel('θ (degrees)')
    ax5.legend(fontsize=8)
    ax5.grid(alpha=0.3)
    
    ax6 = plt.subplot(3, 3, 8)
    mean_theta_10w = np.degrees(np.mean(chains_10w[:, :, 0], axis=1))
    std_theta_10w = np.degrees(np.std(chains_10w[:, :, 0], axis=1))
    steps = np.arange(len(mean_theta_10w))
    ax6.plot(steps, mean_theta_10w, 'b-', lw=2)
    ax6.fill_between(steps, mean_theta_10w - std_theta_10w, mean_theta_10w + std_theta_10w, 
                     color='b', alpha=0.3)
    ax6.axhline(np.degrees(results_10w['true_theta']), color='r', ls='--', lw=2)
    ax6.set_xlabel('Step')
    ax6.grid(alpha=0.3)
    
    # Plot 4: 2D distribution (after burnin)
    burnin_64w = 400
    burnin_10w = 1000
    
    ax7 = plt.subplot(3, 3, 3)
    flat_64w = chains_64w[burnin_64w:, :, :].reshape(-1, 2)
    ax7.scatter(np.degrees(flat_64w[:, 1]), np.degrees(flat_64w[:, 0]), 
               s=1, alpha=0.1, c='b')
    ax7.plot(np.degrees(results_64w['true_phi']), np.degrees(results_64w['true_theta']), 
            'r*', ms=20, label='True', mew=2)
    ax7.plot(np.degrees(results_64w['best_phi']), np.degrees(results_64w['best_theta']), 
            'gx', ms=15, label='Best fit', mew=3)
    ax7.set_xlabel('φ (degrees)')
    ax7.set_ylabel('θ (degrees)')
    ax7.set_title('Posterior samples')
    ax7.legend(fontsize=8)
    ax7.grid(alpha=0.3)
    
    ax8 = plt.subplot(3, 3, 6)
    flat_10w = chains_10w[burnin_10w:, :, :].reshape(-1, 2)
    ax8.scatter(np.degrees(flat_10w[:, 1]), np.degrees(flat_10w[:, 0]), 
               s=1, alpha=0.3, c='b')
    ax8.plot(np.degrees(results_10w['true_phi']), np.degrees(results_10w['true_theta']), 
            'r*', ms=20, mew=2)
    ax8.plot(np.degrees(results_10w['best_phi']), np.degrees(results_10w['best_theta']), 
            'gx', ms=15, mew=3)
    ax8.set_xlabel('φ (degrees)')
    ax8.grid(alpha=0.3)
    
    # Plot 5: Autocorrelation comparison
    ax9 = plt.subplot(3, 3, 9)
    try:
        tau_64w = sampler.get_autocorr_time(quiet=True)
        tau_10w_msg = f"τ unavailable"
    except:
        tau_64w = None
        tau_10w_msg = "τ unavailable"
    
    ax9.text(0.1, 0.8, f"64w/2ks:", fontsize=12, weight='bold', transform=ax9.transAxes)
    ax9.text(0.1, 0.7, f"  N_clusters = {results_64w['n_clusters']}", fontsize=10, transform=ax9.transAxes)
    ax9.text(0.1, 0.6, f"  Acceptance = {results_64w['acceptance']:.1%}", fontsize=10, transform=ax9.transAxes)
    ax9.text(0.1, 0.5, f"  Error = {results_64w['error_deg']:.2f}°", fontsize=10, transform=ax9.transAxes)
    
    ax9.text(0.1, 0.3, f"10w/10ks:", fontsize=12, weight='bold', transform=ax9.transAxes)
    ax9.text(0.1, 0.2, f"  N_clusters = {results_10w['n_clusters']}", fontsize=10, transform=ax9.transAxes)
    ax9.text(0.1, 0.1, f"  Acceptance = {results_10w['acceptance']:.1%}", fontsize=10, transform=ax9.transAxes)
    ax9.text(0.1, 0.0, f"  Error = {results_10w['error_deg']:.2f}°", fontsize=10, transform=ax9.transAxes)
    ax9.axis('off')
    
    plt.suptitle(f'{cat_name}: MCMC Configuration Comparison', fontsize=14, weight='bold')
    plt.tight_layout()
    
    outfile = f'mcmc_comparison_{cat_name}.png'
    plt.savefig(outfile, dpi=150, bbox_inches='tight')
    print(f"\nSaved: {outfile}")
    
    return outfile

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python test_mcmc_convergence.py <cat_name>")
        print("Example: python test_mcmc_convergence.py cat000303")
        sys.exit(1)
    
    cat_name = sys.argv[1]
    
    print(f"Testing MCMC convergence for {cat_name}")
    print("="*70)
    
    # Run both configurations
    results_64w = run_mcmc_test(cat_name, nwalkers=64, nsteps=2000, burnin=400)
    results_10w = run_mcmc_test(cat_name, nwalkers=10, nsteps=10000, burnin=1000)
    
    # Create comparison plots
    plot_comparison(cat_name, results_64w, results_10w)
    
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"64w/2ks: Accept={results_64w['acceptance']:.1%}, Error={results_64w['error_deg']:.2f}°")
    print(f"10w/10ks: Accept={results_10w['acceptance']:.1%}, Error={results_10w['error_deg']:.2f}°")
    print(f"Difference: {results_10w['error_deg'] - results_64w['error_deg']:+.2f}° ({'WORSE' if results_10w['error_deg'] > results_64w['error_deg'] else 'BETTER'})")
