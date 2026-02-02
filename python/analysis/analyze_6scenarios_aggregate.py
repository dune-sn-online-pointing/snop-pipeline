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

def load_results(base_path='/eos/project-e/ep-nu/evilla/sn-pointing'):
    """Load all emcee results for the 6 scenarios."""
    base = Path(base_path)
    results = {scenario: [] for scenario in SCENARIOS}
    cat_names = {scenario: [] for scenario in SCENARIOS}
    cos_theta_results = {scenario: [] for scenario in SCENARIOS}
    true_directions = {scenario: [] for scenario in SCENARIOS}  # Store true nu directions
    cluster_tracking = {scenario: {'n_total': [], 'n_es_main': [], 'n_used': []}
                       for scenario in SCENARIOS}
    
    # Track files and clusters per cat (for all cats, not per scenario)
    cat_file_stats = {'es_files': [], 'cc_files': [], 'es_clusters': [], 'cc_clusters': []}    # Find all cats with emcee results
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
        
        # Cosine distribution
        ax2 = plt.subplot(3, 2, idx*2 + 2)
        n, bins, patches = ax2.hist(cos_aligned, bins=50, range=(-1, 1),
                                      alpha=0.7, color=color, edgecolor='black', linewidth=0.5)
        
        ax2.axvline(q68_cos, color='red', linestyle='--', linewidth=2.5,
                   label=f'68th %ile = {q68_cos:.4f}')
        ax2.axvline(np.median(cos_aligned), color='orange', linestyle='--', linewidth=2,
                   label=f'Median = {np.median(cos_aligned):.4f}')
        
        ax2.set_xlabel('cos(θ)', fontsize=11, fontweight='bold')
        ax2.set_ylabel('Count', fontsize=11, fontweight='bold')
        ax2.set_title(f'{axis_name}-aligned: Cosine Distribution', fontsize=12, fontweight='bold')
        ax2.legend(fontsize=9, loc='upper left')
        ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
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
            q68 = np.percentile(cos_arr, 68)
            stats[scenario] = {
                'data': arr,
                'mean': np.mean(arr),
                'median': np.median(arr),
                'std': np.std(arr),
                'n': len(arr),
                'min': np.min(arr),
                'max': np.max(arr),
                'q25': np.percentile(arr, 25),
                'q75': np.percentile(arr, 75),
                'cos_theta': cos_arr,
                'cos_theta_68': q68
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
                f"{s['mean']:.2f}°",
                f"{s['median']:.2f}°",
                f"{s['std']:.2f}°"
            ])
    
    table = ax2.table(cellText=table_data,
                     colLabels=['Scenario', 'N', 'Mean', 'Median', 'Std'],
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
            print(f"  Mean: {s['mean']:.2f}° ± {s['std']:.2f}°")
            print(f"  Median: {s['median']:.2f}°")
            print(f"  Range: [{s['min']:.2f}°, {s['max']:.2f}°]")
            print(f"  IQR: [{s['q25']:.2f}°, {s['q75']:.2f}°]")
        else:
            print(f"\n{SCENARIO_LABELS[scenario]}: No data")
    
    print("\n" + "="*90)
    
    # Comparison analysis
    print("\nCOMPARISON ANALYSIS:")
    print("="*90)
    
    if stats['best_case'] and stats['perfect_ct']:
        improvement = stats['best_case']['mean'] - stats['perfect_ct']['mean']
        pct = (improvement / stats['best_case']['mean']) * 100
        print(f"Perfect CT vs Best Case: {improvement:+.2f}° ({pct:+.1f}%)")
    
    if stats['perfect_ct'] and stats['full_pipeline']:
        diff = stats['full_pipeline']['mean'] - stats['perfect_ct']['mean']
        pct = (diff / stats['perfect_ct']['mean']) * 100
        print(f"Full Pipeline vs Perfect CT: {diff:+.2f}° ({pct:+.1f}%)")
    
    if stats['full_pipeline'] and stats['weighted_ct']:
        diff = stats['weighted_ct']['mean'] - stats['full_pipeline']['mean']
        pct = (diff / stats['full_pipeline']['mean']) * 100
        print(f"Weighted CT vs Full Pipeline: {diff:+.2f}° ({pct:+.1f}%)")
    
    if stats['perfect_ct'] and stats['perfect_ct_e_gt_10mev']:
        diff = stats['perfect_ct_e_gt_10mev']['mean'] - stats['perfect_ct']['mean']
        pct = (diff / stats['perfect_ct']['mean']) * 100
        print(f"E>10 MeV vs E>3 MeV: {diff:+.2f}° ({pct:+.1f}%)")
    
    if stats['perfect_ct_e_gt_10mev'] and stats['perfect_ct_e_gt_5mev']:
        diff = stats['perfect_ct_e_gt_10mev']['mean'] - stats['perfect_ct_e_gt_5mev']['mean']
        pct = (diff / stats['perfect_ct_e_gt_5mev']['mean']) * 100
        print(f"E>10 MeV vs E>5 MeV: +{diff:.2f}° (+{pct:.1f}%)")
    
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
