#!/usr/bin/env python3
"""
Generate comprehensive PDF report for SN pointing systematic analysis.
Includes cluster statistics, angular resolution comparisons, and efficiency metrics.
"""

import argparse
import json
import numpy as np
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from datetime import datetime
import sys


def load_all_results(results_dir, scenarios):
    """Load results from all categories for all scenarios."""
    results = {scenario: [] for scenario in scenarios}
    
    for scenario in scenarios:
        scenario_dir = Path(results_dir) / scenario
        if not scenario_dir.exists():
            continue
        
        for cat_dir in sorted(scenario_dir.glob('cat*')):
            metrics_file = cat_dir / 'metrics.json'
            if metrics_file.exists():
                with open(metrics_file, 'r') as f:
                    data = json.load(f)
                    data['category'] = cat_dir.name
                    results[scenario].append(data)
    
    return results


def compute_aggregate_stats(results, scenarios):
    """Compute aggregate statistics across all categories."""
    stats = {}
    
    for scenario in scenarios:
        if not results[scenario]:
            stats[scenario] = None
            continue
        
        angular_errors = []
        cluster_stats = {
            'n_input': [], 'n_input_main': [], 'n_input_non_main': [],
            'n_matched': [], 'n_matched_main': [], 'n_matched_non_main': []
        }
        
        for cat_result in results[scenario]:
            # Angular resolution
            if cat_result.get('angular_resolution', {}).get('median_deg'):
                angular_errors.append(cat_result['angular_resolution']['median_deg'])
            
            # Cluster statistics
            cs = cat_result.get('cluster_statistics', {})
            cluster_stats['n_input'].append(cs.get('n_input_clusters', 0))
            cluster_stats['n_input_main'].append(cs.get('n_input_main_clusters', 0))
            cluster_stats['n_input_non_main'].append(cs.get('n_input_non_main_clusters', 0))
            cluster_stats['n_matched'].append(cs.get('n_matched_clusters', 0))
            cluster_stats['n_matched_main'].append(cs.get('n_matched_main_clusters', 0))
            cluster_stats['n_matched_non_main'].append(cs.get('n_matched_non_main_clusters', 0))
        
        stats[scenario] = {
            'n_categories': len(results[scenario]),
            'angular_resolution': {
                'median': np.median(angular_errors) if angular_errors else None,
                'mean': np.mean(angular_errors) if angular_errors else None,
                'p68': np.percentile(angular_errors, 68) if angular_errors else None,
                'p90': np.percentile(angular_errors, 90) if angular_errors else None,
                'std': np.std(angular_errors) if angular_errors else None,
            },
            'cluster_statistics': {
                key: {
                    'total': int(np.sum(values)),
                    'mean': float(np.mean(values)),
                    'median': float(np.median(values)),
                    'std': float(np.std(values)),
                } for key, values in cluster_stats.items()
            }
        }
    
    return stats


def plot_angular_resolution_comparison(results, scenarios, ax):
    """Plot angular resolution comparison across scenarios."""
    scenario_labels = {
        'best_case': 'Best Case\n(True Directions)',
        'ed_network': 'ED Network\n(Perfect Tagging)',
        'full_pipeline': 'Full Pipeline\n(MT→CT→ED)'
    }
    
    data_to_plot = []
    labels = []
    
    for scenario in scenarios:
        if not results[scenario]:
            continue
        
        angular_errors = []
        for cat_result in results[scenario]:
            if cat_result.get('angular_resolution', {}).get('median_deg'):
                angular_errors.append(cat_result['angular_resolution']['median_deg'])
        
        if angular_errors:
            data_to_plot.append(angular_errors)
            labels.append(scenario_labels.get(scenario, scenario))
    
    if data_to_plot:
        bp = ax.boxplot(data_to_plot, labels=labels, patch_artist=True)
        for patch in bp['boxes']:
            patch.set_facecolor('lightblue')
        
        ax.set_ylabel('Angular Resolution (degrees)', fontsize=12)
        ax.set_title('Angular Resolution Comparison Across Scenarios', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.tick_params(axis='x', rotation=0)


def plot_cluster_statistics(results, scenarios, ax):
    """Plot cluster statistics (main vs non-main, input vs matched)."""
    scenario_labels = {
        'best_case': 'Best Case',
        'ed_network': 'ED Network',
        'full_pipeline': 'Full Pipeline'
    }
    
    x_pos = np.arange(len(scenarios))
    width = 0.35
    
    input_main = []
    matched_main = []
    
    for scenario in scenarios:
        if not results[scenario]:
            input_main.append(0)
            matched_main.append(0)
            continue
        
        # Average across categories
        im = np.mean([r.get('cluster_statistics', {}).get('n_input_main_clusters', 0) 
                      for r in results[scenario]])
        mm = np.mean([r.get('cluster_statistics', {}).get('n_matched_main_clusters', 0) 
                      for r in results[scenario]])
        
        input_main.append(im)
        matched_main.append(mm)
    
    ax.bar(x_pos - width/2, input_main, width, label='Input Main Clusters', color='steelblue', alpha=0.8)
    ax.bar(x_pos + width/2, matched_main, width, label='Matched Main Clusters', color='darkorange', alpha=0.8)
    
    ax.set_ylabel('Average Number of Clusters', fontsize=12)
    ax.set_title('Cluster Filtering Statistics (Main Tracks)', fontsize=14, fontweight='bold')
    ax.set_xticks(x_pos)
    ax.set_xticklabels([scenario_labels.get(s, s) for s in scenarios])
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, axis='y')


