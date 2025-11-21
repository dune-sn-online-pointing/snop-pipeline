#!/usr/bin/env python3
"""
Standalone tool to visualize electron burst directions.

Loads EMCEE results and individual electron cluster directions to create
sky maps showing the true neutrino direction, reconstructed direction,
and all individual electron scatter directions.

Usage:
    python3 plot_electron_skymap.py <cat_name> [--scenario perfect_ct]
    
Example:
    python3 plot_electron_skymap.py cat000072
    python3 plot_electron_skymap.py cat000072 --scenario full_pipeline
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from pathlib import Path
import argparse
import sys


def load_emcee_summary(cat_name, scenario='perfect_ct', base_path='/eos/project-e/ep-nu/evilla/sn-pointing'):
    """Load EMCEE summary file with best-fit direction and statistics."""
    # Path structure: /eos/project-e/ep-nu/evilla/sn-pointing/catXXXXXX/pipeline/catXXXXXX_scenario_SCENARIO_emcee.npz
    emcee_file = Path(base_path) / cat_name / 'pipeline' / f'{cat_name}_scenario_{scenario}_emcee.npz'
    
    if not emcee_file.exists():
        raise FileNotFoundError(f"EMCEE file not found: {emcee_file}")
    
    data = np.load(emcee_file)
    
    # Extract relevant data with scenario-specific keys
    key_error = f"{scenario}_emcee_angular_error_deg"
    key_x = f"{scenario}_emcee_best_dir_x"
    key_y = f"{scenario}_emcee_best_dir_y"
    key_z = f"{scenario}_emcee_best_dir_z"
    key_true_px = f"{scenario}_emcee_true_nu_px"
    key_true_py = f"{scenario}_emcee_true_nu_py"
    key_true_pz = f"{scenario}_emcee_true_nu_pz"
    key_omega = f"{scenario}_emcee_omega_68"
    
    if key_error not in data:
        raise KeyError(f"Key {key_error} not found in {emcee_file}")
    
    # Get directions
    true_dir = np.array([data[key_true_px], data[key_true_py], data[key_true_pz]])
    best_fit = np.array([data[key_x], data[key_y], data[key_z]])
    
    # Normalize
    true_norm = true_dir / np.linalg.norm(true_dir)
    best_norm = best_fit / np.linalg.norm(best_fit)
    
    # Get error and omega
    error_deg = float(data[key_error])
    omega_68 = float(data[key_omega]) if key_omega in data else None
    
    return {
        'true_dir': true_norm,
        'best_fit': best_norm,
        'error_deg': error_deg,
        'omega_68': omega_68
    }


def load_electron_directions(cat_name, scenario='perfect_ct', base_path='/eos/project-e/ep-nu/evilla/sn-pointing'):
    """Load MCMC posterior samples from the regular (non-EMCEE) reconstruction.
    
    NOTE: This loads samples from the older MCMC method, NOT from EMCEE!
    The EMCEE files only contain summary statistics (best-fit, omega_68),
    not the full posterior chain. The regular method typically has worse
    performance but provides the full posterior distribution for visualization.
    """
    # Load the regular (non-summary) file which contains MCMC chain
    reg_file = Path(base_path) / cat_name / 'pipeline' / f'{cat_name}_scenario_{scenario}.npz'
    
    if not reg_file.exists():
        raise FileNotFoundError(f"Regular pipeline file not found: {reg_file}")
    
    data = np.load(reg_file)
    
    # Load MCMC chain from regular method
    key_chain = f"{scenario}_mcmc_chain"
    if key_chain not in data:
        raise KeyError(f"Key {key_chain} not found in {reg_file}")
    
    mcmc_chain = data[key_chain]
    
    # Use post-burnin samples (second half)
    n_samples = len(mcmc_chain)
    burnin = n_samples // 2
    samples = mcmc_chain[burnin:]
    
    # Normalize
    samples_norm = samples / np.linalg.norm(samples, axis=1, keepdims=True)
    
    # Also get the regular method's error for comparison
    reg_error_key = f"{scenario}_angular_error_deg"
    reg_error = float(data[reg_error_key]) if reg_error_key in data else None
    
    print(f"Loaded {len(samples_norm)} MCMC posterior samples (from regular method, not EMCEE)")
    if reg_error:
        print(f"  Regular method error: {reg_error:.2f}° (for comparison)")
    
    return samples_norm


def cart_to_sph(dirs):
    """Convert Cartesian (x,y,z) to spherical (theta, phi)."""
    if dirs.ndim == 1:
        dirs = dirs.reshape(1, -1)
    x, y, z = dirs[:, 0], dirs[:, 1], dirs[:, 2]
    theta = np.arccos(np.clip(z, -1, 1))  # polar angle from +z
    phi = np.arctan2(y, x)  # azimuthal angle
    return theta, phi


def gnomonic_project(dirs, center):
    """
    Project directions onto tangent plane at center (gnomonic projection).
    
    Args:
        dirs: (N, 3) array of normalized direction vectors
        center: (3,) normalized center direction
        
    Returns:
        x, y: (N,) arrays of projected coordinates
    """
    # Calculate cosine of angular separation
    if dirs.ndim == 1:
        dirs = dirs.reshape(1, -1)
    
    cos_ang = dirs @ center
    # Avoid division by zero for directions near the edge
    cos_ang = np.maximum(cos_ang, 0.01)
    scale = 1.0 / cos_ang
    
    # Create orthonormal basis on tangent plane
    # First basis vector (perpendicular to center)
    if abs(center[2]) < 0.9:
        e1 = np.array([0, 0, 1])
    else:
        e1 = np.array([1, 0, 0])
    e1 = e1 - (e1 @ center) * center
    e1 = e1 / np.linalg.norm(e1)
    
    # Second basis vector (perpendicular to both)
    e2 = np.cross(center, e1)
    e2 = e2 / np.linalg.norm(e2)
    
    # Project onto tangent plane
    x = (dirs @ e1) * scale
    y = (dirs @ e2) * scale
    
    return x, y


def create_skymap(cat_name, emcee_data, electron_dirs, scenario='perfect_ct', 
                  zoom_angle=30.0, output_file=None):
    """
    Create dual sky map visualization.
    
    Args:
        cat_name: Name of the cat (e.g., 'cat000072')
        emcee_data: Dictionary with EMCEE results
        electron_dirs: (N, 3) array of electron directions
        scenario: Scenario name for title
        zoom_angle: Zoom angle in degrees for second panel
        output_file: Optional output filename (default: <cat_name>_skymap.png)
    """
    true_dir = emcee_data['true_dir']
    best_fit = emcee_data['best_fit']
    error_deg = emcee_data['error_deg']
    omega_68 = emcee_data['omega_68']
    
    # Convert to spherical coordinates
    true_theta, true_phi = cart_to_sph(true_dir)
    best_theta, best_phi = cart_to_sph(best_fit)
    elec_theta, elec_phi = cart_to_sph(electron_dirs)
    
    # Create figure
    fig = plt.figure(figsize=(18, 10))
    
    # ===== LEFT PANEL: Mollweide projection (full sky) =====
    ax1 = plt.subplot(121, projection='mollweide')
    ax1.set_facecolor('white')
    
    # Mollweide expects longitude in [-pi, pi] and latitude in [-pi/2, pi/2]
    # Convert theta (polar from +z) to latitude (from equator)
    elec_lat = np.pi/2 - elec_theta
    elec_lon = elec_phi
    
    # Create 2D histogram for heatmap
    from scipy.ndimage import gaussian_filter
    
    H, xedges, yedges = np.histogram2d(elec_lon.flatten(), elec_lat.flatten(), 
                                       bins=[360, 180], 
                                       range=[[-np.pi, np.pi], [-np.pi/2, np.pi/2]])
    
    # Apply Gaussian smoothing
    H_smooth = gaussian_filter(H.T, sigma=3.0)
    
    # Mask zeros for better visualization
    H_smooth = np.ma.masked_where(H_smooth < 0.01, H_smooth)
    
    # Create meshgrid for pcolormesh (works with Mollweide projection)
    lon_centers = (xedges[:-1] + xedges[1:]) / 2
    lat_centers = (yedges[:-1] + yedges[1:]) / 2
    LON, LAT = np.meshgrid(lon_centers, lat_centers)
    
    # Plot density heatmap
    im = ax1.pcolormesh(LON, LAT, H_smooth, cmap='viridis', 
                        shading='auto', alpha=0.8, zorder=1, rasterized=True)
    
    # Add colorbar
    cbar = plt.colorbar(im, ax=ax1, orientation='horizontal', pad=0.05, shrink=0.8)
    cbar.set_label('Electron Density', fontsize=10, fontweight='bold')
    
    # Plot true direction as red star
    true_lat = np.pi/2 - true_theta[0]
    true_lon = true_phi[0]
    ax1.scatter(true_lon, true_lat, marker='*', c='red', s=300, 
               edgecolors='white', linewidths=1.5, label='True ν Direction', zorder=10)
    
    # Plot EMCEE best-fit as yellow star
    best_lat = np.pi/2 - best_theta[0]
    best_lon = best_phi[0]
    ax1.scatter(best_lon, best_lat, marker='*', c='#FFD700', s=250, 
               edgecolors='black', linewidths=1.5, label=f'EMCEE Best ({error_deg:.2f}°)', zorder=10)
    
    ax1.set_title(f'Full Sky Map: {cat_name}', 
                 fontsize=14, fontweight='bold', pad=20)
    ax1.grid(True, alpha=0.3)
    ax1.legend(fontsize=11, loc='upper left', framealpha=0.9)
    
    # ===== RIGHT PANEL: Gnomonic projection (zoomed) =====
    ax2 = plt.subplot(122)
    ax2.set_facecolor('white')
    
    # Calculate angular separation from true direction
    cos_sep = electron_dirs @ true_dir
    ang_sep = np.degrees(np.arccos(np.clip(cos_sep, -1, 1)))
    
    # Select electrons within zoom cone
    zoom_mask = ang_sep <= zoom_angle
    zoom_electrons = electron_dirs[zoom_mask]
    
    print(f"MCMC samples within {zoom_angle}° of true direction: {len(zoom_electrons)}")
    
    if len(zoom_electrons) > 0:
        # Project onto tangent plane
        zoom_x, zoom_y = gnomonic_project(zoom_electrons, true_dir)
        
        # Plot MCMC samples
        ax2.scatter(zoom_x, zoom_y, c='#FFD700', alpha=0.4, s=8, 
                   label=f'MCMC Samples (N={len(zoom_electrons)})', rasterized=True, zorder=5)
        
        # Plot EMCEE best-fit
        best_x, best_y = gnomonic_project(best_fit.reshape(1, -1), true_dir)
        ax2.scatter(best_x, best_y, marker='*', c='#FFD700', s=250, 
                   edgecolors='black', linewidths=1.5, label=f'EMCEE Best', zorder=10)
        
        # Plot true direction at origin
        ax2.scatter(0, 0, marker='*', c='red', s=300, 
                   edgecolors='white', linewidths=1.5, label='True ν', zorder=10)
        
        # Add angular scale circles
        circle_angles = [5, 10, 15, 20, 25, 30] if zoom_angle >= 30 else [5, 10, 15, 20]
        for radius_deg in circle_angles:
            if radius_deg <= zoom_angle:
                radius_rad = np.radians(radius_deg)
                circle = Circle((0, 0), np.tan(radius_rad), fill=False, 
                              edgecolor='gray', linestyle='--', linewidth=1, alpha=0.5)
                ax2.add_patch(circle)
                ax2.text(np.tan(radius_rad) * 1.05, 0, f'{radius_deg}°', 
                        fontsize=9, color='gray', ha='left', va='center', alpha=0.8)
        
        # Add omega_68 credible interval circle if available
        if omega_68 is not None:
            omega_rad = np.radians(omega_68)
            best_r = np.sqrt(best_x[0]**2 + best_y[0]**2)
            ci_circle = Circle((best_x[0], best_y[0]), np.tan(omega_rad), fill=False,
                             edgecolor='orange', linestyle='-', linewidth=2, alpha=0.8)
            ax2.add_patch(ci_circle)
            ax2.text(best_x[0], best_y[0] + np.tan(omega_rad) * 1.1, 
                    f'ω₆₈={omega_68:.2f}°',
                    fontsize=10, color='orange', ha='center', va='bottom', 
                    fontweight='bold', bbox=dict(boxstyle='round,pad=0.3', 
                    facecolor='white', edgecolor='orange', alpha=0.9))
    else:
        ax2.text(0.5, 0.5, 'No electrons within zoom range', 
                transform=ax2.transAxes, fontsize=14, color='gray',
                ha='center', va='center')
    
    # Set equal aspect and limits
    ax2.set_aspect('equal')
    max_radius = np.tan(np.radians(zoom_angle))
    ax2.set_xlim(-max_radius * 1.1, max_radius * 1.1)
    ax2.set_ylim(-max_radius * 1.1, max_radius * 1.1)
    
    ax2.set_xlabel('Tangent Plane X', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Tangent Plane Y', fontsize=12, fontweight='bold')
    ax2.set_title(f'Zoomed View (±{zoom_angle}° from True ν)', 
                 fontsize=14, fontweight='bold', pad=20)
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=11, loc='upper right', framealpha=0.9)
    
    # Overall title
    title_text = f'{cat_name} - {scenario.upper()} (EMCEE Best-Fit)\n'
    title_text += f'Angular Error: {error_deg:.2f}°'
    if omega_68 is not None:
        title_text += f'  |  ω₆₈: {omega_68:.2f}°'
    title_text += '  |  Density: Regular MCMC (not EMCEE)'
    
    plt.suptitle(title_text, fontsize=16, fontweight='bold', y=0.98)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    
    # Save
    if output_file is None:
        output_file = f'{cat_name}_skymap.png'
    
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\n✓ Saved skymap to: {output_file}")
    
    return fig


def main():
    parser = argparse.ArgumentParser(
        description='Create electron burst sky map visualization',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 plot_electron_skymap.py cat000072
  python3 plot_electron_skymap.py cat000072 --scenario full_pipeline
  python3 plot_electron_skymap.py cat000072 --zoom 45 --output my_skymap.png
        """
    )
    
    parser.add_argument('cat_name', help='Cat name (e.g., cat000072)')
    parser.add_argument('--scenario', default='perfect_ct', 
                       help='Scenario name (default: perfect_ct)')
    parser.add_argument('--zoom', type=float, default=30.0,
                       help='Zoom angle in degrees (default: 30)')
    parser.add_argument('--output', '-o', help='Output filename')
    parser.add_argument('--base-path', default='/eos/project-e/ep-nu/evilla/sn-pointing',
                       help='Base path to data (default: /eos/project-e/ep-nu/evilla/sn-pointing)')
    
    args = parser.parse_args()
    
    try:
        print(f"Loading data for {args.cat_name}...")
        
        # Load EMCEE summary
        print(f"  Loading EMCEE summary ({args.scenario})...")
        emcee_data = load_emcee_summary(args.cat_name, args.scenario, args.base_path)
        print(f"    Angular error: {emcee_data['error_deg']:.2f}°")
        if emcee_data['omega_68'] is not None:
            print(f"    ω₆₈: {emcee_data['omega_68']:.2f}°")
        
        # Load MCMC posterior samples
        print(f"  Loading MCMC posterior samples...")
        electron_dirs = load_electron_directions(args.cat_name, args.scenario, args.base_path)
        
        # Create skymap
        print(f"\nCreating skymap...")
        create_skymap(args.cat_name, emcee_data, electron_dirs, 
                     scenario=args.scenario, zoom_angle=args.zoom,
                     output_file=args.output)
        
        print("\n✓ Done!")
        
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
