#!/usr/bin/env python3
"""
Aggregate results from EOS pipeline structure across all categories.
Computes cos(θ) distributions, 68% quantiles, and efficiency metrics.
Groups by overall and inclination categories (X-like, Y-like, Z-like).
"""

import argparse
import numpy as np
from pathlib import Path
import json
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


def classify_inclination(true_direction):
    """
    Classify neutrino direction as X-like, Y-like, or Z-like.
    Returns 'X', 'Y', 'Z', or 'mixed' if no dominant component.
    """
    abs_components = np.abs(true_direction)
    max_idx = np.argmax(abs_components)
    max_val = abs_components[max_idx]
    
    if max_val > 0.7:  # Threshold for "dominant" component
        return ['X', 'Y', 'Z'][max_idx]
    else:
        return 'mixed'


def load_scenario_result(cat_path, scenario_name):
    """Load a single scenario result from a category."""
    pipeline_dir = cat_path / 'pipeline'
    
    # Try different naming patterns
    patterns = [
        f"cat*_scenario_{scenario_name}.npz",
        f"scenario_{scenario_name}*.npz",
        f"*{scenario_name}*.npz"
    ]
    
    for pattern in patterns:
        files = list(pipeline_dir.glob(pattern))
        if files:
            result_file = files[0]
            try:
                data = np.load(result_file, allow_pickle=True)
                
                # Keys are prefixed with scenario name, e.g., 'best_case_cos_theta'
                # Convert to unprefixed keys
                result = {}
                prefix = f"{scenario_name}_"
                
                for key in data.keys():
                    if key.startswith(prefix):
                        new_key = key[len(prefix):]
                        result[new_key] = data[key]
                    else:
                        result[key] = data[key]
                
                return result
            except Exception as e:
                print(f"Warning: Could not load {result_file}: {e}")
                return None
    
    return None


