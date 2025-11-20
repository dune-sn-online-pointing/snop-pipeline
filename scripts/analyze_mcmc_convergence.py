#!/usr/bin/env python3
"""
Analyze MCMC convergence and damping behavior from pipeline results.

This script loads scenario results and generates detailed convergence plots
showing log likelihood evolution, jump sizes, direction stability, and
angular error convergence.

Usage:
    python analyze_mcmc_convergence.py cat000001 perfect_ct
    python analyze_mcmc_convergence.py cat000062 best_case
"""

import sys
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

try:
    import corner
    HAS_CORNER = True
except ImportError:
    HAS_CORNER = False
    print("Warning: 'corner' package not available. Install with: pip install corner")


def cartesian_to_spherical(directions):
    """
    Convert Cartesian (x, y, z) directions to spherical (theta, phi).
    
    Parameters:
    -----------
    directions : ndarray, shape (N, 3)
        Unit direction vectors in Cartesian coordinates
    
    Returns:
    --------
    theta : ndarray, shape (N,)
        Polar angle in radians [0, π]
    phi : ndarray, shape (N,)
        Azimuthal angle in radians [-π, π]
    """
    x, y, z = directions[:, 0], directions[:, 1], directions[:, 2]
    
    # Theta: angle from z-axis
    theta = np.arccos(np.clip(z, -1, 1))
    
    # Phi: angle in xy-plane from x-axis
    phi = np.arctan2(y, x)
    
    return theta, phi


