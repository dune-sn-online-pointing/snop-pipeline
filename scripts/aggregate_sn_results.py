#!/usr/bin/env python3
"""
Aggregate results from systematic SN analysis across all categories.
Combines per-cat metrics into scenario-level summaries.
"""

import argparse
import json
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt


def load_cat_results(results_dir, scenario_name):
    """Load all per-cat results for a given scenario."""
    scenario_dir = Path(results_dir) / scenario_name
    
    if not scenario_dir.exists():
        print(f"Warning: Scenario directory not found: {scenario_dir}")
        return []
    
    cat_results = []
    for cat_dir in sorted(scenario_dir.glob('cat*')):
        metrics_file = cat_dir / 'metrics.json'
        if metrics_file.exists():
            with open(metrics_file, 'r') as f:
                data = json.load(f)
                cat_results.append(data)
    
    return cat_results


def aggregate_angular_resolution(cat_results):
    """Aggregate angular resolution metrics across categories."""
    all_angular_errors = []
    
    for cat_data in cat_results:
        # Get per-event angular errors
        per_event = cat_data.get('per_event_results', [])
        for event in per_event:
            if event.get('angular_error_deg') is not None:
                all_angular_errors.append(event['angular_error_deg'])
    
    if len(all_angular_errors) == 0:
        return None
    
    all_angular_errors = np.array(all_angular_errors)
    
    return {
        'n_events': len(all_angular_errors),
        'median_deg': float(np.median(all_angular_errors)),
        'mean_deg': float(np.mean(all_angular_errors)),
        'std_deg': float(np.std(all_angular_errors)),
        'p50_deg': float(np.percentile(all_angular_errors, 50)),
        'p68_deg': float(np.percentile(all_angular_errors, 68)),
        'p90_deg': float(np.percentile(all_angular_errors, 90)),
        'p95_deg': float(np.percentile(all_angular_errors, 95)),
        'min_deg': float(np.min(all_angular_errors)),
        'max_deg': float(np.max(all_angular_errors)),
        'all_errors_deg': all_angular_errors.tolist(),
    }


def aggregate_per_cat_metrics(cat_results):
    """Aggregate per-category summary metrics."""
    per_cat = []
    
    for cat_data in cat_results:
        cat_name = cat_data.get('cat_name')
        n_events = cat_data.get('n_events_processed', 0)
        
        angular_res = cat_data.get('angular_resolution', {})
        median_deg = angular_res.get('median_deg')
        
        per_cat.append({
            'cat_name': cat_name,
            'n_events': n_events,
            'median_resolution_deg': median_deg,
        })
    
    return per_cat


def aggregate_efficiency_metrics(cat_results):
    """Aggregate efficiency metrics (for full pipeline scenario)."""
    mt_efficiencies = []
    ct_efficiencies = []
    overall_efficiencies = []
    
    for cat_data in cat_results:
        if 'mt_efficiency' in cat_data:
            mt_efficiencies.append(cat_data['mt_efficiency'])
        if 'ct_efficiency' in cat_data:
            ct_efficiencies.append(cat_data['ct_efficiency'])
        if 'overall_efficiency' in cat_data:
            overall_efficiencies.append(cat_data['overall_efficiency'])
    
    if len(overall_efficiencies) == 0:
        return None
    
    return {
        'mt_efficiency': {
            'mean': float(np.mean(mt_efficiencies)),
            'median': float(np.median(mt_efficiencies)),
            'std': float(np.std(mt_efficiencies)),
        } if mt_efficiencies else None,
        'ct_efficiency': {
            'mean': float(np.mean(ct_efficiencies)),
            'median': float(np.median(ct_efficiencies)),
            'std': float(np.std(ct_efficiencies)),
        } if ct_efficiencies else None,
        'overall_efficiency': {
            'mean': float(np.mean(overall_efficiencies)),
            'median': float(np.median(overall_efficiencies)),
            'std': float(np.std(overall_efficiencies)),
        } if overall_efficiencies else None,
    }