def aggregate_scenario(base_dir, scenario_name, cat_names=None):
    """
    Aggregate results for a single scenario across all categories.
    
    Args:
        base_dir: Base directory containing cat* folders
        scenario_name: Name of scenario (e.g., 'best_case', 'full_pipeline')
        cat_names: List of specific cat names to process (None = all)
    
    Returns:
        Dictionary with aggregated metrics
    """
    base_path = Path(base_dir)
    
    # Find all cat directories
    if cat_names:
        cat_dirs = [base_path / cat for cat in cat_names]
    else:
        cat_dirs = sorted(base_path.glob('cat*'))
    
    # Storage for aggregated data
    all_cos_theta = []
    all_angular_errors = []
    all_true_directions = []
    all_recon_directions = []
    all_cat_names = []
    all_log_likelihoods = []
    all_n_clusters = []
    
    # Inclination-grouped storage
    inclination_data = {
        'X': {'cos_theta': [], 'angular_errors': [], 'cat_names': []},
        'Y': {'cos_theta': [], 'angular_errors': [], 'cat_names': []},
        'Z': {'cos_theta': [], 'angular_errors': [], 'cat_names': []},
        'mixed': {'cos_theta': [], 'angular_errors': [], 'cat_names': []}
    }
    
    # Process each category
    n_loaded = 0
    n_failed = 0
    
    for cat_dir in cat_dirs:
        if not cat_dir.exists():
            continue
            
        cat_name = cat_dir.name
        result = load_scenario_result(cat_dir, scenario_name)
        
        if result is None:
            n_failed += 1
            continue
        
        # Extract metrics
        cos_theta = result.get('cos_theta')
        angular_error = result.get('angular_error_deg')
        true_dir = result.get('true_nu_direction')  # Key is 'true_nu_direction' not 'true_direction'
        recon_dir = result.get('reconstructed_direction')
        log_likelihood = result.get('log_likelihood')  # Key is 'log_likelihood' not 'final_log_likelihood'
        n_clusters = result.get('n_clusters_used')
        
        if cos_theta is None or angular_error is None or true_dir is None:
            n_failed += 1
            continue
        
        # Add to overall aggregation
        all_cos_theta.append(cos_theta)
        all_angular_errors.append(angular_error)
        all_true_directions.append(true_dir)
        all_recon_directions.append(recon_dir)
        all_cat_names.append(cat_name)
        all_log_likelihoods.append(log_likelihood if log_likelihood is not None else np.nan)
        all_n_clusters.append(n_clusters if n_clusters is not None else 0)
        
        # Classify by inclination
        inclination = classify_inclination(true_dir)
        inclination_data[inclination]['cos_theta'].append(cos_theta)
        inclination_data[inclination]['angular_errors'].append(angular_error)
        inclination_data[inclination]['cat_names'].append(cat_name)
        
        n_loaded += 1
    
    if n_loaded == 0:
        print(f"Error: No valid results found for scenario '{scenario_name}'")
        return None
    
    print(f"Loaded {n_loaded} categories, {n_failed} failed")
    
    # Convert to numpy arrays
    all_cos_theta = np.array(all_cos_theta)
    all_angular_errors = np.array(all_angular_errors)
    all_true_directions = np.array(all_true_directions)
    all_recon_directions = np.array(all_recon_directions)
    all_log_likelihoods = np.array(all_log_likelihoods)
    all_n_clusters = np.array(all_n_clusters)
    
    # Compute overall statistics
    overall_stats = {
        'n_categories': n_loaded,
        'cos_theta_mean': float(np.mean(all_cos_theta)),
        'cos_theta_std': float(np.std(all_cos_theta)),
        'cos_theta_68_quantile': float(np.percentile(all_cos_theta, 68)),
        'cos_theta_median': float(np.median(all_cos_theta)),
        'cos_theta_min': float(np.min(all_cos_theta)),
        'cos_theta_max': float(np.max(all_cos_theta)),
        'angular_error_mean': float(np.mean(all_angular_errors)),
        'angular_error_std': float(np.std(all_angular_errors)),
        'angular_error_median': float(np.median(all_angular_errors)),
        'angular_error_68_quantile': float(np.percentile(all_angular_errors, 68)),
        'n_clusters_mean': float(np.mean(all_n_clusters)),
        'n_clusters_median': float(np.median(all_n_clusters)),
        'log_likelihood_mean': float(np.nanmean(all_log_likelihoods)) if not np.all(np.isnan(all_log_likelihoods)) else None,
    }
    
    # Compute per-inclination statistics
    inclination_stats = {}
    for incl, data in inclination_data.items():
        if len(data['cos_theta']) > 0:
            cos_theta_arr = np.array(data['cos_theta'])
            angular_errors_arr = np.array(data['angular_errors'])
            
            inclination_stats[incl] = {
                'n_categories': len(cos_theta_arr),
                'cos_theta_mean': float(np.mean(cos_theta_arr)),
                'cos_theta_std': float(np.std(cos_theta_arr)),
                'cos_theta_68_quantile': float(np.percentile(cos_theta_arr, 68)),
                'cos_theta_median': float(np.median(cos_theta_arr)),
                'angular_error_mean': float(np.mean(angular_errors_arr)),
                'angular_error_std': float(np.std(angular_errors_arr)),
                'angular_error_median': float(np.median(angular_errors_arr)),
                'angular_error_68_quantile': float(np.percentile(angular_errors_arr, 68)),
            }
        else:
            inclination_stats[incl] = None
    
    # Build result dictionary
    result_dict = {
        'scenario_name': scenario_name,
        'overall': overall_stats,
        'by_inclination': inclination_stats,
        'raw_data': {
            'cat_names': all_cat_names,
            'cos_theta': all_cos_theta.tolist(),
            'angular_errors': all_angular_errors.tolist(),
            'n_clusters': all_n_clusters.tolist(),
        },
        'inclination_data': {
            incl: {
                'cat_names': data['cat_names'],
                'cos_theta': [float(x) for x in data['cos_theta']],  # Convert to list of floats
                'angular_errors': [float(x) for x in data['angular_errors']],  # Convert to list of floats
            }
            for incl, data in inclination_data.items()
            if len(data['cat_names']) > 0
        }
    }
    
    return result_dict


