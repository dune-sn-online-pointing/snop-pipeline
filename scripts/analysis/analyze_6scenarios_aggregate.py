#!/usr/bin/env python3
"""
Aggregate analysis of emcee results across all 6 scenarios.
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys

SCENARIOS = [
    'best_case',
    'perfect_ct',
    'full_pipeline',
    'weighted_ct',
    'perfect_ct_e_gt_10mev',
    'perfect_ct_e_gt_5mev'
]

SCENARIO_LABELS = {
    'best_case': 'Best Case (True e⁻)',
    'perfect_ct': 'Perfect CT (ES + ED)',
    'full_pipeline': 'Full Pipeline (CT + ED)',
    'weighted_ct': 'Weighted CT',
    'perfect_ct_e_gt_10mev': 'Perfect CT (E>10 MeV)',
    'perfect_ct_e_gt_5mev': 'Perfect CT (E>5 MeV)'
}

def load_results(base_path='/eos/project-e/ep-nu/evilla/sn-pointing', min_es_files=9):
    """Load all emcee results for the 6 scenarios.
    
    Args:
        base_path: Base path to search for results
        min_es_files: Minimum number of ES files required (default: 9)
    """
    base = Path(base_path)
    results = {scenario: [] for scenario in SCENARIOS}
    cat_names = {scenario: [] for scenario in SCENARIOS}
    cos_theta_results = {scenario: [] for scenario in SCENARIOS}
    true_directions = {scenario: [] for scenario in SCENARIOS}  # Store true nu directions
    cluster_tracking = {scenario: {'n_total': [], 'n_es_main': [], 'n_used': []}
                       for scenario in SCENARIOS}
    
    # Track files and clusters per cat (for all cats, not per scenario)
    cat_file_stats = {'es_files': [], 'cc_files': [], 'es_clusters': [], 'cc_clusters': []}
    n_filtered_cats = 0  # Count filtered cats
    
    # Find all cats with emcee results
    for cat_dir in sorted(base.glob('cat*')):
        cat_name = cat_dir.name
        pipeline_dir = cat_dir / 'pipeline'
        
        if not pipeline_dir.exists():
            continue
        
        # Count input clusters once per cat
        cluster_dir = cat_dir / f'{cat_name}_cluster_images_tick3_ch2_min2_tot3_e3p0'
        try:
            # Count files (unique clusters across all planes)
            es_files = list(cluster_dir.glob('*/es_*.npz'))
            cc_files = list(cluster_dir.glob('*/cc_*.npz'))
            n_es_files = len(set([f.stem.replace('_planeU', '').replace('_planeV', '').replace('_planeX', '') for f in es_files]))
            n_cc_files = len(set([f.stem.replace('_planeU', '').replace('_planeV', '').replace('_planeX', '') for f in cc_files]))
            
            # Apply ES file filter
            if n_es_files < min_es_files:
                n_filtered_cats += 1
                continue
            
            # Total number of cluster files (all planes)
            n_es_clusters = len(es_files)
            n_cc_clusters = len(cc_files)
            n_total_clusters = n_es_files + n_cc_files
            
            # Track stats for histograms (only if cat has any results)
            has_results = any((pipeline_dir / f"{cat_name}_scenario_{s}_emcee.npz").exists() for s in SCENARIOS)
            if has_results:
                cat_file_stats['es_files'].append(n_es_files)
                cat_file_stats['cc_files'].append(n_cc_files)
                cat_file_stats['es_clusters'].append(n_es_clusters)
                cat_file_stats['cc_clusters'].append(n_cc_clusters)
        except:
            n_es_files = 0
            n_cc_files = 0
            n_es_clusters = 0
            n_cc_clusters = 0
            n_total_clusters = 0
        
        # Check each scenario
        for scenario in SCENARIOS:
            emcee_file = pipeline_dir / f"{cat_name}_scenario_{scenario}_emcee.npz"
            
            if emcee_file.exists():
                try:
                    data = np.load(emcee_file)
                    key_error = f"{scenario}_emcee_angular_error_deg"
                    key_cos_theta = f"{scenario}_emcee_cos_theta"
                    key_n_clusters = f"{scenario}_emcee_n_clusters_used"
                    
                    if key_error in data and key_cos_theta in data:
                        angular_error = float(data[key_error])
                        cos_theta = float(data[key_cos_theta])
                        results[scenario].append(angular_error)
                        cos_theta_results[scenario].append(cos_theta)
                        cat_names[scenario].append(cat_name)
                        
                        # Store true neutrino direction
                        key_true_px = f"{scenario}_emcee_true_nu_px"
                        key_true_py = f"{scenario}_emcee_true_nu_py"
                        key_true_pz = f"{scenario}_emcee_true_nu_pz"
                        if key_true_px in data and key_true_py in data and key_true_pz in data:
                            true_dir = np.array([data[key_true_px], data[key_true_py], data[key_true_pz]])
                            true_directions[scenario].append(true_dir)
                        else:
                            true_directions[scenario].append(None)
                        
                        # Track cluster usage
                        if key_n_clusters in data and n_total_clusters > 0:
                            cluster_tracking[scenario]['n_total'].append(n_total_clusters)
                            cluster_tracking[scenario]['n_es_main'].append(n_es_files)
                            cluster_tracking[scenario]['n_used'].append(int(data[key_n_clusters]))
                            
                except Exception as e:
                    print(f"Warning: Could not load {emcee_file}: {e}", file=sys.stderr)
    
    print(f"\nFiltered out {n_filtered_cats} cats with fewer than {min_es_files} ES files")
    return results, cat_names, cos_theta_results, cluster_tracking, cat_file_stats, true_directions

def create_cluster_tracking_page(cluster_tracking, pdf):
    """Create a page showing cluster tracking/retention metrics"""
    fig = plt.figure(figsize=(18, 10))
    
    # Compute statistics
    track_stats = {}
    for scenario in SCENARIOS:
        t = cluster_tracking[scenario]
        if len(t['n_used']) > 0:
            # For scenarios with reasonable retention (<200%), calculate normally
            # For full_pipeline/weighted_ct with >200%, flag as "MCMC samples"
            mean_total = np.mean(t['n_total'])
            mean_used = np.mean(t['n_used'])
            retention = (mean_used / mean_total * 100) if mean_total > 0 else 0
            
            track_stats[scenario] = {
                'n_cats': len(t['n_used']),
                'total_mean': mean_total,
                'es_main_mean': np.mean(t['n_es_main']),
                'used_mean': mean_used,
                'retention_pct': retention,
                'is_mcmc_count': retention > 200  # Flag if this is MCMC samples count
            }
        else:
            track_stats[scenario] = None
    
    # Create table
    ax = plt.subplot(1, 1, 1)
    ax.axis('off')
    
    table_data = [['Scenario', 'N Cats', 'Input Total', 'Input ES Main', 
                   'Value "Clusters Used"', 'Notes']]
    
    for scenario in SCENARIOS:
        s = track_stats[scenario]
        if s is not None:
            if s['is_mcmc_count']:
                note = 'MCMC samples (weighted sum)'
            else:
                note = f"{s['retention_pct']:.1f}% retention"
            
            table_data.append([
                SCENARIO_LABELS[scenario],
                f"{s['n_cats']}",
                f"{s['total_mean']:.0f}",
                f"{s['es_main_mean']:.0f}",
                f"{s['used_mean']:.0f}",
                note
            ])
    
    table = ax.table(cellText=table_data, cellLoc='center', loc='center',
                    colWidths=[0.28, 0.08, 0.12, 0.14, 0.16, 0.22])
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 4)
    
    # Style header
    for j in range(6):
        cell = table[(0, j)]
        cell.set_facecolor('#2E7D32')
        cell.set_text_props(weight='bold', color='white', fontsize=12)
        cell.set_edgecolor('white')
        cell.set_linewidth(2)
    
    # Style data rows
    for i in range(1, len(table_data)):
        for j in range(6):
            cell = table[(i, j)]
            cell.set_facecolor('#f5f5f5' if i % 2 == 0 else 'white')
            cell.set_edgecolor('#ddd')
            cell.set_text_props(fontsize=10)
            if j == 0:  # Scenario name column
                cell.set_text_props(weight='bold', fontsize=11)
    
    ax.text(0.5, 0.95, 'Cluster Usage Across Scenarios',
            ha='center', va='top', transform=ax.transAxes,
            fontsize=18, fontweight='bold')
    
    ax.text(0.5, 0.06, 
            'Note: "Clusters Used" shows different meanings per scenario:\n'
            '• Best Case, Perfect CT: Number of ES main clusters actually used (after E>3 MeV cut)\n'
            '• Full Pipeline, Weighted CT: Weighted sum of cluster contributions in MCMC (includes CT probabilities)\n'
            '• Energy cut scenarios: Number of clusters passing energy threshold\n\n'
            'The key insight: Best Case and Perfect CT use ~85-90% of ES main tracks with E>3 MeV.\n'
            'Full Pipeline shows much higher values due to weighted MCMC sampling, not actual cluster count.',
            ha='center', va='top', transform=ax.transAxes,
            fontsize=9, style='italic', color='#555',
            bbox=dict(boxstyle='round,pad=0.8', facecolor='#fffacd', alpha=0.6))
    
    pdf.savefig(fig, bbox_inches='tight')
    plt.close()


def create_axis_aligned_page(results, cos_theta_results, true_directions, pdf):
    """Create axis-aligned analysis page for perfect_ct scenario (±30° selection)."""
    scenario = 'perfect_ct'
    
    if scenario not in results or not results[scenario]:
        return
    
    angular_errors = np.array(results[scenario])
    cos_theta_data = np.array(cos_theta_results[scenario])
    true_dirs = true_directions[scenario]
    
    # Filter out None values
    valid_indices = [i for i, d in enumerate(true_dirs) if d is not None]
    if len(valid_indices) == 0:
        return
    
    angular_errors = angular_errors[valid_indices]
    cos_theta_data = cos_theta_data[valid_indices]
    true_dirs = np.array([true_dirs[i] for i in valid_indices])
    
    # Normalize directions
    true_dirs_norm = true_dirs / np.linalg.norm(true_dirs, axis=1, keepdims=True)
    
    # Define axes
    x_axis = np.array([1, 0, 0])
    y_axis = np.array([0, 1, 0])
    z_axis = np.array([0, 0, 1])
    
    # Calculate angles with each axis
    angle_with_x = np.degrees(np.arccos(np.clip(np.abs(true_dirs_norm @ x_axis), -1, 1)))
    angle_with_y = np.degrees(np.arccos(np.clip(np.abs(true_dirs_norm @ y_axis), -1, 1)))
    angle_with_z = np.degrees(np.arccos(np.clip(np.abs(true_dirs_norm @ z_axis), -1, 1)))
    
    # Select events within ±30° of each axis
    opening_angle = 30.0
    x_aligned = angle_with_x <= opening_angle
    y_aligned = angle_with_y <= opening_angle
    z_aligned = angle_with_z <= opening_angle
    
    # Create figure with 3x2 subplots (angle and cosine for each axis)
    fig = plt.figure(figsize=(18, 12))
    fig.suptitle(f'Perfect CT (ES + ED) - Axis-Aligned Analysis (±{opening_angle}° selection)', 
                 fontsize=16, fontweight='bold', y=0.995)
    
    axes_data = [
        ('X', x_aligned, '#E74C3C'),
        ('Y', y_aligned, '#3498DB'),
        ('Z', z_aligned, '#2ECC71')
    ]
    
    for idx, (axis_name, mask, color) in enumerate(axes_data):
        if np.sum(mask) == 0:
            continue
        
        errors_aligned = angular_errors[mask]
        cos_aligned = cos_theta_data[mask]
        n_events = len(errors_aligned)
        
        median_err = np.median(errors_aligned)
        q68_cos = np.percentile(cos_aligned, 68)
        forward_pct = np.sum(cos_aligned > 0) / len(cos_aligned) * 100 if len(cos_aligned) > 0 else 0
        backward_pct = 100 - forward_pct
        
        # Angle distribution
        ax1 = plt.subplot(3, 2, idx*2 + 1)
        n, bins, patches = ax1.hist(errors_aligned, bins=30, range=(0, 180), 
                                      alpha=0.7, color=color, edgecolor='black', linewidth=0.5)
        
        ax1.axvline(median_err, color='red', linestyle='--', linewidth=2.5, 
                   label=f'Median = {median_err:.1f}°')
        ax1.axvline(np.percentile(errors_aligned, 68), color='orange', linestyle='--', linewidth=2,
                   label=f'68th %ile = {np.percentile(errors_aligned, 68):.1f}°')
        
        stats_text = f'Events: {n_events:,}\nMedian: {median_err:.1f}°\n68th %ile: {np.percentile(errors_aligned, 68):.1f}°\nForward: {forward_pct:.1f}%\nBackward: {backward_pct:.1f}%'
        ax1.text(0.95, 0.95, stats_text, transform=ax1.transAxes, 
                fontsize=10, verticalalignment='top', horizontalalignment='right',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        ax1.set_xlabel(f'Angle (degrees) with true neutrino direction', fontsize=11, fontweight='bold')
        ax1.set_ylabel('Count', fontsize=11, fontweight='bold')
        ax1.set_title(f'{axis_name}-aligned (within ±{opening_angle}° of {axis_name}-axis): Angle Distribution', 
                     fontsize=12, fontweight='bold')
        ax1.legend(fontsize=9, loc='upper right')
        ax1.grid(True, alpha=0.3)
        
        # Cosine distribution (zoomed to 0.5-1.0)
        ax2 = plt.subplot(3, 2, idx*2 + 2)
        n, bins, patches = ax2.hist(cos_aligned, bins=50, range=(0.5, 1.0),
                                      alpha=0.7, color=color, edgecolor='black', linewidth=0.5)
        
        # Convert cosine values to angles for legend
        q68_angle = np.degrees(np.arccos(q68_cos))
        median_angle = np.degrees(np.arccos(np.median(cos_aligned)))
        
        ax2.axvline(q68_cos, color='red', linestyle='--', linewidth=2.5,
                   label=f'68th %ile = {q68_cos:.4f} ({q68_angle:.1f}°)')
        ax2.axvline(np.median(cos_aligned), color='orange', linestyle='--', linewidth=2,
                   label=f'Median = {np.median(cos_aligned):.4f} ({median_angle:.1f}°)')
        
        ax2.set_xlabel('cos(θ)', fontsize=11, fontweight='bold')
        ax2.set_ylabel('Count', fontsize=11, fontweight='bold')
        ax2.set_title(f'{axis_name}-aligned: Cosine Distribution [0.5-1.0 range]', fontsize=12, fontweight='bold')
        ax2.legend(fontsize=9, loc='upper left')
        ax2.grid(True, alpha=0.3)
    
    # Add note about coordinate system and axis alignment
    fig.text(0.5, 0.02, 
            'NOTE: Axis alignment is based on TRUE neutrino direction. '
            'X-axis performance depends on detector geometry (drift direction, wire orientation). '
            'Verify X/Y/Z coordinate definitions match your detector setup.',
            ha='center', fontsize=9, style='italic', color='#555',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#fffacd', alpha=0.7))
    
    plt.tight_layout(rect=[0, 0.05, 1, 1])
    pdf.savefig(fig, bbox_inches='tight')
    plt.close()


def create_best_cat_skymap_page(results, cat_names, pdf, base_path='/eos/project-e/ep-nu/evilla/sn-pointing'):
    """Create a skymap showing true direction, EMCEE best-fit, and electron directions.
    
    Uses EMCEE results which are the primary analysis outputs.
    Shows individual electron directions from ES main tracks if available.
    """
    from matplotlib.patches import Circle, Ellipse
    import matplotlib.patches as mpatches
    
    scenario = 'perfect_ct'
    
    if scenario not in results or not results[scenario]:
        print(f"  Skipping skymap: no results for {scenario}")
        return
    
    print(f"  Found {len(results[scenario])} results for {scenario} (from EMCEE summary)")
    
    # Find best cat (lowest angular error) that has EMCEE data
    errors = np.array(results[scenario])
    cats = cat_names[scenario]
    base = Path(base_path)
    
    # Sort by error and find first cat with emcee data
    sorted_indices = np.argsort(errors)
    best_cat = None
    best_error = None
    emcee_file = None
    reg_file = None
    
    for idx in sorted_indices[:20]:  # Check top 20 cats
        candidate_cat = cats[idx]
        cat_dir = base / candidate_cat / 'pipeline'
        candidate_emcee = cat_dir / f"{candidate_cat}_scenario_{scenario}_emcee.npz"
        candidate_reg = cat_dir / f"{candidate_cat}_scenario_{scenario}.npz"
        
        if candidate_emcee.exists() and candidate_reg.exists():
            best_cat = candidate_cat
            best_error = errors[idx]
            emcee_file = candidate_emcee
            reg_file = candidate_reg
            break
    
    if best_cat is None:
        print(f"  Skipping skymap: no cats with available EMCEE data files")
        return
    
    # Load EMCEE data (summary)
    emcee_data = np.load(emcee_file)
    true_dir = np.array([
        emcee_data[f'{scenario}_emcee_true_nu_px'],
        emcee_data[f'{scenario}_emcee_true_nu_py'],
        emcee_data[f'{scenario}_emcee_true_nu_pz']
    ])
    emcee_best_dir = np.array([
        emcee_data[f'{scenario}_emcee_best_dir_x'],
        emcee_data[f'{scenario}_emcee_best_dir_y'],
        emcee_data[f'{scenario}_emcee_best_dir_z']
    ])
    omega_68 = float(emcee_data[f'{scenario}_emcee_omega_68'])
    n_clusters = int(emcee_data[f'{scenario}_emcee_n_clusters_used'])
    
    # Load regular file for MCMC chain visualization (for spread)
    reg_data = np.load(reg_file)
    mcmc_chain = reg_data[f'{scenario}_mcmc_chain']
    
    print(f"  Using best available cat: {best_cat}")
    print(f"  EMCEE error: {best_error:.2f}°, omega_68: {omega_68:.2f}°")
    print(f"  N ES clusters used: {n_clusters}")
    print(f"  Loading data from EMCEE file and regular file for visualization")
    
    # Normalize directions
    true_dir_norm = true_dir / np.linalg.norm(true_dir)
    emcee_best_norm = emcee_best_dir / np.linalg.norm(emcee_best_dir)
    
    # Try to load electron directions from cluster images
    electron_dirs = []
    cluster_dir = base / best_cat / f'{best_cat}_cluster_images_tick3_ch2_min2_tot3_e3p0'
    
    if cluster_dir.exists():
        # Load ES files and extract directions
        es_files = list(cluster_dir.glob('*/es_*.npz'))
        print(f"  Found {len(es_files)} ES electron files, loading directions...")
        
        for es_file in es_files[:min(len(es_files), 100)]:  # Limit for performance
            try:
                es_data = np.load(es_file)
                metadata = es_data['metadata']
                # Extract directions from metadata
                # Columns typically: [id, tick, ch, plane, energy, x, y, z, px, py, pz, ...]
                # Try columns 8-10 for px, py, pz (momentum/direction)
                for row in metadata:
                    if len(row) >= 11:
                        px, py, pz = row[8], row[9], row[10]
                        if np.sqrt(px**2 + py**2 + pz**2) > 0:
                            electron_dirs.append([px, py, pz])
            except:
                pass
    
    if len(electron_dirs) > 0:
        electron_dirs = np.array(electron_dirs)
        # Normalize
        electron_dirs_norm = electron_dirs / np.linalg.norm(electron_dirs, axis=1, keepdims=True)
        print(f"  Loaded {len(electron_dirs_norm)} electron directions")
    else:
        # Use MCMC samples as fallback
        n_samples = len(mcmc_chain)
        burnin = n_samples // 2
        electron_dirs_norm = mcmc_chain[burnin:] / np.linalg.norm(mcmc_chain[burnin:], axis=1, keepdims=True)
        print(f"  Using {len(electron_dirs_norm)} MCMC samples as electron directions (fallback)")
    
    # Convert to spherical coordinates
    def cart_to_sph(dirs):
        if dirs.ndim == 1:
            dirs = dirs.reshape(1, -1)
        x, y, z = dirs[:, 0], dirs[:, 1], dirs[:, 2]
        theta = np.arccos(np.clip(z, -1, 1))
        phi = np.arctan2(y, x)
        return theta, phi
    
    true_theta, true_phi = cart_to_sph(true_dir_norm)
    emcee_theta, emcee_phi = cart_to_sph(emcee_best_norm)
    electron_theta, electron_phi = cart_to_sph(electron_dirs_norm)
    
    # Create figure with Mollweide projection
    fig = plt.figure(figsize=(18, 10))
    fig.patch.set_facecolor('#1a1a2e')  # Dark blue background
    
    # Mollweide projection (full sky)
    ax1 = plt.subplot(121, projection='mollweide')
    ax1.set_facecolor('#0f0f1e')  # Darker blue for sky
    
    # Plot electron directions (convert theta to latitude: pi/2 - theta)
    # Mollweide expects longitude in [-pi, pi] and latitude in [-pi/2, pi/2]
    elec_lat = np.pi/2 - electron_theta
    elec_lon = electron_phi
    
    ax1.scatter(elec_lon, elec_lat, c='#FFD700', alpha=0.3, s=3, 
               label=f'Electrons (N={len(electron_dirs_norm)})', rasterized=True, zorder=5)
    
    # Plot true direction as a red star
    true_lat = np.pi/2 - true_theta[0]
    true_lon = true_phi[0]
    ax1.scatter(true_lon, true_lat, marker='*', c='red', s=600, 
               edgecolors='white', linewidths=2.5, label='True ν Direction', zorder=10)
    
    # Plot EMCEE best-fit as a yellow star
    emcee_lat = np.pi/2 - emcee_theta[0]
    emcee_lon = emcee_phi[0]
    ax1.scatter(emcee_lon, emcee_lat, marker='*', c='#FFD700', s=500, 
               edgecolors='black', linewidths=2, label=f'EMCEE Best ({best_error:.2f}°)', zorder=10)
    
    ax1.set_title(f'Sky Map: Best Cat ({best_cat})', 
                 fontsize=14, fontweight='bold', color='white')
    ax1.grid(True, alpha=0.2, color='white')
    ax1.legend(fontsize=11, loc='upper left', facecolor='#1a1a2e', edgecolor='white', 
              labelcolor='white', framealpha=0.9)
    
    # Zoomed view around true direction (±30° cone)
    ax2 = plt.subplot(122)
    ax2.set_facecolor('#0f0f1e')
    
    # Calculate angular separation from true direction for electrons
    cos_sep = electron_dirs_norm @ true_dir_norm
    ang_sep = np.degrees(np.arccos(np.clip(cos_sep, -1, 1)))
    
    # Select electrons within 30° of true direction
    zoom_angle = 30.0
    zoom_mask = ang_sep <= zoom_angle
    zoom_electrons = electron_dirs_norm[zoom_mask]
    
    if len(zoom_electrons) > 0:
        # Project onto tangent plane at true direction
        # Use gnomonic projection (tangent plane)
        def gnomonic_project(dirs, center):
            """Project directions onto tangent plane at center."""
            # center should be normalized
            cos_ang = dirs @ center
            # Avoid division by zero
            cos_ang = np.maximum(cos_ang, 0.01)
            scale = 1.0 / cos_ang
            
            # Create orthonormal basis on tangent plane
            # First basis vector
            if abs(center[2]) < 0.9:
                e1 = np.array([0, 0, 1])
            else:
                e1 = np.array([1, 0, 0])
            e1 = e1 - (e1 @ center) * center
            e1 = e1 / np.linalg.norm(e1)
            
            # Second basis vector
            e2 = np.cross(center, e1)
            e2 = e2 / np.linalg.norm(e2)
            
            # Project
            x = (dirs @ e1) * scale
            y = (dirs @ e2) * scale
            return x, y
        
        zoom_x, zoom_y = gnomonic_project(zoom_electrons, true_dir_norm)
        
        # Plot electrons in yellow
        ax2.scatter(zoom_x, zoom_y, c='#FFD700', alpha=0.4, s=8, 
                   label=f'Electrons (N={len(zoom_electrons)})', rasterized=True, zorder=5)
        
        # Plot EMCEE best-fit
        emcee_x, emcee_y = gnomonic_project(emcee_best_norm.reshape(1, -1), true_dir_norm)
        ax2.scatter(emcee_x, emcee_y, marker='*', c='#FFD700', s=500, 
                   edgecolors='black', linewidths=2, label=f'EMCEE Best', zorder=10)
        
        # Plot true direction at origin
        ax2.scatter(0, 0, marker='*', c='red', s=600, 
                   edgecolors='white', linewidths=2.5, label='True ν', zorder=10)
        
        # Add circles for angular scales
        for radius_deg in [5, 10, 15, 20, 25, 30]:
            radius_rad = np.radians(radius_deg)
            circle = Circle((0, 0), np.tan(radius_rad), fill=False, 
                          edgecolor='white', linestyle='--', linewidth=1, alpha=0.3)
            ax2.add_patch(circle)
            ax2.text(np.tan(radius_rad) * 1.05, 0, f'{radius_deg}°', 
                    fontsize=9, color='white', ha='left', va='center', 
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='#1a1a2e', alpha=0.7, edgecolor='none'))
        
        # Add omega_68 circle around EMCEE best
        if omega_68 < zoom_angle:
            omega_circle = Circle((emcee_x[0], emcee_y[0]), np.tan(np.radians(omega_68)), 
                                fill=False, edgecolor='#FFD700', linestyle='-', linewidth=2, 
                                alpha=0.7, label=f'68% CL (ω₆₈={omega_68:.2f}°)')
            ax2.add_patch(omega_circle)
        
        ax2.set_xlabel('Tangent Plane X', fontsize=12, fontweight='bold', color='white')
        ax2.set_ylabel('Tangent Plane Y', fontsize=12, fontweight='bold', color='white')
        ax2.set_title(f'Zoomed View (±{zoom_angle:.0f}° cone)\nEMCEE Error: {best_error:.2f}°', 
                     fontsize=14, fontweight='bold', color='white')
        ax2.set_aspect('equal')
        ax2.grid(True, alpha=0.2, color='white')
        ax2.legend(fontsize=11, facecolor='#1a1a2e', edgecolor='white', 
                  labelcolor='white', framealpha=0.9, loc='upper right')
        ax2.tick_params(colors='white')
        
        # Set limits
        max_rad = np.tan(np.radians(zoom_angle)) * 1.1
        ax2.set_xlim(-max_rad, max_rad)
        ax2.set_ylim(-max_rad, max_rad)
    
    fig.text(0.5, 0.03, 
            f'Best cat from EMCEE analysis: {best_cat} | Angular Error: {best_error:.2f}° | '
            f'68% Credible Interval (ω₆₈): {omega_68:.2f}° | N electrons: {n_clusters}',
            ha='center', fontsize=11, color='white', style='italic',
            bbox=dict(boxstyle='round,pad=0.8', facecolor='#1a1a2e', alpha=0.9, edgecolor='white', linewidth=2))
    
    plt.suptitle(f'Neutrino Pointing Reconstruction: {best_cat} - Perfect CT Scenario\n'
                f'Yellow: Electrons | Red: True Neutrino Direction', 
                fontsize=16, fontweight='bold', y=0.98, color='white')
    
    print(f"  Saving skymap page to PDF...")
    pdf.savefig(fig, bbox_inches='tight', dpi=150)
    print(f"  Skymap saved, closing figure...")
    plt.close()
    print(f"  Skymap page complete")


def create_bias_analysis_page(results, cat_names, pdf, base_path='/eos/project-e/ep-nu/evilla/sn-pointing'):
    """Analyze directional bias across all cats."""
    scenario = 'perfect_ct'
    
    if scenario not in results or not results[scenario]:
        return
    
    base = Path(base_path)
    
    # Collect reconstructed and true directions for all cats
    recon_dirs = []
    true_dirs = []
    cat_list = []
    
    for cat_name in cat_names[scenario]:
        cat_dir = base / cat_name / 'pipeline'
        data_file = cat_dir / f"{cat_name}_scenario_{scenario}.npz"
        
        if data_file.exists():
            try:
                data = np.load(data_file)
                true_dir = data[f'{scenario}_true_nu_direction']
                recon_dir = data[f'{scenario}_reconstructed_direction']
                
                # Normalize
                true_dir_norm = true_dir / np.linalg.norm(true_dir)
                recon_dir_norm = recon_dir / np.linalg.norm(recon_dir)
                
                true_dirs.append(true_dir_norm)
                recon_dirs.append(recon_dir_norm)
                cat_list.append(cat_name)
            except:
                pass
    
    if len(true_dirs) == 0:
        return
    
    true_dirs = np.array(true_dirs)
    recon_dirs = np.array(recon_dirs)
    
    # Calculate bias vectors (recon - true) in Cartesian coordinates
    bias_vectors = recon_dirs - true_dirs
    
    # Calculate bias magnitudes
    bias_mags = np.linalg.norm(bias_vectors, axis=1)
    
    # Calculate mean bias vector
    mean_bias = np.mean(bias_vectors, axis=0)
    mean_bias_mag = np.linalg.norm(mean_bias)
    
    # Create figure
    fig = plt.figure(figsize=(18, 12))
    
    # 1. Bias magnitude distribution
    ax1 = plt.subplot(2, 3, 1)
    ax1.hist(bias_mags, bins=40, alpha=0.7, color='#3498DB', edgecolor='black', linewidth=1)
    ax1.axvline(np.mean(bias_mags), color='red', linestyle='--', linewidth=2, 
               label=f'Mean: {np.mean(bias_mags):.4f}')
    ax1.axvline(np.median(bias_mags), color='orange', linestyle='--', linewidth=2,
               label=f'Median: {np.median(bias_mags):.4f}')
    ax1.set_xlabel('Bias Magnitude', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Count', fontsize=11, fontweight='bold')
    ax1.set_title(f'Distribution of Bias Magnitudes (N={len(bias_mags)} cats)', 
                 fontsize=12, fontweight='bold')
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3)
    
    # 2. Bias in X component
    ax2 = plt.subplot(2, 3, 2)
    ax2.hist(bias_vectors[:, 0], bins=40, alpha=0.7, color='#E74C3C', edgecolor='black', linewidth=1)
    ax2.axvline(mean_bias[0], color='red', linestyle='--', linewidth=2,
               label=f'Mean: {mean_bias[0]:.4f}')
    ax2.axvline(0, color='black', linestyle='-', linewidth=1, alpha=0.5)
    ax2.set_xlabel('Bias in X', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Count', fontsize=11, fontweight='bold')
    ax2.set_title('X-Component Bias', fontsize=12, fontweight='bold')
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3)
    
    # 3. Bias in Y component
    ax3 = plt.subplot(2, 3, 3)
    ax3.hist(bias_vectors[:, 1], bins=40, alpha=0.7, color='#2ECC71', edgecolor='black', linewidth=1)
    ax3.axvline(mean_bias[1], color='red', linestyle='--', linewidth=2,
               label=f'Mean: {mean_bias[1]:.4f}')
    ax3.axvline(0, color='black', linestyle='-', linewidth=1, alpha=0.5)
    ax3.set_xlabel('Bias in Y', fontsize=11, fontweight='bold')
    ax3.set_ylabel('Count', fontsize=11, fontweight='bold')
    ax3.set_title('Y-Component Bias', fontsize=12, fontweight='bold')
    ax3.legend(fontsize=10)
    ax3.grid(True, alpha=0.3)
    
    # 4. Bias in Z component
    ax4 = plt.subplot(2, 3, 4)
    ax4.hist(bias_vectors[:, 2], bins=40, alpha=0.7, color='#9B59B6', edgecolor='black', linewidth=1)
    ax4.axvline(mean_bias[2], color='red', linestyle='--', linewidth=2,
               label=f'Mean: {mean_bias[2]:.4f}')
    ax4.axvline(0, color='black', linestyle='-', linewidth=1, alpha=0.5)
    ax4.set_xlabel('Bias in Z', fontsize=11, fontweight='bold')
    ax4.set_ylabel('Count', fontsize=11, fontweight='bold')
    ax4.set_title('Z-Component Bias', fontsize=12, fontweight='bold')
    ax4.legend(fontsize=10)
    ax4.grid(True, alpha=0.3)
    
    # 5. 2D scatter: Bias X vs Y
    ax5 = plt.subplot(2, 3, 5)
    scatter = ax5.scatter(bias_vectors[:, 0], bias_vectors[:, 1], 
                         c=bias_mags, cmap='viridis', alpha=0.6, s=20)
    ax5.scatter(mean_bias[0], mean_bias[1], marker='*', c='red', s=300,
               edgecolors='black', linewidths=2, label='Mean Bias', zorder=10)
    ax5.axhline(0, color='black', linestyle='-', linewidth=0.5, alpha=0.5)
    ax5.axvline(0, color='black', linestyle='-', linewidth=0.5, alpha=0.5)
    ax5.set_xlabel('Bias X', fontsize=11, fontweight='bold')
    ax5.set_ylabel('Bias Y', fontsize=11, fontweight='bold')
    ax5.set_title('Bias: X vs Y Components', fontsize=12, fontweight='bold')
    ax5.legend(fontsize=10)
    ax5.grid(True, alpha=0.3)
    ax5.set_aspect('equal')
    cbar = plt.colorbar(scatter, ax=ax5)
    cbar.set_label('Bias Magnitude', fontsize=10)
    
    # 6. 2D scatter: Bias X vs Z
    ax6 = plt.subplot(2, 3, 6)
    scatter = ax6.scatter(bias_vectors[:, 0], bias_vectors[:, 2], 
                         c=bias_mags, cmap='viridis', alpha=0.6, s=20)
    ax6.scatter(mean_bias[0], mean_bias[2], marker='*', c='red', s=300,
               edgecolors='black', linewidths=2, label='Mean Bias', zorder=10)
    ax6.axhline(0, color='black', linestyle='-', linewidth=0.5, alpha=0.5)
    ax6.axvline(0, color='black', linestyle='-', linewidth=0.5, alpha=0.5)
    ax6.set_xlabel('Bias X', fontsize=11, fontweight='bold')
    ax6.set_ylabel('Bias Z', fontsize=11, fontweight='bold')
    ax6.set_title('Bias: X vs Z Components', fontsize=12, fontweight='bold')
    ax6.legend(fontsize=10)
    ax6.grid(True, alpha=0.3)
    ax6.set_aspect('equal')
    cbar = plt.colorbar(scatter, ax=ax6)
    cbar.set_label('Bias Magnitude', fontsize=10)
    
    plt.suptitle(f'Directional Bias Analysis (Perfect CT) - Cartesian Components\nMean Bias Vector: ({mean_bias[0]:.4f}, {mean_bias[1]:.4f}, {mean_bias[2]:.4f}), Magnitude: {mean_bias_mag:.4f}', 
                fontsize=16, fontweight='bold', y=0.995)
    
    plt.tight_layout()
    pdf.savefig(fig, bbox_inches='tight')
    plt.close()


def create_angular_bias_analysis_page(results, cat_names, pdf, base_path='/eos/project-e/ep-nu/evilla/sn-pointing'):
    """Analyze angular bias in spherical coordinates (θ, φ) for perfect_ct scenario."""
    scenario = 'perfect_ct'
    
    if scenario not in results or not results[scenario]:
        return
    
    base = Path(base_path)
    
    # Collect reconstructed and true directions for all cats
    recon_dirs = []
    true_dirs = []
    angular_errors = []
    cat_list = []
    
    for cat_name in cat_names[scenario]:
        cat_dir = base / cat_name / 'pipeline'
        data_file = cat_dir / f"{cat_name}_scenario_{scenario}.npz"
        
        if data_file.exists():
            try:
                data = np.load(data_file)
                true_dir = data[f'{scenario}_true_nu_direction']
                recon_dir = data[f'{scenario}_reconstructed_direction']
                
                # Normalize
                true_dir_norm = true_dir / np.linalg.norm(true_dir)
                recon_dir_norm = recon_dir / np.linalg.norm(recon_dir)
                
                true_dirs.append(true_dir_norm)
                recon_dirs.append(recon_dir_norm)
                cat_list.append(cat_name)
                
                # Calculate angular error
                cos_angle = np.clip(np.dot(true_dir_norm, recon_dir_norm), -1, 1)
                angular_errors.append(np.degrees(np.arccos(cos_angle)))
            except:
                pass
    
    if len(true_dirs) == 0:
        return
    
    true_dirs = np.array(true_dirs)
    recon_dirs = np.array(recon_dirs)
    angular_errors = np.array(angular_errors)
    
    def cart_to_spherical(dirs):
        """Convert Cartesian to spherical (θ from z-axis, φ from x-axis)."""
        x, y, z = dirs[:, 0], dirs[:, 1], dirs[:, 2]
        r = np.sqrt(x**2 + y**2 + z**2)
        theta = np.arccos(np.clip(z / r, -1, 1))  # polar angle from z-axis [0, π]
        phi = np.arctan2(y, x)  # azimuthal angle from x-axis [-π, π]
        return np.degrees(theta), np.degrees(phi)
    
    # Convert to spherical coordinates
    true_theta, true_phi = cart_to_spherical(true_dirs)
    recon_theta, recon_phi = cart_to_spherical(recon_dirs)
    
    # Calculate angular biases
    theta_bias = recon_theta - true_theta  # bias in polar angle
    phi_bias = recon_phi - true_phi  # bias in azimuthal angle
    
    # Wrap phi_bias to [-180, 180]
    phi_bias = np.where(phi_bias > 180, phi_bias - 360, phi_bias)
    phi_bias = np.where(phi_bias < -180, phi_bias + 360, phi_bias)
    
    # Calculate mean biases
    mean_theta_bias = np.mean(theta_bias)
    mean_phi_bias = np.mean(phi_bias)
    median_theta_bias = np.median(theta_bias)
    median_phi_bias = np.median(phi_bias)
    
    # Create figure
    fig = plt.figure(figsize=(18, 12))
    
    # 1. Theta bias distribution
    ax1 = plt.subplot(2, 3, 1)
    ax1.hist(theta_bias, bins=40, alpha=0.7, color='#E74C3C', edgecolor='black', linewidth=1)
    ax1.axvline(mean_theta_bias, color='red', linestyle='--', linewidth=2.5, 
               label=f'Mean: {mean_theta_bias:.2f}°')
    ax1.axvline(median_theta_bias, color='orange', linestyle='--', linewidth=2,
               label=f'Median: {median_theta_bias:.2f}°')
    ax1.axvline(0, color='black', linestyle='-', linewidth=1, alpha=0.5)
    ax1.set_xlabel('Bias in θ (degrees)', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Count', fontsize=11, fontweight='bold')
    ax1.set_title(f'Polar Angle (θ) Bias Distribution\nStd: {np.std(theta_bias):.2f}°', 
                 fontsize=12, fontweight='bold')
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3)
    
    # 2. Phi bias distribution
    ax2 = plt.subplot(2, 3, 2)
    ax2.hist(phi_bias, bins=40, alpha=0.7, color='#3498DB', edgecolor='black', linewidth=1)
    ax2.axvline(mean_phi_bias, color='red', linestyle='--', linewidth=2.5, 
               label=f'Mean: {mean_phi_bias:.2f}°')
    ax2.axvline(median_phi_bias, color='orange', linestyle='--', linewidth=2,
               label=f'Median: {median_phi_bias:.2f}°')
    ax2.axvline(0, color='black', linestyle='-', linewidth=1, alpha=0.5)
    ax2.set_xlabel('Bias in φ (degrees)', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Count', fontsize=11, fontweight='bold')
    ax2.set_title(f'Azimuthal Angle (φ) Bias Distribution\nStd: {np.std(phi_bias):.2f}°', 
                 fontsize=12, fontweight='bold')
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3)
    
    # 3. Angular error distribution (for reference)
    ax3 = plt.subplot(2, 3, 3)
    ax3.hist(angular_errors, bins=40, alpha=0.7, color='#2ECC71', edgecolor='black', linewidth=1)
    ax3.axvline(np.mean(angular_errors), color='red', linestyle='--', linewidth=2.5,
               label=f'Mean: {np.mean(angular_errors):.2f}°')
    ax3.axvline(np.median(angular_errors), color='orange', linestyle='--', linewidth=2,
               label=f'Median: {np.median(angular_errors):.2f}°')
    ax3.set_xlabel('Total Angular Error (degrees)', fontsize=11, fontweight='bold')
    ax3.set_ylabel('Count', fontsize=11, fontweight='bold')
    ax3.set_title(f'Total Angular Error\n68th %ile: {np.percentile(angular_errors, 68):.2f}°', 
                 fontsize=12, fontweight='bold')
    ax3.legend(fontsize=10)
    ax3.grid(True, alpha=0.3)
    
    # 4. 2D scatter: Theta bias vs True theta
    ax4 = plt.subplot(2, 3, 4)
    scatter = ax4.scatter(true_theta, theta_bias, c=angular_errors, cmap='plasma', 
                         alpha=0.6, s=30, edgecolors='black', linewidths=0.5)
    ax4.axhline(0, color='black', linestyle='-', linewidth=1, alpha=0.5)
    ax4.axhline(mean_theta_bias, color='red', linestyle='--', linewidth=2, alpha=0.7,
               label=f'Mean bias: {mean_theta_bias:.2f}°')
    ax4.set_xlabel('True θ (degrees)', fontsize=11, fontweight='bold')
    ax4.set_ylabel('Bias in θ (degrees)', fontsize=11, fontweight='bold')
    ax4.set_title('θ Bias vs True θ', fontsize=12, fontweight='bold')
    ax4.legend(fontsize=9)
    ax4.grid(True, alpha=0.3)
    cbar = plt.colorbar(scatter, ax=ax4)
    cbar.set_label('Angular Error (°)', fontsize=9)
    
    # 5. 2D scatter: Phi bias vs True phi
    ax5 = plt.subplot(2, 3, 5)
    scatter = ax5.scatter(true_phi, phi_bias, c=angular_errors, cmap='plasma', 
                         alpha=0.6, s=30, edgecolors='black', linewidths=0.5)
    ax5.axhline(0, color='black', linestyle='-', linewidth=1, alpha=0.5)
    ax5.axhline(mean_phi_bias, color='red', linestyle='--', linewidth=2, alpha=0.7,
               label=f'Mean bias: {mean_phi_bias:.2f}°')
    ax5.set_xlabel('True φ (degrees)', fontsize=11, fontweight='bold')
    ax5.set_ylabel('Bias in φ (degrees)', fontsize=11, fontweight='bold')
    ax5.set_title('φ Bias vs True φ', fontsize=12, fontweight='bold')
    ax5.legend(fontsize=9)
    ax5.grid(True, alpha=0.3)
    cbar = plt.colorbar(scatter, ax=ax5)
    cbar.set_label('Angular Error (°)', fontsize=9)
    
    # 6. 2D scatter: Theta bias vs Phi bias
    ax6 = plt.subplot(2, 3, 6)
    scatter = ax6.scatter(theta_bias, phi_bias, c=angular_errors, cmap='plasma', 
                         alpha=0.6, s=30, edgecolors='black', linewidths=0.5)
    ax6.scatter(mean_theta_bias, mean_phi_bias, marker='*', c='red', s=400,
               edgecolors='black', linewidths=2, label=f'Mean bias\n(θ={mean_theta_bias:.2f}°, φ={mean_phi_bias:.2f}°)', 
               zorder=10)
    ax6.axhline(0, color='black', linestyle='-', linewidth=0.5, alpha=0.5)
    ax6.axvline(0, color='black', linestyle='-', linewidth=0.5, alpha=0.5)
    ax6.set_xlabel('Bias in θ (degrees)', fontsize=11, fontweight='bold')
    ax6.set_ylabel('Bias in φ (degrees)', fontsize=11, fontweight='bold')
    ax6.set_title('θ Bias vs φ Bias Correlation', fontsize=12, fontweight='bold')
    ax6.legend(fontsize=9, loc='best')
    ax6.grid(True, alpha=0.3)
    ax6.set_aspect('equal')
    cbar = plt.colorbar(scatter, ax=ax6)
    cbar.set_label('Angular Error (°)', fontsize=9)
    
    # Add summary statistics text
    stats_text = (
        f'Angular Bias Statistics (N={len(angular_errors)} cats):\n'
        f'θ bias: mean={mean_theta_bias:.2f}°, median={median_theta_bias:.2f}°, std={np.std(theta_bias):.2f}°\n'
        f'φ bias: mean={mean_phi_bias:.2f}°, median={median_phi_bias:.2f}°, std={np.std(phi_bias):.2f}°\n'
        f'Total angular error: mean={np.mean(angular_errors):.2f}°, 68th %ile={np.percentile(angular_errors, 68):.2f}°'
    )
    
    plt.suptitle(f'Angular Bias Analysis in Spherical Coordinates (Perfect CT)\n'
                f'θ = polar angle from z-axis [0°, 180°], φ = azimuthal angle from x-axis [-180°, 180°]', 
                fontsize=16, fontweight='bold', y=0.995)
    
    fig.text(0.5, 0.02, stats_text, ha='center', fontsize=10, family='monospace',
            bbox=dict(boxstyle='round,pad=0.8', facecolor='wheat', alpha=0.8))
    
    plt.tight_layout(rect=[0, 0.06, 1, 0.98])
    pdf.savefig(fig, bbox_inches='tight')
    plt.close()


def create_file_cluster_stats_page(cat_file_stats, pdf):
    """Create a page showing distributions of files and clusters per cat"""
    fig = plt.figure(figsize=(18, 10))
    
    # Get data
    es_files = np.array(cat_file_stats['es_files'])
    cc_files = np.array(cat_file_stats['cc_files'])
    es_clusters = np.array(cat_file_stats['es_clusters'])
    cc_clusters = np.array(cat_file_stats['cc_clusters'])
    
    # 1. ES Files per cat
    ax1 = plt.subplot(2, 2, 1)
    ax1.hist(es_files, bins=30, alpha=0.7, color='#2E7D32', edgecolor='black', linewidth=1)
    ax1.axvline(np.mean(es_files), color='red', linestyle='--', linewidth=2, label=f'Mean: {np.mean(es_files):.1f}')
    ax1.axvline(np.median(es_files), color='blue', linestyle='--', linewidth=2, label=f'Median: {np.median(es_files):.1f}')
    ax1.set_xlabel('Number of ES Files', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Number of Cats', fontsize=12, fontweight='bold')
    ax1.set_title(f'ES Files per Cat (N={len(es_files)} cats)', fontsize=13, fontweight='bold')
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.text(0.98, 0.97, f'Std: {np.std(es_files):.1f}\nMin: {np.min(es_files):.0f}\nMax: {np.max(es_files):.0f}',
             transform=ax1.transAxes, fontsize=9, verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # 2. CC Files per cat
    ax2 = plt.subplot(2, 2, 2)
    ax2.hist(cc_files, bins=30, alpha=0.7, color='#1976D2', edgecolor='black', linewidth=1)
    ax2.axvline(np.mean(cc_files), color='red', linestyle='--', linewidth=2, label=f'Mean: {np.mean(cc_files):.1f}')
    ax2.axvline(np.median(cc_files), color='blue', linestyle='--', linewidth=2, label=f'Median: {np.median(cc_files):.1f}')
    ax2.set_xlabel('Number of CC Files', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Number of Cats', fontsize=12, fontweight='bold')
    ax2.set_title(f'CC Files per Cat (N={len(cc_files)} cats)', fontsize=13, fontweight='bold')
    ax2.legend(fontsize=10)
    ax2.grid(True, alpha=0.3)
    ax2.text(0.98, 0.97, f'Std: {np.std(cc_files):.1f}\nMin: {np.min(cc_files):.0f}\nMax: {np.max(cc_files):.0f}',
             transform=ax2.transAxes, fontsize=9, verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # 3. ES Clusters per cat (all planes)
    ax3 = plt.subplot(2, 2, 3)
    ax3.hist(es_clusters, bins=30, alpha=0.7, color='#388E3C', edgecolor='black', linewidth=1)
    ax3.axvline(np.mean(es_clusters), color='red', linestyle='--', linewidth=2, label=f'Mean: {np.mean(es_clusters):.1f}')
    ax3.axvline(np.median(es_clusters), color='blue', linestyle='--', linewidth=2, label=f'Median: {np.median(es_clusters):.1f}')
    ax3.set_xlabel('Number of ES Cluster Files (all planes)', fontsize=12, fontweight='bold')
    ax3.set_ylabel('Number of Cats', fontsize=12, fontweight='bold')
    ax3.set_title(f'ES Cluster Files per Cat (N={len(es_clusters)} cats)', fontsize=13, fontweight='bold')
    ax3.legend(fontsize=10)
    ax3.grid(True, alpha=0.3)
    ax3.text(0.98, 0.97, f'Std: {np.std(es_clusters):.1f}\nMin: {np.min(es_clusters):.0f}\nMax: {np.max(es_clusters):.0f}',
             transform=ax3.transAxes, fontsize=9, verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # 4. CC Clusters per cat (all planes)
    ax4 = plt.subplot(2, 2, 4)
    ax4.hist(cc_clusters, bins=30, alpha=0.7, color='#1565C0', edgecolor='black', linewidth=1)
    ax4.axvline(np.mean(cc_clusters), color='red', linestyle='--', linewidth=2, label=f'Mean: {np.mean(cc_clusters):.1f}')
    ax4.axvline(np.median(cc_clusters), color='blue', linestyle='--', linewidth=2, label=f'Median: {np.median(cc_clusters):.1f}')
    ax4.set_xlabel('Number of CC Cluster Files (all planes)', fontsize=12, fontweight='bold')
    ax4.set_ylabel('Number of Cats', fontsize=12, fontweight='bold')
    ax4.set_title(f'CC Cluster Files per Cat (N={len(cc_clusters)} cats)', fontsize=13, fontweight='bold')
    ax4.legend(fontsize=10)
    ax4.grid(True, alpha=0.3)
    ax4.text(0.98, 0.97, f'Std: {np.std(cc_clusters):.1f}\nMin: {np.min(cc_clusters):.0f}\nMax: {np.max(cc_clusters):.0f}',
             transform=ax4.transAxes, fontsize=9, verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    plt.suptitle('Input Data Statistics: Files and Clusters per Cat', 
                fontsize=16, fontweight='bold', y=0.995)
    
    # Add note
    note_text = ('Note: "Files" = unique clusters (counted once across all planes). '
                 '"Cluster Files" = all plane files (U, V, X) for each cluster (typically 3x files).')
    fig.text(0.5, 0.02, note_text, ha='center', fontsize=10, style='italic', color='#555',
             bbox=dict(boxstyle='round,pad=0.8', facecolor='#fffacd', alpha=0.6))
    
    plt.tight_layout()
    pdf.savefig(fig, bbox_inches='tight')
    plt.close()


def plot_aggregate_analysis(results, cat_names, cos_theta_results, cluster_tracking, cat_file_stats, true_directions):
    """Create comprehensive aggregate analysis plots."""
    
    # Convert to arrays and calculate statistics
    stats = {}
    for scenario in SCENARIOS:
        if results[scenario]:
            arr = np.array(results[scenario])
            cos_arr = np.array(cos_theta_results[scenario])
            q68_cos = np.percentile(cos_arr, 68)
            q68_angle = np.percentile(arr, 68)  # 68% quantile of angular error
            stats[scenario] = {
                'data': arr,
                'mean': np.mean(arr),
                'median': np.median(arr),
                'std': np.std(arr),
                'n': len(arr),
                'min': np.min(arr),
                'max': np.max(arr),
                'q25': np.percentile(arr, 25),
                'q68': q68_angle,  # 68% quantile - PRIMARY METRIC
                'q75': np.percentile(arr, 75),
                'cos_theta': cos_arr,
                'cos_theta_68': q68_cos
            }
        else:
            stats[scenario] = None
    
    # Create figure with subplots
    fig = plt.figure(figsize=(18, 12))
    
    # 1. Box plot comparison
    ax1 = plt.subplot(2, 3, 1)
    plot_data = []
    plot_labels = []
    plot_colors = []
    colors = plt.cm.Set3(np.linspace(0, 1, len(SCENARIOS)))
    
    for i, scenario in enumerate(SCENARIOS):
        if stats[scenario] is not None:
            plot_data.append(stats[scenario]['data'])
            plot_labels.append(SCENARIO_LABELS[scenario])
            plot_colors.append(colors[i])
    
    bp = ax1.boxplot(plot_data, labels=plot_labels, patch_artist=True, 
                     notch=True, showmeans=True)
    for patch, color in zip(bp['boxes'], plot_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    
    ax1.set_ylabel('Angular Error (degrees)', fontsize=11, fontweight='bold')
    ax1.set_title('Angular Resolution Comparison', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='y')
    ax1.tick_params(axis='x', rotation=45, labelsize=9)
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # 2. Statistics table
    ax2 = plt.subplot(2, 3, 2)
    ax2.axis('off')
    
    table_data = []
    for scenario in SCENARIOS:
        if stats[scenario] is not None:
            s = stats[scenario]
            table_data.append([
                SCENARIO_LABELS[scenario],
                f"{s['n']}",
                f"{s['q68']:.2f}°",  # 68% quantile as primary metric
                f"{s['median']:.2f}°",
                f"{s['mean']:.2f}°"
            ])
    
    table = ax2.table(cellText=table_data,
                     colLabels=['Scenario', 'N', '68% Q', 'Median', 'Mean'],
                     cellLoc='left',
                     loc='center',
                     bbox=[0, 0.1, 1, 0.8])
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 2.5)
    
    for i in range(5):
        table[(0, i)].set_facecolor('#4472C4')
        table[(0, i)].set_text_props(weight='bold', color='white')
    
    for i in range(1, len(table_data) + 1):
        for j in range(5):
            if i % 2 == 0:
                table[(i, j)].set_facecolor('#f0f0f0')
    
    ax2.set_title('Summary Statistics', fontsize=13, fontweight='bold', pad=20)
    
    # 3. Bar plot with error bars
    ax3 = plt.subplot(2, 3, 3)
    means = []
    stds = []
    labels = []
    bar_colors = []
    
    for i, scenario in enumerate(SCENARIOS):
        if stats[scenario] is not None:
            means.append(stats[scenario]['mean'])
            stds.append(stats[scenario]['std'])
            labels.append(SCENARIO_LABELS[scenario])
            bar_colors.append(colors[i])
    
    x_pos = np.arange(len(labels))
    bars = ax3.bar(x_pos, means, yerr=stds, capsize=5, alpha=0.8, 
                   color=bar_colors, edgecolor='black', linewidth=1.5)
    
    for i, (bar, mean, std) in enumerate(zip(bars, means, stds)):
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., height,
                f'{mean:.1f}°',
                ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    ax3.set_xticks(x_pos)
    ax3.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
    ax3.set_ylabel('Mean Angular Error (degrees)', fontsize=11, fontweight='bold')
    ax3.set_title('Mean Resolution ± Std Dev', fontsize=13, fontweight='bold')
    ax3.grid(True, alpha=0.3, axis='y')
    
    # 4. Histogram overlay
    ax4 = plt.subplot(2, 3, 4)
    for i, scenario in enumerate(SCENARIOS):
        if stats[scenario] is not None:
            ax4.hist(stats[scenario]['data'], bins=30, alpha=0.5, 
                    label=SCENARIO_LABELS[scenario], color=colors[i], 
                    edgecolor='black', linewidth=0.5)
    
    ax4.set_xlabel('Angular Error (degrees)', fontsize=11, fontweight='bold')
    ax4.set_ylabel('Count', fontsize=11, fontweight='bold')
    ax4.set_title('Distribution Overlay', fontsize=13, fontweight='bold')
    ax4.legend(fontsize=8, loc='upper right')
    ax4.grid(True, alpha=0.3)
    
    # 5. Cumulative distribution
    ax5 = plt.subplot(2, 3, 5)
    for i, scenario in enumerate(SCENARIOS):
        if stats[scenario] is not None:
            sorted_data = np.sort(stats[scenario]['data'])
            cumulative = np.arange(1, len(sorted_data) + 1) / len(sorted_data) * 100
            ax5.plot(sorted_data, cumulative, label=SCENARIO_LABELS[scenario], 
                    color=colors[i], linewidth=2.5, alpha=0.8)
    
    ax5.axhline(y=68, color='red', linestyle='--', alpha=0.6, linewidth=2, label='68% CL')
    ax5.set_xlabel('Angular Error (degrees)', fontsize=11, fontweight='bold')
    ax5.set_ylabel('Cumulative Percentage (%)', fontsize=11, fontweight='bold')
    ax5.set_title('Cumulative Distribution', fontsize=13, fontweight='bold')
    ax5.legend(fontsize=8, loc='lower right')
    ax5.grid(True, alpha=0.3)
    
    # 6. Violin plot
    ax6 = plt.subplot(2, 3, 6)
    parts = ax6.violinplot(plot_data, positions=range(len(plot_data)), 
                          showmeans=True, showmedians=True, widths=0.7)
    for pc, color in zip(parts['bodies'], plot_colors):
        pc.set_facecolor(color)
        pc.set_alpha(0.7)
    
    ax6.set_xticks(range(len(plot_labels)))
    ax6.set_xticklabels(plot_labels, rotation=45, ha='right', fontsize=9)
    ax6.set_ylabel('Angular Error (degrees)', fontsize=11, fontweight='bold')
    ax6.set_title('Distribution Shapes', fontsize=13, fontweight='bold')
    ax6.grid(True, alpha=0.3, axis='y')
    
    plt.suptitle('Emcee 6-Scenario Aggregate Analysis', 
                fontsize=16, fontweight='bold', y=0.995)
    plt.tight_layout()
    
    # Save first page to PDF
    output_png = 'emcee_6scenarios_aggregate_analysis.png'
    output_pdf = 'emcee_6scenarios_aggregate_analysis.pdf'
    plt.savefig(output_png, dpi=300, bbox_inches='tight')
    
    from matplotlib.backends.backend_pdf import PdfPages
    pdf = PdfPages(output_pdf)
    pdf.savefig(fig, bbox_inches='tight')
    plt.close()
    
    # Page 2: Cosine distributions with 68% quantile (full range -1 to 1)
    fig2 = plt.figure(figsize=(18, 10))
    
    for i, scenario in enumerate(SCENARIOS):
        if stats[scenario] is not None:
            ax = plt.subplot(2, 3, i+1)
            cos_data = stats[scenario]['cos_theta']
            q68 = stats[scenario]['cos_theta_68']
            
            # Histogram
            n, bins, patches = ax.hist(cos_data, bins=50, range=(-1, 1), alpha=0.7, 
                                       color=colors[i], edgecolor='black', linewidth=0.5)
            
            # 68% quantile line
            angle_q68 = np.degrees(np.arccos(np.clip(q68, -1, 1)))
            ax.axvline(q68, color='red', linestyle='--', linewidth=2.5, 
                      label=f'68% quantile: {q68:.4f} ({angle_q68:.1f}°)')
            
            # Mean line
            mean_cos = np.mean(cos_data)
            angle_mean = np.degrees(np.arccos(np.clip(mean_cos, -1, 1)))
            ax.axvline(mean_cos, color='blue', linestyle='-', linewidth=2, alpha=0.7,
                      label=f'Mean: {mean_cos:.4f} ({angle_mean:.1f}°)')
            
            ax.set_xlabel('cos(θ_true - θ_reco)', fontsize=10, fontweight='bold')
            ax.set_ylabel('Count', fontsize=10, fontweight='bold')
            ax.set_xlim(-1, 1)
            ax.set_title(f'{SCENARIO_LABELS[scenario]}\n(N={stats[scenario]["n"]})',
                        fontsize=11, fontweight='bold')
            ax.legend(fontsize=8, loc='upper left')
            ax.grid(True, alpha=0.3)
    
    plt.suptitle('Cosine Distribution: cos(θ_true - θ_reco) - Full Range',
                fontsize=16, fontweight='bold', y=0.995)
    plt.tight_layout()
    
    pdf.savefig(fig2, bbox_inches='tight')
    plt.close()
    
    # Page 3: Cosine distributions zoomed (0.9 to 1.0)
    fig3 = plt.figure(figsize=(18, 10))
    
    for i, scenario in enumerate(SCENARIOS):
        if stats[scenario] is not None:
            ax = plt.subplot(2, 3, i+1)
            cos_data = stats[scenario]['cos_theta']
            q68 = stats[scenario]['cos_theta_68']
            
            # Histogram with zoomed range
            n, bins, patches = ax.hist(cos_data, bins=50, range=(0.9, 1.0), alpha=0.7, 
                                       color=colors[i], edgecolor='black', linewidth=0.5)
            
            # 68% quantile line
            angle_q68 = np.degrees(np.arccos(np.clip(q68, -1, 1)))
            if 0.9 <= q68 <= 1.0:
                ax.axvline(q68, color='red', linestyle='--', linewidth=2.5, 
                          label=f'68% quantile: {q68:.4f} ({angle_q68:.1f}°)')
            
            # Mean line
            mean_cos = np.mean(cos_data)
            angle_mean = np.degrees(np.arccos(np.clip(mean_cos, -1, 1)))
            if 0.9 <= mean_cos <= 1.0:
                ax.axvline(mean_cos, color='blue', linestyle='-', linewidth=2, alpha=0.7,
                          label=f'Mean: {mean_cos:.4f} ({angle_mean:.1f}°)')
            
            ax.set_xlabel('cos(θ_true - θ_reco)', fontsize=10, fontweight='bold')
            ax.set_ylabel('Count', fontsize=10, fontweight='bold')
            ax.set_xlim(0.9, 1.0)
            ax.set_title(f'{SCENARIO_LABELS[scenario]}\n(N={stats[scenario]["n"]})',
                        fontsize=11, fontweight='bold')
            ax.legend(fontsize=8, loc='upper left')
            ax.grid(True, alpha=0.3)
    
    plt.suptitle('Cosine Distribution: cos(θ_true - θ_reco) - Zoomed (0.9-1.0)',
                fontsize=16, fontweight='bold', y=0.995)
    plt.tight_layout()
    
    pdf.savefig(fig3, bbox_inches='tight')
    plt.close()
    
    # Page 4: Cluster tracking metrics
    create_cluster_tracking_page(cluster_tracking, pdf)
    
    # Page 5: File and cluster statistics
    create_file_cluster_stats_page(cat_file_stats, pdf)
    
    # Page 6: Axis-aligned analysis for perfect_ct scenario
    create_axis_aligned_page(results, cos_theta_results, true_directions, pdf)
    
    # Page 7: Best cat skymap with reconstructed directions
    print("Creating best cat skymap page...")
    create_best_cat_skymap_page(results, cat_names, pdf)
    print("✓ Best cat skymap page created")
    
    # Page 8: Directional bias analysis (Cartesian)
    print("Creating Cartesian bias analysis page...")
    create_bias_analysis_page(results, cat_names, pdf)
    print("✓ Cartesian bias analysis page created")
    
    # Page 9: Angular bias analysis (Spherical coordinates)
    print("Creating angular bias analysis page...")
    create_angular_bias_analysis_page(results, cat_names, pdf)
    print("✓ Angular bias analysis page created")
    
    pdf.close()
    print(f"\n✓ Saved multi-page PDF report to: {output_pdf}")
    
    # Print detailed statistics
    print("\n" + "="*90)
    print("DETAILED STATISTICS - 6 SCENARIOS")
    print("="*90)
    
    for scenario in SCENARIOS:
        if stats[scenario] is not None:
            s = stats[scenario]
            print(f"\n{SCENARIO_LABELS[scenario]}:")
            print(f"  Sample size: {s['n']}")
            print(f"  68% Quantile: {s['q68']:.2f}° [PRIMARY METRIC]")
            print(f"  Median: {s['median']:.2f}°")
            print(f"  Mean: {s['mean']:.2f}° ± {s['std']:.2f}°")
            print(f"  Range: [{s['min']:.2f}°, {s['max']:.2f}°]")
            print(f"  IQR: [{s['q25']:.2f}°, {s['q75']:.2f}°]")
        else:
            print(f"\n{SCENARIO_LABELS[scenario]}: No data")
    
    print("\n" + "="*90)
    
    # Comparison analysis (using 68% quantile as main metric)
    print("\nCOMPARISON ANALYSIS (based on 68% Quantile):")
    print("="*90)
    
    if stats['best_case'] and stats['perfect_ct']:
        improvement = stats['best_case']['q68'] - stats['perfect_ct']['q68']
        pct = (improvement / stats['best_case']['q68']) * 100
        print(f"Perfect CT vs Best Case: {improvement:+.2f}° ({pct:+.1f}%)")
    
    if stats['perfect_ct'] and stats['full_pipeline']:
        diff = stats['full_pipeline']['q68'] - stats['perfect_ct']['q68']
        pct = (diff / stats['perfect_ct']['q68']) * 100
        print(f"Full Pipeline vs Perfect CT: {diff:+.2f}° ({pct:+.1f}%)")
    
    if stats['full_pipeline'] and stats['weighted_ct']:
        diff = stats['weighted_ct']['q68'] - stats['full_pipeline']['q68']
        pct = (diff / stats['full_pipeline']['q68']) * 100
        print(f"Weighted CT vs Full Pipeline: {diff:+.2f}° ({pct:+.1f}%)")
    
    if stats['perfect_ct'] and stats['perfect_ct_e_gt_10mev']:
        diff = stats['perfect_ct_e_gt_10mev']['q68'] - stats['perfect_ct']['q68']
        pct = (diff / stats['perfect_ct']['q68']) * 100
        print(f"E>10 MeV vs E>3 MeV: {diff:+.2f}° ({pct:+.1f}%)")
    
    if stats['perfect_ct_e_gt_10mev'] and stats['perfect_ct_e_gt_5mev']:
        diff = stats['perfect_ct_e_gt_10mev']['q68'] - stats['perfect_ct_e_gt_5mev']['q68']
        pct = (diff / stats['perfect_ct_e_gt_5mev']['q68']) * 100
        print(f"E>10 MeV vs E>5 MeV: {diff:+.2f}° ({pct:+.1f}%)")
    
    print("="*90)

def main():
    print("Loading emcee results for 6 scenarios...")
    results, cat_names, cos_theta_results, cluster_tracking, cat_file_stats, true_directions = load_results()
    
    # Summary
    total_complete = len(set().union(*[set(cats) for cats in cat_names.values() if cats]))
    print(f"\nCats with at least one scenario: {total_complete}")
    for scenario in SCENARIOS:
        n = len(results[scenario])
        print(f"  {SCENARIO_LABELS[scenario]}: {n} cats")
    
    if total_complete == 0:
        print("\nNo results found!")
        return
    
    print("\nGenerating aggregate analysis plots...")
    plot_aggregate_analysis(results, cat_names, cos_theta_results, cluster_tracking, cat_file_stats, true_directions)

if __name__ == '__main__':
    main()