def plot_angular_resolution_comparison(aggregated_results, output_dir):
    """Create comparison plot of angular resolution across scenarios."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    scenarios = ['best_case', 'ed_network', 'full_pipeline']
    scenario_labels = ['Best Case\n(True Directions)', 'ED Network\n(Perfect Tagging)', 'Full Pipeline\n(MT→CT→ED)']
    colors = ['green', 'blue', 'red']
    
    # Plot 1: Box plot of angular errors
    ax = axes[0]
    box_data = []
    box_labels = []
    box_colors = []
    
    for i, scenario in enumerate(scenarios):
        if scenario in aggregated_results and aggregated_results[scenario]['angular_resolution'] is not None:
            errors = aggregated_results[scenario]['angular_resolution']['all_errors_deg']
            box_data.append(errors)
            box_labels.append(scenario_labels[i])
            box_colors.append(colors[i])
    
    if box_data:
        bp = ax.boxplot(box_data, labels=box_labels, patch_artist=True, showfliers=False)
        for patch, color in zip(bp['boxes'], box_colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.6)
        
        ax.set_ylabel('Angular Error (degrees)', fontsize=12)
        ax.set_title('Angular Resolution Distribution', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, axis='y')
    
    # Plot 2: Percentile comparison
    ax = axes[1]
    percentiles = ['p50_deg', 'p68_deg', 'p90_deg', 'p95_deg']
    percentile_labels = ['50th', '68th', '90th', '95th']
    
    x = np.arange(len(percentiles))
    width = 0.25
    
    for i, scenario in enumerate(scenarios):
        if scenario in aggregated_results and aggregated_results[scenario]['angular_resolution'] is not None:
            ang_res = aggregated_results[scenario]['angular_resolution']
            values = [ang_res.get(p, 0) for p in percentiles]
            ax.bar(x + i*width, values, width, label=scenario_labels[i], color=colors[i], alpha=0.7)
    
    ax.set_xlabel('Percentile', fontsize=12)
    ax.set_ylabel('Angular Error (degrees)', fontsize=12)
    ax.set_title('Angular Resolution Percentiles', fontsize=14, fontweight='bold')
    ax.set_xticks(x + width)
    ax.set_xticklabels(percentile_labels)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    output_file = Path(output_dir) / 'angular_resolution_comparison.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Saved plot: {output_file}")
    plt.close()


def main():
    parser = argparse.ArgumentParser(description='Aggregate systematic SN analysis results')
    parser.add_argument('--results-dir', required=True, help='Results directory from systematic analysis')
    parser.add_argument('--output-dir', help='Output directory for aggregated results (default: same as results-dir)')
    parser.add_argument('--plot', action='store_true', help='Generate comparison plots')
    
    args = parser.parse_args()
    
    results_dir = Path(args.results_dir)
    output_dir = Path(args.output_dir) if args.output_dir else results_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*70}")
    print("AGGREGATING SYSTEMATIC SN ANALYSIS RESULTS")
    print(f"{'='*70}\n")
    print(f"Results directory: {results_dir}")
    print(f"Output directory: {output_dir}\n")
    
    # Load analysis summary
    summary_file = results_dir / 'analysis_summary.json'
    if summary_file.exists():
        with open(summary_file, 'r') as f:
            summary = json.load(f)
        print(f"Analysis summary:")
        print(f"  Total categories: {summary['total_cats']}")
        print(f"  Processed: {len(summary['processed_cats'])}")
        print(f"  Skipped: {len(summary['skipped_cats'])}")
        print(f"  Scenarios: {', '.join(summary['scenarios'])}\n")
    else:
        print("Warning: analysis_summary.json not found\n")
        summary = None
    
    # Aggregate results for each scenario
    scenarios = ['best_case', 'ed_network', 'full_pipeline']
    scenario_names = {
        'best_case': 'Best Case (True Directions)',
        'ed_network': 'ED Network (Perfect Tagging)',
        'full_pipeline': 'Full Pipeline (MT→CT→ED)',
    }
    
    aggregated_results = {}
    
    for scenario in scenarios:
        print(f"{'='*70}")
        print(f"SCENARIO: {scenario_names[scenario]}")
        print(f"{'='*70}\n")
        
        # Load cat results
        cat_results = load_cat_results(results_dir, scenario)
        
        if len(cat_results) == 0:
            print(f"No results found for {scenario}\n")
            continue
        
        print(f"Loaded results from {len(cat_results)} categories")
        
        # Aggregate angular resolution
        angular_resolution = aggregate_angular_resolution(cat_results)
        
        # Aggregate per-cat metrics
        per_cat_metrics = aggregate_per_cat_metrics(cat_results)
        
        # Aggregate efficiency (for full pipeline)
        efficiency_metrics = None
        if scenario == 'full_pipeline':
            efficiency_metrics = aggregate_efficiency_metrics(cat_results)
        
        # Compile aggregated results
        aggregated = {
            'scenario': scenario,
            'scenario_name': scenario_names[scenario],
            'n_cats': len(cat_results),
            'angular_resolution': angular_resolution,
            'per_cat_metrics': per_cat_metrics,
        }
        
        if efficiency_metrics is not None:
            aggregated['efficiency_metrics'] = efficiency_metrics
        
        aggregated_results[scenario] = aggregated
        
        # Print summary
        if angular_resolution:
            print(f"\nAngular Resolution Summary:")
            print(f"  Events: {angular_resolution['n_events']}")
            print(f"  Median: {angular_resolution['median_deg']:.2f}°")
            print(f"  Mean: {angular_resolution['mean_deg']:.2f}° ± {angular_resolution['std_deg']:.2f}°")
            print(f"  68th percentile: {angular_resolution['p68_deg']:.2f}°")
            print(f"  90th percentile: {angular_resolution['p90_deg']:.2f}°")
            print(f"  95th percentile: {angular_resolution['p95_deg']:.2f}°")
        
        if efficiency_metrics:
            print(f"\nEfficiency Summary:")
            if efficiency_metrics['mt_efficiency']:
                print(f"  MT: {efficiency_metrics['mt_efficiency']['mean']:.1%} ± {efficiency_metrics['mt_efficiency']['std']:.1%}")
            if efficiency_metrics['ct_efficiency']:
                print(f"  CT: {efficiency_metrics['ct_efficiency']['mean']:.1%} ± {efficiency_metrics['ct_efficiency']['std']:.1%}")
            if efficiency_metrics['overall_efficiency']:
                print(f"  Overall: {efficiency_metrics['overall_efficiency']['mean']:.1%} ± {efficiency_metrics['overall_efficiency']['std']:.1%}")
        
        print()
    
    # Save aggregated results
    output_file = output_dir / 'aggregated_results.json'
    
    # Remove large arrays before saving
    output_data = {}
    for scenario, data in aggregated_results.items():
        output_data[scenario] = data.copy()
        if output_data[scenario]['angular_resolution'] is not None:
            # Remove the full error list to keep file size manageable
            del output_data[scenario]['angular_resolution']['all_errors_deg']
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"{'='*70}")
    print("AGGREGATION COMPLETE")
    print(f"{'='*70}")
    print(f"Aggregated results saved to: {output_file}\n")
    
    # Generate comparison plots
    if args.plot:
        print("Generating comparison plots...")
        try:
            plot_angular_resolution_comparison(aggregated_results, output_dir)
        except Exception as e:
            print(f"Warning: Failed to generate plots: {e}")
    
    # Print final comparison table
    print("\nFinal Comparison:")
    print(f"{'Scenario':<35} {'Median':<12} {'68th %':<12} {'90th %':<12}")
    print('-' * 70)
    for scenario in scenarios:
        if scenario in aggregated_results and aggregated_results[scenario]['angular_resolution']:
            ang_res = aggregated_results[scenario]['angular_resolution']
            name = scenario_names[scenario]
            print(f"{name:<35} {ang_res['median_deg']:>8.2f}°   {ang_res['p68_deg']:>8.2f}°   {ang_res['p90_deg']:>8.2f}°")
    print()


if __name__ == '__main__':
    main()