def plot_cos_theta_distribution(aggregated_results, output_path):
    """Create histogram of cos(θ) distribution."""
    scenarios = [s for s in aggregated_results.keys() if aggregated_results[s] is not None]
    
    if not scenarios:
        print("Warning: No valid scenarios to plot")
        return
    
    # Create figure with enough subplots (2 rows)
    n_scenarios = len(scenarios)
    n_cols = min(3, n_scenarios)
    n_rows = (n_scenarios + n_cols - 1) // n_cols
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(6*n_cols, 5*n_rows))
    if n_scenarios == 1:
        axes = np.array([axes])
    axes = axes.flatten() if n_scenarios > 1 else axes
    
    fig.suptitle('cos(θ) Distributions by Scenario', fontsize=16, fontweight='bold')
    
    for idx, scenario_name in enumerate(scenarios):
        ax = axes[idx] if n_scenarios > 1 else axes[0]
        result = aggregated_results[scenario_name]
        
        cos_theta = result['raw_data']['cos_theta']
        quantile_68 = result['overall']['cos_theta_68_quantile']
        median = result['overall']['cos_theta_median']
        mean = result['overall']['cos_theta_mean']
        
        # Convert to angles for labels
        angle_68 = np.rad2deg(np.arccos(np.clip(quantile_68, -1, 1)))
        angle_median = np.rad2deg(np.arccos(np.clip(median, -1, 1)))
        angle_mean = np.rad2deg(np.arccos(np.clip(mean, -1, 1)))
        
        ax.hist(cos_theta, bins=20, alpha=0.7, edgecolor='black', color='steelblue')
        ax.axvline(quantile_68, color='red', linestyle='--', linewidth=2, 
                  label=f'68%: {quantile_68:.3f} ({angle_68:.1f}°)')
        ax.axvline(median, color='green', linestyle='--', linewidth=2,
                  label=f'Median: {median:.3f} ({angle_median:.1f}°)')
        ax.axvline(mean, color='blue', linestyle='--', linewidth=1,
                  label=f'Mean: {mean:.3f} ({angle_mean:.1f}°)')
        
        ax.set_xlabel('cos(θ)', fontsize=11)
        ax.set_ylabel('Frequency', fontsize=11)
        ax.set_title(f'{scenario_name}\n({result["overall"]["n_categories"]} cats)', 
                    fontsize=12, fontweight='bold')
        ax.legend(fontsize=9, loc='upper left')
        ax.grid(True, alpha=0.3)
    
    # Hide unused subplots
    if n_scenarios > 1:
        for idx in range(n_scenarios, len(axes)):
            axes[idx].axis('off')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Saved cos(θ) distribution plot: {output_path}")
    plt.close()


