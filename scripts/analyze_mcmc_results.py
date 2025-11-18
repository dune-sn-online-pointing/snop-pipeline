#!/usr/bin/env python3
"""
Analyze existing MCMC results and create visualizations.
Shows evolution of offsets and theta-phi distributions.
"""

import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from pathlib import Path
import sys
import argparse

def load_mcmc_metrics(metrics_file):
    """Load MCMC metrics from JSON file."""
    with open(metrics_file, 'r') as f:
        data = json.load(f)
    return data

def extract_directions(events):
    """Extract true and predicted directions from events."""
    true_dirs = []
    mcmc_dirs = []
    
    for event in events:
        true_dirs.append(event['true_direction'])
        mcmc_dirs.append(event['mcmc_direction'])
    
    true_dirs = np.array(true_dirs)
    mcmc_dirs = np.array(mcmc_dirs)
    
    return true_dirs, mcmc_dirs

def cartesian_to_spherical(directions):
    """Convert cartesian (x,y,z) to spherical (theta, phi)."""
    x, y, z = directions[:, 0], directions[:, 1], directions[:, 2]
    
    # Theta: polar angle from z-axis (0 to pi)
    theta = np.arccos(np.clip(z, -1, 1))
    
    # Phi: azimuthal angle in x-y plane (-pi to pi)
    phi = np.arctan2(y, x)
    
    return np.degrees(theta), np.degrees(phi)