def analyze_mcmc(cat_name, scenario='perfect_ct', base_path='/eos/project-e/ep-nu/evilla/sn-pointing'):
    """
    Analyze MCMC convergence for a given cat and scenario.
    
    Parameters:
    -----------
    cat_name : str
        Category name (e.g., 'cat000001')
    scenario : str
        Scenario name (e.g., 'perfect_ct', 'best_case')
    base_path : str
        Base path to sn-pointing data
    
    Returns:
    --------
    dict : Analysis results and metrics
    """
    # Load data
    result_file = Path(base_path) / cat_name / 'pipeline' / f'{cat_name}_scenario_{scenario}.npz'
    
    if not result_file.exists():
        raise FileNotFoundError(f"Result file not found: {result_file}")
    
    data = np.load(result_file, allow_pickle=True)
    
    # Extract MCMC data
    mcmc_chain = data[f'{scenario}_mcmc_chain']
    mcmc_log_likes = data[f'{scenario}_mcmc_log_likelihoods']
    
    print(f"=== MCMC Chain Analysis for {cat_name} ===\n")
    print(f"Scenario: {scenario}")
    print(f"Stored chain shape: {mcmc_chain.shape}")
    print(f"Stored log likelihoods: {len(mcmc_log_likes)}")
    
    # Convergence metrics
    print(f"\n=== Convergence Metrics ===")
    print(f"Log likelihood range: [{mcmc_log_likes.min():.2f}, {mcmc_log_likes.max():.2f}]")
    print(f"Initial log likelihood: {mcmc_log_likes[0]:.2f}")
    print(f"Final log likelihood: {mcmc_log_likes[-1]:.2f}")
    print(f"Improvement: {mcmc_log_likes[-1] - mcmc_log_likes[0]:.2f}")
    
    # Direction stability (convergence indicator)
    final_100 = mcmc_chain[-100:]
    direction_std = np.std(final_100, axis=0)
    mean_std = direction_std.mean()
    
    print(f"\n=== Final 100 Steps Stability ===")
    print(f"Direction std dev: [{direction_std[0]:.6f}, {direction_std[1]:.6f}, {direction_std[2]:.6f}]")
    print(f"Mean std dev: {mean_std:.6f}")
    
    if mean_std < 0.001:
        print("✓ Excellent convergence (std < 0.001)")
        convergence_quality = "excellent"
    elif mean_std < 0.01:
        print("✓ Good convergence (std < 0.01)")
        convergence_quality = "good"
    else:
        print("⚠ Poor convergence (std >= 0.01)")
        convergence_quality = "poor"
    
    # Analyze jumps between consecutive accepted steps
    jumps = np.array([np.linalg.norm(mcmc_chain[i] - mcmc_chain[i-1]) 
                      for i in range(1, len(mcmc_chain))])
    
    print(f"\n=== Jump Size Analysis (between accepted steps) ===")
    early_jumps = jumps[:100].mean()
    mid_jumps = jumps[len(jumps)//2-50:len(jumps)//2+50].mean() if len(jumps) > 100 else 0
    late_jumps = jumps[-100:].mean()
    
    print(f"Early jumps (0-100):     {early_jumps:.6f}")
    print(f"Middle jumps (center):   {mid_jumps:.6f}")
    print(f"Late jumps (last 100):   {late_jumps:.6f}")
    
    # Reconstruction results
    reconstructed_dir = data[f'{scenario}_reconstructed_direction']
    true_dir = data[f'{scenario}_true_nu_direction']
    cos_theta = float(data[f'{scenario}_cos_theta'])
    angular_error = float(data[f'{scenario}_angular_error_deg'])
    n_clusters = int(data[f'{scenario}_n_clusters_used'])
    
    print(f"\n=== Reconstruction Results ===")
    print(f"N clusters: {n_clusters}")
    print(f"cos(θ): {cos_theta:.4f}")
    print(f"Angular error: {angular_error:.2f}°")
    print(f"True direction:  [{true_dir[0]:.4f}, {true_dir[1]:.4f}, {true_dir[2]:.4f}]")
    print(f"Final direction: [{reconstructed_dir[0]:.4f}, {reconstructed_dir[1]:.4f}, {reconstructed_dir[2]:.4f}]")
    
    # Convert to spherical coordinates for better visualization
    theta, phi = cartesian_to_spherical(mcmc_chain)
    theta_deg = np.degrees(theta)
    phi_deg = np.degrees(phi)
    
    true_theta, true_phi = cartesian_to_spherical(true_dir.reshape(1, -1))
    true_theta_deg = np.degrees(true_theta[0])
    true_phi_deg = np.degrees(true_phi[0])
    
    # Create main visualization with walker plots
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Plot 1: Theta walker traces
    ax = axes[0, 0]
    ax.plot(theta_deg, linewidth=0.5, alpha=0.8, color='steelblue')
    ax.axhline(y=true_theta_deg, color='red', linestyle='--', linewidth=2, alpha=0.7, 
               label=f'True: {true_theta_deg:.1f}°')
    ax.set_xlabel('Step number', fontsize=11)
    ax.set_ylabel('θ (degrees)', fontsize=11)
    ax.set_title('Polar Angle (θ) Walker Trace', fontsize=12, weight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # Plot 2: Phi walker traces
    ax = axes[0, 1]
    ax.plot(phi_deg, linewidth=0.5, alpha=0.8, color='coral')
    ax.axhline(y=true_phi_deg, color='red', linestyle='--', linewidth=2, alpha=0.7,
               label=f'True: {true_phi_deg:.1f}°')
    ax.set_xlabel('Step number', fontsize=11)
    ax.set_ylabel('φ (degrees)', fontsize=11)
    ax.set_title('Azimuthal Angle (φ) Walker Trace', fontsize=12, weight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # Plot 3: Log likelihood evolution
    ax = axes[1, 0]
    ax.plot(mcmc_log_likes, linewidth=0.8, alpha=0.8, color='green')
    ax.axhline(y=mcmc_log_likes[-1], color='red', linestyle='--', alpha=0.5, 
               label=f'Final: {mcmc_log_likes[-1]:.2f}')
    ax.set_xlabel('Step number', fontsize=11)
    ax.set_ylabel('Log Likelihood', fontsize=11)
    ax.set_title('Log Likelihood Evolution', fontsize=12, weight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # Plot 4: 2D scatter of theta-phi
    ax = axes[1, 1]
    # Use different colors for early (burn-in) vs late (converged) samples
    n_burnin = min(1000, len(theta_deg) // 10)
    ax.scatter(phi_deg[:n_burnin], theta_deg[:n_burnin], 
               s=1, alpha=0.3, c='lightgray', label='Burn-in', rasterized=True)
    ax.scatter(phi_deg[n_burnin:], theta_deg[n_burnin:], 
               s=1, alpha=0.4, c='steelblue', label='Post burn-in', rasterized=True)
    ax.scatter(true_phi_deg, true_theta_deg, s=200, marker='*', 
               color='red', edgecolor='black', linewidth=1.5, 
               label='True direction', zorder=10)
    ax.set_xlabel('φ (degrees)', fontsize=11)
    ax.set_ylabel('θ (degrees)', fontsize=11)
    ax.set_title('2D θ-φ Distribution', fontsize=12, weight='bold')
    ax.legend(fontsize=9, loc='best')
    ax.grid(True, alpha=0.3)
    
    plt.suptitle(f'MCMC Walker Analysis: {cat_name} ({scenario}, {n_clusters} clusters)\n'
                 f'Angular error: {angular_error:.2f}°, Convergence: {convergence_quality.upper()}', 
                 fontsize=13, weight='bold', y=0.995)
    plt.tight_layout()
    
    # Save walker figure
    output_path = Path(base_path) / cat_name / 'pipeline' / f'mcmc_walkers_{cat_name}_{scenario}.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n✓ Saved walker plot to: {output_path}")
    plt.close()
    
    # Create corner plot if available
    if HAS_CORNER:
        # Use samples after burn-in
        n_burnin = min(2000, len(theta_deg) // 5)
        samples = np.column_stack([theta_deg[n_burnin:], phi_deg[n_burnin:]])
        
        fig = corner.corner(samples, 
                           labels=['θ (deg)', 'φ (deg)'],
                           truths=[true_theta_deg, true_phi_deg],
                           quantiles=[0.16, 0.5, 0.84],
                           show_titles=True,
                           title_fmt='.2f',
                           title_kwargs={"fontsize": 12},
                           label_kwargs={"fontsize": 13},
                           smooth=1.0,
                           bins=30,
                           color='steelblue',
                           truth_color='red',
                           hist_kwargs={'density': True})
        
        fig.suptitle(f'{cat_name} ({scenario}): θ-φ Posterior\n'
                    f'Angular error: {angular_error:.2f}°, {n_clusters} clusters', 
                    fontsize=14, weight='bold', y=1.0)
        
        corner_path = Path(base_path) / cat_name / 'pipeline' / f'mcmc_corner_{cat_name}_{scenario}.png'
        plt.savefig(corner_path, dpi=150, bbox_inches='tight')
        print(f"✓ Saved corner plot to: {corner_path}")
        plt.close()
    else:
        print("⚠ Corner plot skipped (install 'corner' package)")
    
    # Return analysis results
    results = {
        'cat_name': cat_name,
        'scenario': scenario,
        'n_clusters': n_clusters,
        'convergence_quality': convergence_quality,
        'mean_std': mean_std,
        'log_like_improvement': mcmc_log_likes[-1] - mcmc_log_likes[0],
        'angular_error': angular_error,
        'cos_theta': cos_theta,
        'early_jumps': early_jumps,
        'late_jumps': late_jumps,
        'walker_plot': str(output_path),
        'corner_plot': str(corner_path) if HAS_CORNER else None
    }
    
    return results


def main():
    """Command line interface."""
    if len(sys.argv) < 2:
        print("Usage: python analyze_mcmc_convergence.py CAT_NAME [SCENARIO]")
        print("Example: python analyze_mcmc_convergence.py cat000001 perfect_ct")
        sys.exit(1)
    
    cat_name = sys.argv[1]
    scenario = sys.argv[2] if len(sys.argv) > 2 else 'perfect_ct'
    
    try:
        results = analyze_mcmc(cat_name, scenario)
        print("\n" + "="*80)
        print("ANALYSIS COMPLETE")
        print("="*80)
        print(f"Convergence quality: {results['convergence_quality']}")
        print(f"Angular error: {results['angular_error']:.2f}°")
        print(f"Walker plot: {results['walker_plot']}")
        if results['corner_plot']:
            print(f"Corner plot: {results['corner_plot']}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