def plot_matching_efficiency(results, scenarios, ax):
    """Plot 3-plane matching efficiency for main tracks only."""
    scenario_labels = {
        'best_case': 'Best Case',
        'ed_network': 'ED Network',
        'full_pipeline': 'Full Pipeline'
    }
    
    efficiencies = []
    labels = []
    
    for scenario in scenarios:
        if not results[scenario]:
            continue
        
        # Compute matching efficiency per category (main tracks only)
        cat_efficiencies = []
        for cat_result in results[scenario]:
            cs = cat_result.get('cluster_statistics', {})
            n_input_main = cs.get('n_input_main_clusters', 0)
            n_matched_main = cs.get('n_matched_main_clusters', 0)
            if n_input_main > 0:
                cat_efficiencies.append(100.0 * n_matched_main / n_input_main)
        
        if cat_efficiencies:
            efficiencies.append(cat_efficiencies)
            labels.append(scenario_labels.get(scenario, scenario))
    
    if efficiencies:
        bp = ax.boxplot(efficiencies, labels=labels, patch_artist=True)
        for patch in bp['boxes']:
            patch.set_facecolor('lightgreen')
        
        ax.set_ylabel('Matching Efficiency (%)', fontsize=12)
        ax.set_title('3-Plane Cluster Matching Efficiency (Main Tracks)', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.axhline(y=100, color='r', linestyle='--', alpha=0.3, label='100%')


def plot_per_category_angular_resolution(results, scenarios, ax):
    """Plot angular resolution for each category across scenarios."""
    categories = sorted(set(r['category'] for scenario in scenarios 
                           for r in results[scenario] if results[scenario]))
    
    if not categories:
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', transform=ax.transAxes)
        return
    
    scenario_colors = {
        'best_case': 'blue',
        'ed_network': 'orange',
        'full_pipeline': 'green'
    }
    
    scenario_labels = {
        'best_case': 'Best Case',
        'ed_network': 'ED Network',
        'full_pipeline': 'Full Pipeline'
    }
    
    for scenario in scenarios:
        if not results[scenario]:
            continue
        
        cat_to_res = {r['category']: r.get('angular_resolution', {}).get('median_deg') 
                      for r in results[scenario]}
        
        y_values = [cat_to_res.get(cat) for cat in categories]
        x_values = range(len(categories))
        
        # Plot with markers
        ax.plot(x_values, y_values, 'o-', label=scenario_labels.get(scenario, scenario),
                color=scenario_colors.get(scenario, 'gray'), alpha=0.7, linewidth=2, markersize=4)
    
    ax.set_xlabel('Category', fontsize=12)
    ax.set_ylabel('Median Angular Resolution (degrees)', fontsize=12)
    ax.set_title('Angular Resolution by Category', fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # Show only every Nth category label to avoid crowding
    n_show = max(1, len(categories) // 10)
    ax.set_xticks(range(0, len(categories), n_show))
    ax.set_xticklabels([categories[i] for i in range(0, len(categories), n_show)], rotation=45, ha='right')


def plot_cosine_distribution(results, scenarios, ax):
    """Plot cosine(theta) distribution from ED network with 68% quantile."""
    scenario_colors = {
        'best_case': 'blue',
        'ed_network': 'orange',
        'full_pipeline': 'green'
    }
    
    scenario_labels = {
        'best_case': 'Best Case',
        'ed_network': 'ED Network',
        'full_pipeline': 'Full Pipeline'
    }
    
    # Collect all cosine values from per_event_results
    for scenario in scenarios:
        if not results[scenario]:
            continue
        
        cosines = []
        for cat_result in results[scenario]:
            per_event = cat_result.get('per_event_results', [])
            for event in per_event:
                # cosine(theta) where theta is angular error
                angular_error_deg = event.get('angular_error_deg')
                if angular_error_deg is not None:
                    # cos(theta) for angular error
                    cosine = np.cos(np.radians(angular_error_deg))
                    cosines.append(cosine)
        
        if cosines:
            # Plot histogram
            counts, bins, patches = ax.hist(cosines, bins=50, alpha=0.6, 
                                           label=scenario_labels.get(scenario, scenario),
                                           color=scenario_colors.get(scenario, 'gray'),
                                           edgecolor='black', linewidth=0.5)
            
            # Compute and plot 68% quantile
            p68_cosine = np.percentile(cosines, 32)  # 32nd percentile = lower 68% bound
            ax.axvline(p68_cosine, color=scenario_colors.get(scenario, 'gray'), 
                      linestyle='--', linewidth=2, alpha=0.8,
                      label=f'{scenario_labels.get(scenario, scenario)} 68%: {p68_cosine:.3f}')
    
    ax.set_xlabel('cos(θ) [Angular Error]', fontsize=12)
    ax.set_ylabel('Number of Events', fontsize=12)
    ax.set_title('Cosine Distribution of Angular Errors', fontsize=14, fontweight='bold')
    ax.legend(fontsize=9, loc='upper left')
    ax.grid(True, alpha=0.3)
    ax.set_xlim([0.9, 1.0])  # Focus on the high-precision region


def generate_summary_page(pdf, results, scenarios, stats):
    """Generate summary page with text statistics."""
    fig = plt.figure(figsize=(8.5, 11))
    fig.text(0.5, 0.95, 'SN Pointing Analysis - Summary Report', 
             ha='center', fontsize=18, fontweight='bold')
    
    fig.text(0.5, 0.92, f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
             ha='center', fontsize=10, style='italic')
    
    y_pos = 0.85
    line_height = 0.03
    
    # Overall summary
    fig.text(0.1, y_pos, 'Overall Summary', fontsize=14, fontweight='bold')
    y_pos -= line_height * 1.5
    
    total_cats = max([len(results[s]) for s in scenarios if results[s]], default=0)
    fig.text(0.1, y_pos, f'Total Categories Analyzed: {total_cats}', fontsize=11)
    y_pos -= line_height
    
    fig.text(0.1, y_pos, f'Scenarios Completed: {sum(1 for s in scenarios if results[s])} / {len(scenarios)}', fontsize=11)
    y_pos -= line_height * 2
    
    # Per-scenario statistics
    for scenario in scenarios:
        if not stats[scenario]:
            continue
        
        scenario_names = {
            'best_case': 'Best Case (True Electron Directions)',
            'ed_network': 'ED Network (Perfect MT/CT Tagging)',
            'full_pipeline': 'Full Pipeline (MT → CT → ED)'
        }
        
        fig.text(0.1, y_pos, scenario_names.get(scenario, scenario), fontsize=13, fontweight='bold')
        y_pos -= line_height * 1.3
        
        # Angular resolution
        ar = stats[scenario]['angular_resolution']
        if ar['median']:
            fig.text(0.12, y_pos, f"Angular Resolution:", fontsize=11, fontweight='bold')
            y_pos -= line_height
            fig.text(0.15, y_pos, f"Median: {ar['median']:.2f}° ± {ar['std']:.2f}°", fontsize=10)
            y_pos -= line_height
            fig.text(0.15, y_pos, f"68th percentile: {ar['p68']:.2f}°", fontsize=10)
            y_pos -= line_height
            fig.text(0.15, y_pos, f"90th percentile: {ar['p90']:.2f}°", fontsize=10)
            y_pos -= line_height * 1.2
        
        # Cluster statistics
        cs = stats[scenario]['cluster_statistics']
        fig.text(0.12, y_pos, f"Cluster Statistics (per category average):", fontsize=11, fontweight='bold')
        y_pos -= line_height
        fig.text(0.15, y_pos, f"Input clusters: {cs['n_input']['mean']:.1f} (main: {cs['n_input_main']['mean']:.1f}, non-main: {cs['n_input_non_main']['mean']:.1f})", fontsize=10)
        y_pos -= line_height
        fig.text(0.15, y_pos, f"Matched across 3 planes: {cs['n_matched']['mean']:.1f} (main: {cs['n_matched_main']['mean']:.1f}, non-main: {cs['n_matched_non_main']['mean']:.1f})", fontsize=10)
        y_pos -= line_height
        
        # Matching efficiency
        if cs['n_input']['mean'] > 0:
            eff = 100.0 * cs['n_matched']['mean'] / cs['n_input']['mean']
            fig.text(0.15, y_pos, f"Matching efficiency: {eff:.2f}%", fontsize=10)
            y_pos -= line_height * 1.8
        else:
            y_pos -= line_height * 1.8
    
    # Key findings section
    if y_pos > 0.15:
        fig.text(0.1, y_pos, 'Key Findings', fontsize=14, fontweight='bold')
        y_pos -= line_height * 1.5
        
        # Compare best case vs full pipeline
        if stats.get('best_case') and stats.get('full_pipeline'):
            bc_res = stats['best_case']['angular_resolution']['median']
            fp_res = stats['full_pipeline']['angular_resolution']['median']
            if bc_res and fp_res:
                degradation = fp_res - bc_res
                fig.text(0.12, y_pos, f"• Pipeline degradation vs. best case: {degradation:.2f}° ({100*degradation/bc_res:.1f}%)", fontsize=10)
                y_pos -= line_height
        
        # Main cluster matching
        if stats.get('best_case'):
            cs = stats['best_case']['cluster_statistics']
            main_frac = 100.0 * cs['n_matched_main']['mean'] / cs['n_matched']['mean'] if cs['n_matched']['mean'] > 0 else 0
            fig.text(0.12, y_pos, f"• Main tracks in matched clusters: {main_frac:.1f}%", fontsize=10)
            y_pos -= line_height
    
    plt.axis('off')
    pdf.savefig(fig, bbox_inches='tight')
    plt.close()


def generate_report(results_dir, output_file, scenarios=['best_case', 'ed_network', 'full_pipeline']):
    """Generate comprehensive PDF report."""
    
    print(f"Loading results from {results_dir}...")
    results = load_all_results(results_dir, scenarios)
    
    # Check if we have any data
    if not any(results[s] for s in scenarios):
        print("ERROR: No results found in the specified directory")
        return False
    
    print("Computing aggregate statistics...")
    stats = compute_aggregate_stats(results, scenarios)
    
    print(f"Generating PDF report: {output_file}")
    with PdfPages(output_file) as pdf:
        # Page 1: Summary
        generate_summary_page(pdf, results, scenarios, stats)
        
        # Page 2: Plots (2x2 grid)
        fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
        fig.suptitle('SN Pointing Analysis - Detailed Statistics', fontsize=16, fontweight='bold')
        
        plot_angular_resolution_comparison(results, scenarios, axes[0, 0])
        plot_cluster_statistics(results, scenarios, axes[0, 1])
        plot_matching_efficiency(results, scenarios, axes[1, 0])
        plot_per_category_angular_resolution(results, scenarios, axes[1, 1])
        
        plt.tight_layout(rect=[0, 0, 1, 0.97])
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        # Page 3: Cosine Distribution
        fig = plt.figure(figsize=(11, 8.5))
        ax = fig.add_subplot(111)
        
        plot_cosine_distribution(results, scenarios, ax)
        
        fig.suptitle('SN Pointing Analysis - Cosine Distribution (68% Quantile)', 
                     fontsize=16, fontweight='bold')
        plt.tight_layout(rect=[0, 0, 1, 0.97])
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        # Save metadata
        d = pdf.infodict()
        d['Title'] = 'SN Pointing Systematic Analysis Report'
        d['Author'] = 'DUNE SN Analysis Pipeline'
        d['Subject'] = 'Angular Resolution and Cluster Statistics'
        d['Keywords'] = 'DUNE, Supernova, Pointing, Angular Resolution'
        d['CreationDate'] = datetime.now()
    
    print(f"Report saved to: {output_file}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Generate PDF report for SN pointing systematic analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate report from test results
  python generate_sn_report.py --results-dir results/systematic_sn_test --output report_test.pdf
  
  # Generate report for all scenarios
  python generate_sn_report.py --results-dir results/systematic_sn --output full_report.pdf
  
  # Generate report for specific scenarios only
  python generate_sn_report.py --results-dir results/systematic_sn --output report.pdf --scenarios best_case full_pipeline
        """
    )
    
    parser.add_argument('--results-dir', type=str, required=True,
                        help='Directory containing scenario results (e.g., results/systematic_sn)')
    parser.add_argument('--output', type=str, required=True,
                        help='Output PDF file path (e.g., sn_report.pdf)')
    parser.add_argument('--scenarios', nargs='+', 
                        default=['best_case', 'ed_network', 'full_pipeline'],
                        help='Scenarios to include in report')
    
    args = parser.parse_args()
    
    # Validate inputs
    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        print(f"ERROR: Results directory not found: {results_dir}")
        return 1
    
    # Generate report
    success = generate_report(args.results_dir, args.output, args.scenarios)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