def plot_theta_phi_comparison(true_dirs, mcmc_dirs, cat_name, output_dir):
    """Create theta-phi comparison plots similar to the reference image."""
    
    # Convert to spherical coordinates
    true_theta, true_phi = cartesian_to_spherical(true_dirs)
    mcmc_theta, mcmc_phi = cartesian_to_spherical(mcmc_dirs)
    
    # Create figure with 2x2 subplot layout
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle(f'MCMC Direction Analysis - {cat_name}', fontsize=16, fontweight='bold')
    
    # Common histogram parameters
    alpha = 0.7
    bins = 20
    
    # Plot 1: Phi comparison
    ax1.hist(true_phi, bins=bins, alpha=alpha, label='True', color='blue', density=True)
    ax1.hist(mcmc_phi, bins=bins, alpha=alpha, label='MCMC', color='red', density=True)
    ax1.set_xlabel('φ [degrees]')
    ax1.set_ylabel('Density')
    ax1.set_title('Azimuthal Angle (φ) Distribution')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Add statistics
    phi_stats = f'True: μ={np.mean(true_phi):.1f}°, σ={np.std(true_phi):.1f}°\n'
    phi_stats += f'MCMC: μ={np.mean(mcmc_phi):.1f}°, σ={np.std(mcmc_phi):.1f}°'
    ax1.text(0.05, 0.95, phi_stats, transform=ax1.transAxes, verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    # Plot 2: Theta comparison
    ax2.hist(true_theta, bins=bins, alpha=alpha, label='True', color='blue', density=True)
    ax2.hist(mcmc_theta, bins=bins, alpha=alpha, label='MCMC', color='red', density=True)
    ax2.set_xlabel('θ [degrees]')
    ax2.set_ylabel('Density')
    ax2.set_title('Polar Angle (θ) Distribution')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Add statistics
    theta_stats = f'True: μ={np.mean(true_theta):.1f}°, σ={np.std(true_theta):.1f}°\n'
    theta_stats += f'MCMC: μ={np.mean(mcmc_theta):.1f}°, σ={np.std(mcmc_theta):.1f}°'
    ax2.text(0.05, 0.95, theta_stats, transform=ax2.transAxes, verticalalignment='top',
             bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    # Plot 3: 2D scatter plot (φ vs θ)
    ax3.scatter(true_phi, true_theta, alpha=0.6, label='True', color='blue', s=30)
    ax3.scatter(mcmc_phi, mcmc_theta, alpha=0.6, label='MCMC', color='red', s=30)
    ax3.set_xlabel('φ [degrees]')
    ax3.set_ylabel('θ [degrees]')
    ax3.set_title('φ vs θ Scatter Plot')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # Plot 4: Angular difference analysis
    cosines = []
    for i in range(len(true_dirs)):
        cosine = np.dot(true_dirs[i], mcmc_dirs[i])
        cosines.append(cosine)
    
    cosines = np.array(cosines)
    angles_deg = np.degrees(np.arccos(np.clip(cosines, -1, 1)))
    
    ax4.hist(angles_deg, bins=bins, alpha=alpha, color='green', density=True)
    ax4.axvline(np.mean(angles_deg), color='red', linestyle='--', linewidth=2, 
                label=f'Mean: {np.mean(angles_deg):.1f}°')
    ax4.axvline(np.percentile(angles_deg, 68), color='orange', linestyle='--', linewidth=2,
                label=f'68%: {np.percentile(angles_deg, 68):.1f}°')
    ax4.set_xlabel('Angular Difference [degrees]')
    ax4.set_ylabel('Density')
    ax4.set_title('True vs MCMC Angular Difference')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Save plot
    output_file = output_dir / f'{cat_name}_theta_phi_analysis.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✓ Saved theta-phi analysis: {output_file}")
    
    return fig

def plot_mcmc_summary_stats(data, output_dir):
    """Plot summary statistics from MCMC results."""
    
    events = data['events']
    cat_name = data['cat_name']
    
    # Extract key metrics
    cosines = [event['cosine_angle'] for event in events]
    angles = [event['angle_deg'] for event in events]
    acceptance_rates = [event['mcmc_acceptance_rate'] for event in events]
    log_likelihoods = [event['mcmc_log_likelihood'] for event in events]
    n_clusters = [event['n_clusters'] for event in events]
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle(f'MCMC Performance Analysis - {cat_name}', fontsize=16, fontweight='bold')
    
    # Plot 1: Cosine distribution
    ax1.hist(cosines, bins=15, alpha=0.7, color='blue')
    ax1.axvline(np.mean(cosines), color='red', linestyle='--', 
                label=f'Mean: {np.mean(cosines):.3f}')
    ax1.axvline(np.percentile(cosines, 68), color='orange', linestyle='--',
                label=f'68%: {np.percentile(cosines, 68):.3f}')
    ax1.set_xlabel('Cosine Angle')
    ax1.set_ylabel('Count')
    ax1.set_title('True vs MCMC Cosine Distribution')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: MCMC acceptance rate
    ax2.hist(acceptance_rates, bins=15, alpha=0.7, color='green')
    ax2.axvline(np.mean(acceptance_rates), color='red', linestyle='--',
                label=f'Mean: {np.mean(acceptance_rates):.3f}')
    ax2.set_xlabel('Acceptance Rate')
    ax2.set_ylabel('Count')
    ax2.set_title('MCMC Acceptance Rate Distribution')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Plot 3: Log likelihood distribution
    ax3.hist(log_likelihoods, bins=15, alpha=0.7, color='purple')
    ax3.axvline(np.mean(log_likelihoods), color='red', linestyle='--',
                label=f'Mean: {np.mean(log_likelihoods):.1f}')
    ax3.set_xlabel('Log Likelihood')
    ax3.set_ylabel('Count')
    ax3.set_title('MCMC Log Likelihood Distribution')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # Plot 4: Number of clusters vs cosine
    scatter = ax4.scatter(n_clusters, cosines, alpha=0.6, c=acceptance_rates, 
                         cmap='viridis', s=50)
    ax4.set_xlabel('Number of Clusters')
    ax4.set_ylabel('Cosine Angle')
    ax4.set_title('Clusters vs Performance (colored by acceptance rate)')
    ax4.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax4, label='Acceptance Rate')
    
    plt.tight_layout()
    
    # Save plot
    output_file = output_dir / f'{cat_name}_mcmc_performance.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"✓ Saved MCMC performance analysis: {output_file}")
    
    return fig

def analyze_mcmc_category(metrics_file, output_dir):
    """Analyze a single MCMC category and create visualizations."""
    
    print(f"Analyzing MCMC results: {metrics_file}")
    
    # Load data
    data = load_mcmc_metrics(metrics_file)
    cat_name = data['cat_name']
    events = data['events']
    
    print(f"Category: {cat_name}")
    print(f"Number of events: {len(events)}")
    
    # Extract directions
    true_dirs, mcmc_dirs = extract_directions(events)
    
    # Create output directory
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate plots
    plot_theta_phi_comparison(true_dirs, mcmc_dirs, cat_name, output_dir)
    plot_mcmc_summary_stats(data, output_dir)
    
    # Print summary
    summary = data['summary']
    print(f"\nSummary Statistics:")
    print(f"  Mean cosine: {summary['mean_cosine']:.3f}")
    print(f"  Mean angle: {summary['mean_angle_deg']:.1f}°")
    print(f"  P68 angle: {summary['p68_angle_deg']:.1f}°")
    print(f"  Std cosine: {summary['std_cosine']:.3f}")

def main():
    parser = argparse.ArgumentParser(description='Analyze MCMC results')
    parser.add_argument('--metrics-file', required=True, help='Path to metrics.json file')
    parser.add_argument('--output-dir', default='mcmc_analysis', help='Output directory for plots')
    
    args = parser.parse_args()
    
    if not Path(args.metrics_file).exists():
        print(f"Error: Metrics file not found: {args.metrics_file}")
        return 1
    
    analyze_mcmc_category(args.metrics_file, args.output_dir)
    print(f"\n✓ Analysis complete! Check {args.output_dir} for plots.")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())