def plot_inclination_comparison(aggregated_results, output_path):
    """Create comparison plot of performance by inclination."""
    scenarios = [s for s in aggregated_results.keys() if aggregated_results[s] is not None]
    inclinations = ['X', 'Y', 'Z', 'mixed']
    
    if not scenarios:
        print("Warning: No valid scenarios to plot")
        return
    
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle('Performance by Inclination Category', fontsize=16, fontweight='bold')
    
    # Plot 1: cos(θ) 68% quantile by inclination
    ax1 = axes[0]
    x = np.arange(len(inclinations))
    width = 0.8 / max(len(scenarios), 1)
    
    colors = plt.cm.tab10(np.linspace(0, 1, len(scenarios)))
    
    for i, scenario_name in enumerate(scenarios):
        result = aggregated_results[scenario_name]
        
        quantiles = []
        for incl in inclinations:
            incl_data = result['by_inclination'].get(incl)
            if incl_data:
                quantiles.append(incl_data['cos_theta_68_quantile'])
            else:
                quantiles.append(0)
        
        offset = (i - len(scenarios)/2 + 0.5) * width
        ax1.bar(x + offset, quantiles, width, label=scenario_name, color=colors[i], alpha=0.8)
    
    ax1.set_xlabel('Inclination', fontsize=12)
    ax1.set_ylabel('cos(θ) 68% quantile', fontsize=12)
    ax1.set_title('cos(θ) Resolution by Inclination', fontsize=13, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(inclinations)
    ax1.legend(fontsize=9, loc='lower left')
    ax1.grid(True, axis='y', alpha=0.3)
    ax1.set_ylim([0, 1.0])
    
    # Plot 2: Angular error 68% quantile by inclination
    ax2 = axes[1]
    
    for i, scenario_name in enumerate(scenarios):
        result = aggregated_results[scenario_name]
        
        errors = []
        for incl in inclinations:
            incl_data = result['by_inclination'].get(incl)
            if incl_data:
                errors.append(incl_data['angular_error_68_quantile'])
            else:
                errors.append(0)
        
        offset = (i - len(scenarios)/2 + 0.5) * width
        ax2.bar(x + offset, errors, width, label=scenario_name, color=colors[i], alpha=0.8)
    
    ax2.set_xlabel('Inclination', fontsize=12)
    ax2.set_ylabel('Angular Error 68% quantile (deg)', fontsize=12)
    ax2.set_title('Angular Error by Inclination', fontsize=13, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(inclinations)
    ax2.legend(fontsize=9, loc='upper left')
    ax2.grid(True, axis='y', alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"Saved inclination comparison plot: {output_path}")
    plt.close()


def save_aggregated_results(aggregated_results, output_path):
    """Save aggregated results to JSON."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(aggregated_results, f, indent=2)
    
    print(f"Saved aggregated results: {output_path}")


def collect_event_losses(base_dir, scenario_name, cat_names=None):
    """Collect event loss statistics from all categories for a scenario."""
    base_path = Path(base_dir)
    
    if cat_names:
        cat_dirs = [base_path / cat for cat in cat_names]
    else:
        cat_dirs = sorted(base_path.glob('cat*'))
    
    all_losses = []
    
    for cat_dir in cat_dirs:
        if not cat_dir.exists():
            continue
        
        result = load_scenario_result(cat_dir, scenario_name)
        if result and 'event_losses' in result:
            losses_data = result['event_losses']
            # Convert to dict if it's an ndarray or other type
            if isinstance(losses_data, dict):
                losses = losses_data.copy()
            elif hasattr(losses_data, 'item'):  # numpy scalar or 0-d array
                losses = losses_data.item() if hasattr(losses_data, 'item') else {}
            else:
                continue
            
            losses['cat_name'] = cat_dir.name
            all_losses.append(losses)
    
    return all_losses


def create_event_loss_table(all_losses, scenario_name):
    """Create a matplotlib figure with event loss statistics table."""
    if not all_losses:
        return None
    
    fig, ax = plt.subplots(figsize=(14, max(8, len(all_losses) * 0.3 + 2)))
    ax.axis('tight')
    ax.axis('off')
    
    # Determine columns based on available keys
    sample_loss = all_losses[0]
    has_files = 'n_es_files' in sample_loss
    has_3plane = 'total_main_tracks_3plane' in sample_loss
    
    if has_files and has_3plane:
        # Scenario 2 format (perfect_ct)
        headers = ['Category', 'ES Files', 'CC Files', '3-Plane\nMain', 'Not ES', 'ES Main', 
                   '<3 MeV', 'Final']
        data = []
        for loss in all_losses:
            row = [
                loss.get('cat_name', ''),
                loss.get('n_es_files', 0),
                loss.get('n_cc_files', 0),
                loss.get('total_main_tracks_3plane', 0),
                loss.get('not_es', 0),
                loss.get('es_main_tracks', 0),
                loss.get('below_3mev', 0),
                loss.get('after_energy_cut', 0)
            ]
            data.append(row)
    elif 'total_clusters' in sample_loss:
        # Scenario 1 format (best_case)
        headers = ['Category', 'Total\nClusters', 'Not Main\nTrack', 'Not ES', 'ES Main', 
                   'Invalid\nDir', '<3 MeV', 'Final']
        data = []
        for loss in all_losses:
            row = [
                loss.get('cat_name', ''),
                loss.get('total_clusters', 0),
                loss.get('not_main_track', 0),
                loss.get('not_es', 0),
                loss.get('es_main_tracks', 0),
                loss.get('invalid_directions', 0),
                loss.get('below_3mev', 0),
                loss.get('after_energy_cut', 0)
            ]
            data.append(row)
    else:
        return None
    
    # Add summary row
    data.append(['---'] * len(headers))
    summary_row = ['MEAN']
    for col_idx in range(1, len(headers)):
        col_vals = [row[col_idx] for row in data[:-1] if isinstance(row[col_idx], (int, float))]
        if col_vals:
            summary_row.append(f"{np.mean(col_vals):.1f}")
        else:
            summary_row.append('')
    data.append(summary_row)
    
    table = ax.table(cellText=data, colLabels=headers, cellLoc='center', loc='center',
                     colWidths=[0.12] + [0.10] * (len(headers) - 1))
    
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.8)
    
    # Style header
    for (i, j), cell in table.get_celld().items():
        if i == 0:
            cell.set_facecolor('#4CAF50')
            cell.set_text_props(weight='bold', color='white')
        elif i == len(data):  # Summary row
            cell.set_facecolor('#E0E0E0')
            cell.set_text_props(weight='bold')
        elif data[i-1][0] == '---':
            cell.set_text_props(weight='normal')
    
    ax.set_title(f'Event Loss Statistics: {scenario_name}', 
                fontsize=14, fontweight='bold', pad=20)
    
    return fig


def print_summary(aggregated_results):
    """Print a text summary of aggregated results."""
    print("\n" + "="*80)
    print("AGGREGATED RESULTS SUMMARY")
    print("="*80)
    
    for scenario_name, result in aggregated_results.items():
        if result is None:
            print(f"\n{scenario_name}: No data")
            continue
        
        overall = result['overall']
        print(f"\n{scenario_name.upper()}:")
        print(f"  Categories: {overall['n_categories']}")
        print(f"  cos(θ) 68% quantile: {overall['cos_theta_68_quantile']:.3f}")
        print(f"  cos(θ) mean: {overall['cos_theta_mean']:.3f} ± {overall['cos_theta_std']:.3f}")
        print(f"  cos(θ) median: {overall['cos_theta_median']:.3f}")
        print(f"  Angular error mean: {overall['angular_error_mean']:.2f}° ± {overall['angular_error_std']:.2f}°")
        print(f"  Angular error 68%: {overall['angular_error_68_quantile']:.2f}°")
        print(f"  Clusters mean: {overall['n_clusters_mean']:.1f}")
        
        # Print inclination breakdown
        print(f"\n  By Inclination:")
        for incl in ['X', 'Y', 'Z', 'mixed']:
            incl_data = result['by_inclination'].get(incl)
            if incl_data:
                print(f"    {incl}-like ({incl_data['n_categories']} cats): "
                      f"cos(θ) 68% = {incl_data['cos_theta_68_quantile']:.3f}, "
                      f"error 68% = {incl_data['angular_error_68_quantile']:.2f}°")
    
    print("\n" + "="*80)


def create_summary_statistics_page(aggregated_results, scenarios_to_plot):
    """Create a summary statistics table page."""
    fig = plt.figure(figsize=(16, 10))
    ax = fig.add_subplot(111)
    ax.axis('tight')
    ax.axis('off')
    
    # Summary statistics table
    headers = ['Scenario', 'N Cats', 'cos(θ) 68%', 'Angle 68% (°)', 'Mean Error (°)', 'Mean Clusters']
    data = []
    
    for scenario_name in scenarios_to_plot:
        result = aggregated_results[scenario_name]
        overall = result['overall']
        
        cos_68 = overall['cos_theta_68_quantile']
        angle_68 = np.rad2deg(np.arccos(np.clip(cos_68, -1, 1)))
        
        row = [
            scenario_name,
            overall['n_categories'],
            f"{cos_68:.3f}",
            f"{angle_68:.1f}",
            f"{overall['angular_error_mean']:.1f} ± {overall['angular_error_std']:.1f}",
            f"{overall['n_clusters_mean']:.1f}"
        ]
        data.append(row)
    
    table = ax.table(cellText=data, colLabels=headers, cellLoc='center', loc='center',
                     colWidths=[0.20, 0.10, 0.15, 0.15, 0.20, 0.15])
    
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 2.5)
    
    for (i, j), cell in table.get_celld().items():
        if i == 0:
            cell.set_facecolor('#2196F3')
            cell.set_text_props(weight='bold', color='white', fontsize=12)
        else:
            if j == 0:
                cell.set_text_props(weight='bold')
    
    ax.set_title('Summary Statistics by Scenario', fontsize=16, fontweight='bold', pad=30)
    
    return fig


def create_average_event_losses_page(aggregated_results, base_dir, scenarios_to_plot, cats):
    """Create average event loss statistics across all cats."""
    fig, axes = plt.subplots(2, 1, figsize=(14, 11))
    
    # Collect average losses for each scenario
    scenario_avg_losses = {}
    
    for scenario_name in scenarios_to_plot:
        all_losses = collect_event_losses(base_dir, scenario_name, cats)
        if all_losses:
            # Calculate averages
            avg_losses = {}
            sample_loss = all_losses[0]
            
            for key in sample_loss.keys():
                if key != 'cat_name' and isinstance(sample_loss[key], (int, float)):
                    values = [loss.get(key, 0) for loss in all_losses if isinstance(loss.get(key), (int, float))]
                    if values:
                        avg_losses[key] = np.mean(values)
            
            scenario_avg_losses[scenario_name] = avg_losses
    
    # Top plot: Event flow for scenarios with 3-plane info (perfect_ct style)
    ax1 = axes[0]
    scenarios_with_3plane = [s for s in scenarios_to_plot if scenario_avg_losses.get(s) and 'total_main_tracks_3plane' in scenario_avg_losses[s]]
    
    if scenarios_with_3plane:
        x = np.arange(len(scenarios_with_3plane))
        width = 0.15
        
        stages = [
            ('n_es_files', 'ES Files', '#4CAF50'),
            ('total_main_tracks_3plane', '3-Plane Matched', '#2196F3'),
            ('es_main_tracks', 'ES Main', '#FF9800'),
            ('below_3mev', 'Lost <3 MeV', '#F44336'),
            ('after_energy_cut', 'Final Used', '#9C27B0')
        ]
        
        for i, (key, label, color) in enumerate(stages):
            values = [scenario_avg_losses[s].get(key, 0) for s in scenarios_with_3plane]
            offset = (i - len(stages)/2 + 0.5) * width
            ax1.bar(x + offset, values, width, label=label, color=color, alpha=0.8)
        
        ax1.set_xlabel('Scenario', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Average Count per Category', fontsize=12, fontweight='bold')
        ax1.set_title('Average Event Flow: Perfect CT Scenarios', fontsize=14, fontweight='bold')
        ax1.set_xticks(x)
        ax1.set_xticklabels(scenarios_with_3plane, rotation=15, ha='right')
        ax1.legend(fontsize=10, loc='upper right')
        ax1.grid(True, axis='y', alpha=0.3)
    else:
        ax1.text(0.5, 0.5, 'No 3-plane data available', ha='center', va='center', 
                transform=ax1.transAxes, fontsize=14)
        ax1.axis('off')
    
    # Bottom plot: Event flow for scenarios with total_clusters (best_case style)
    ax2 = axes[1]
    scenarios_with_total = [s for s in scenarios_to_plot if scenario_avg_losses.get(s) and 'total_clusters' in scenario_avg_losses[s]]
    
    if scenarios_with_total:
        x = np.arange(len(scenarios_with_total))
        width = 0.12
        
        stages = [
            ('total_clusters', 'Total Clusters', '#4CAF50'),
            ('not_main_track', 'Lost: Not Main', '#FF5722'),
            ('not_es', 'Lost: Not ES', '#FF9800'),
            ('es_main_tracks', 'ES Main', '#2196F3'),
            ('invalid_directions', 'Lost: Invalid Dir', '#9E9E9E'),
            ('below_3mev', 'Lost: <3 MeV', '#F44336'),
            ('after_energy_cut', 'Final Used', '#9C27B0')
        ]
        
        for i, (key, label, color) in enumerate(stages):
            values = [scenario_avg_losses[s].get(key, 0) for s in scenarios_with_total]
            offset = (i - len(stages)/2 + 0.5) * width
            ax2.bar(x + offset, values, width, label=label, color=color, alpha=0.8)
        
        ax2.set_xlabel('Scenario', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Average Count per Category', fontsize=12, fontweight='bold')
        ax2.set_title('Average Event Flow: Best Case Scenario', fontsize=14, fontweight='bold')
        ax2.set_xticks(x)
        ax2.set_xticklabels(scenarios_with_total, rotation=15, ha='right')
        ax2.legend(fontsize=9, loc='upper right', ncol=2)
        ax2.grid(True, axis='y', alpha=0.3)
    else:
        ax2.text(0.5, 0.5, 'No total clusters data available', ha='center', va='center',
                transform=ax2.transAxes, fontsize=14)
        ax2.axis('off')
    
    plt.tight_layout()
    return fig


def create_comprehensive_pdf_report(aggregated_results, base_dir, scenarios, cats, output_path):
    """Create comprehensive PDF report with all plots and event loss tables."""
    print(f"\nGenerating comprehensive PDF report: {output_path}")
    
    with PdfPages(output_path) as pdf:
        scenarios_to_plot = [s for s in scenarios if aggregated_results.get(s) is not None]
        
        # Page 1: Summary statistics table
        print("  Adding summary statistics table...")
        fig = create_summary_statistics_page(aggregated_results, scenarios_to_plot)
        pdf.savefig(fig, dpi=150, bbox_inches='tight')
        plt.close()
        
        # Page 2: Average event losses across all cats
        print("  Adding average event loss statistics...")
        fig = create_average_event_losses_page(aggregated_results, base_dir, scenarios_to_plot, cats)
        pdf.savefig(fig, dpi=150, bbox_inches='tight')
        plt.close()
        
        # Page 3 & 4: cos(θ) distributions (split into 2 pages if needed)
        print("  Adding cos(θ) distributions...")
        
        if scenarios_to_plot:
            n_scenarios = len(scenarios_to_plot)
            scenarios_per_page = 6
            
            for page_idx in range((n_scenarios + scenarios_per_page - 1) // scenarios_per_page):
                page_scenarios = scenarios_to_plot[page_idx * scenarios_per_page:(page_idx + 1) * scenarios_per_page]
                n_page_scenarios = len(page_scenarios)
                n_cols = min(3, n_page_scenarios)
                n_rows = (n_page_scenarios + n_cols - 1) // n_cols
                
                fig, axes = plt.subplots(n_rows, n_cols, figsize=(6*n_cols, 5*n_rows))
                if n_page_scenarios == 1:
                    axes = np.array([axes])
                axes = axes.flatten() if n_page_scenarios > 1 else axes
                
                page_title = f'cos(θ) Distributions by Scenario (Page {page_idx + 1})'
                fig.suptitle(page_title, fontsize=16, fontweight='bold')
                
                for idx, scenario_name in enumerate(page_scenarios):
                    ax = axes[idx] if n_page_scenarios > 1 else axes[0]
                    result = aggregated_results[scenario_name]
                
                cos_theta = result['raw_data']['cos_theta']
                quantile_68 = result['overall']['cos_theta_68_quantile']
                median = result['overall']['cos_theta_median']
                mean = result['overall']['cos_theta_mean']
                
                angle_68 = np.rad2deg(np.arccos(np.clip(quantile_68, -1, 1)))
                angle_median = np.rad2deg(np.arccos(np.clip(median, -1, 1)))
                angle_mean = np.rad2deg(np.arccos(np.clip(mean, -1, 1)))
                
                ax.hist(cos_theta, bins=20, alpha=0.7, edgecolor='black', color='steelblue')
                ax.axvline(quantile_68, color='red', linestyle='--', linewidth=2, 
                          label=f'68%: {quantile_68:.3f} ({angle_68:.1f}°)')
                ax.axvline(median, color='green', linestyle='--', linewidth=2,
                          label=f'Median: {median:.3f} ({angle_median:.1f}°)')
                ax.axvline(mean, color='blue', linestyle='--', linewidth=1,
                          label=f'Mean: {mean:.3f} ({angle_mean:.1f}°)')
                
                ax.set_xlabel('cos(θ)', fontsize=11)
                ax.set_ylabel('Frequency', fontsize=11)
                ax.set_title(f'{scenario_name}\n({result["overall"]["n_categories"]} cats)', 
                            fontsize=12, fontweight='bold')
                ax.legend(fontsize=9, loc='upper left')
                ax.grid(True, alpha=0.3)
                
                if n_page_scenarios > 1:
                    for idx in range(n_page_scenarios, len(axes)):
                        axes[idx].axis('off')
                
                plt.tight_layout()
                pdf.savefig(fig, dpi=150, bbox_inches='tight')
                plt.close()
        
        # Next page: Inclination comparison
        print("  Adding inclination comparison...")
        inclinations = ['X', 'Y', 'Z', 'mixed']
        
        fig, axes = plt.subplots(1, 2, figsize=(16, 6))
        fig.suptitle('Performance by Inclination Category', fontsize=16, fontweight='bold')
        
        ax1 = axes[0]
        x = np.arange(len(inclinations))
        width = 0.8 / max(len(scenarios_to_plot), 1)
        colors = plt.cm.tab10(np.linspace(0, 1, len(scenarios_to_plot)))
        
        for i, scenario_name in enumerate(scenarios_to_plot):
            result = aggregated_results[scenario_name]
            quantiles = []
            for incl in inclinations:
                incl_data = result['by_inclination'].get(incl)
                quantiles.append(incl_data['cos_theta_68_quantile'] if incl_data else 0)
            
            offset = (i - len(scenarios_to_plot)/2 + 0.5) * width
            ax1.bar(x + offset, quantiles, width, label=scenario_name, color=colors[i], alpha=0.8)
        
        ax1.set_xlabel('Inclination', fontsize=12)
        ax1.set_ylabel('cos(θ) 68% quantile', fontsize=12)
        ax1.set_title('cos(θ) Resolution by Inclination', fontsize=13, fontweight='bold')
        ax1.set_xticks(x)
        ax1.set_xticklabels(inclinations)
        ax1.legend(fontsize=9, loc='lower left')
        ax1.grid(True, axis='y', alpha=0.3)
        ax1.set_ylim([0, 1.0])
        
        ax2 = axes[1]
        for i, scenario_name in enumerate(scenarios_to_plot):
            result = aggregated_results[scenario_name]
            errors = []
            for incl in inclinations:
                incl_data = result['by_inclination'].get(incl)
                errors.append(incl_data['angular_error_68_quantile'] if incl_data else 0)
            
            offset = (i - len(scenarios_to_plot)/2 + 0.5) * width
            ax2.bar(x + offset, errors, width, label=scenario_name, color=colors[i], alpha=0.8)
        
        ax2.set_xlabel('Inclination', fontsize=12)
        ax2.set_ylabel('Angular Error 68% quantile (deg)', fontsize=12)
        ax2.set_title('Angular Error by Inclination', fontsize=13, fontweight='bold')
        ax2.set_xticks(x)
        ax2.set_xticklabels(inclinations)
        ax2.legend(fontsize=9, loc='upper left')
        ax2.grid(True, axis='y', alpha=0.3)
        
        plt.tight_layout()
        pdf.savefig(fig, dpi=150, bbox_inches='tight')
        plt.close()
        
        # Final pages: Detailed event loss tables for each scenario (optional detail)
        print("  Adding detailed event loss tables per scenario...")
        for scenario_name in scenarios_to_plot:
            all_losses = collect_event_losses(base_dir, scenario_name, cats)
            if all_losses:
                fig = create_event_loss_table(all_losses, scenario_name)
                if fig:
                    pdf.savefig(fig, dpi=150, bbox_inches='tight')
                    plt.close()
    
    print(f"✓ Comprehensive PDF report saved: {output_path}")
    print(f"  Contains: Summary table, average event losses, cos(θ) distributions,")
    print(f"            inclination comparison, and detailed per-cat loss tables")


def main():
    parser = argparse.ArgumentParser(description='Aggregate pipeline results across categories')
    parser.add_argument('--base-dir', required=True, help='Base directory containing cat* folders')
    parser.add_argument('--scenarios', nargs='+', default=['best_case', 'perfect_ct', 'full_pipeline', 'weighted_linear', 'weighted_squared'],
                       help='Scenarios to aggregate')
    parser.add_argument('--cats', nargs='+', help='Specific categories to process (default: all)')
    parser.add_argument('--output-dir', default='aggregated_results', help='Output directory')
    
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Aggregate each scenario
    aggregated_results = {}
    
    for scenario_name in args.scenarios:
        print(f"\nAggregating scenario: {scenario_name}")
        result = aggregate_scenario(args.base_dir, scenario_name, args.cats)
        aggregated_results[scenario_name] = result
    
    # Save results
    save_aggregated_results(aggregated_results, output_dir / 'aggregated_metrics.json')
    
    # Create comprehensive PDF report
    create_comprehensive_pdf_report(
        aggregated_results, args.base_dir, args.scenarios, args.cats,
        output_dir / 'comprehensive_report.pdf'
    )
    
    # Print summary
    print_summary(aggregated_results)


if __name__ == '__main__':
    main()
