#!/usr/bin/env python3
"""
Plot angular resolution results from emcee analysis across all scenarios.
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys

# Scenarios
SCENARIOS = [
    'perfect_ct',
    'es_main_cc_shower',
    'es_main_cc_all',
    'es_all_cc_shower',
    'es_all_cc_all',
    'all_tracks_all_showers'
]

SCENARIO_LABELS = {
    'perfect_ct': 'Perfect CT',
    'es_main_cc_shower': 'ES Main CC Shower',
    'es_main_cc_all': 'ES Main CC All',
    'es_all_cc_shower': 'ES All CC Shower',
    'es_all_cc_all': 'ES All CC All',
    'all_tracks_all_showers': 'All Tracks/Showers'
}

def load_results(base_path='/eos/project-e/ep-nu/evilla/sn-pointing'):
    """Load all emcee results."""
    base = Path(base_path)
    results = {scenario: [] for scenario in SCENARIOS}
    cat_names = {scenario: [] for scenario in SCENARIOS}
    
    # Find all cats with emcee results
    for cat_dir in sorted(base.glob('cat*')):
        cat_name = cat_dir.name
        pipeline_dir = cat_dir / 'pipeline'
        
        if not pipeline_dir.exists():
            continue
        
        # Check each scenario
        for scenario in SCENARIOS:
            emcee_file = pipeline_dir / f"{cat_name}_scenario_{scenario}_emcee.npz"
            
            if emcee_file.exists():
                try:
                    data = np.load(emcee_file)
                    key = f"{scenario}_emcee_angular_error_deg"
                    
                    if key in data:
                        angular_error = float(data[key])
                        results[scenario].append(angular_error)
                        cat_names[scenario].append(cat_name)
                except Exception as e:
                    print(f"Warning: Could not load {emcee_file}: {e}", file=sys.stderr)
    
    return results, cat_names

def plot_results(results, cat_names):
    """Create comprehensive plots of the results."""
    
    # Convert to arrays and calculate statistics
    stats = {}
    for scenario in SCENARIOS:
        if results[scenario]:
            arr = np.array(results[scenario])
            stats[scenario] = {
                'data': arr,
                'mean': np.mean(arr),
                'median': np.median(arr),
                'std': np.std(arr),
                'n': len(arr),
                'min': np.min(arr),
                'max': np.max(arr),
                'q25': np.percentile(arr, 25),
                'q75': np.percentile(arr, 75)
            }
        else:
            stats[scenario] = None
    
    # Create figure with multiple subplots
    fig = plt.figure(figsize=(16, 10))
    
    # 1. Box plot comparison
    ax1 = plt.subplot(2, 3, 1)
    plot_data = []
    plot_labels = []
    plot_colors = []
    colors = plt.cm.tab10(np.linspace(0, 1, len(SCENARIOS)))
    
    for i, scenario in enumerate(SCENARIOS):
        if stats[scenario] is not None:
            plot_data.append(stats[scenario]['data'])
            plot_labels.append(SCENARIO_LABELS[scenario])
            plot_colors.append(colors[i])
    
    bp = ax1.boxplot(plot_data, labels=plot_labels, patch_artist=True, 
                     notch=True, showmeans=True)
    for patch, color in zip(bp['boxes'], plot_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    
    ax1.set_ylabel('Angular Error (degrees)', fontsize=11)
    ax1.set_title('Angular Resolution by Scenario', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.tick_params(axis='x', rotation=45, labelsize=9)
    
    # 2. Violin plot
    ax2 = plt.subplot(2, 3, 2)
    parts = ax2.violinplot(plot_data, positions=range(len(plot_data)), 
                          showmeans=True, showmedians=True)
    for pc, color in zip(parts['bodies'], plot_colors):
        pc.set_facecolor(color)
        pc.set_alpha(0.6)
    
    ax2.set_xticks(range(len(plot_labels)))
    ax2.set_xticklabels(plot_labels, rotation=45, ha='right', fontsize=9)
    ax2.set_ylabel('Angular Error (degrees)', fontsize=11)
    ax2.set_title('Distribution Shapes', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    
    # 3. Sample size and statistics table
    ax3 = plt.subplot(2, 3, 3)
    ax3.axis('off')
    
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
    
    table = ax3.table(cellText=table_data,
                     colLabels=['Scenario', 'N', 'Mean', 'Median', 'Std'],
                     cellLoc='center',
                     loc='center',
                     bbox=[0, 0.2, 1, 0.7])
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 2)
    
    # Style header
    for i in range(5):
        table[(0, i)].set_facecolor('#4CAF50')
        table[(0, i)].set_text_props(weight='bold', color='white')
    
    # Alternate row colors
    for i in range(1, len(table_data) + 1):
        for j in range(5):
            if i % 2 == 0:
                table[(i, j)].set_facecolor('#f0f0f0')
    
    ax3.set_title('Summary Statistics', fontsize=12, fontweight='bold', pad=20)
    
    # 4. Histogram comparison
    ax4 = plt.subplot(2, 3, 4)
    for i, scenario in enumerate(SCENARIOS):
        if stats[scenario] is not None:
            ax4.hist(stats[scenario]['data'], bins=20, alpha=0.5, 
                    label=SCENARIO_LABELS[scenario], color=colors[i])
    
    ax4.set_xlabel('Angular Error (degrees)', fontsize=11)
    ax4.set_ylabel('Count', fontsize=11)
    ax4.set_title('Error Distribution Overlay', fontsize=12, fontweight='bold')
    ax4.legend(fontsize=8, loc='upper right')
    ax4.grid(True, alpha=0.3)
    
    # 5. Cumulative distribution
    ax5 = plt.subplot(2, 3, 5)
    for i, scenario in enumerate(SCENARIOS):
        if stats[scenario] is not None:
            sorted_data = np.sort(stats[scenario]['data'])
            cumulative = np.arange(1, len(sorted_data) + 1) / len(sorted_data) * 100
            ax5.plot(sorted_data, cumulative, label=SCENARIO_LABELS[scenario], 
                    color=colors[i], linewidth=2)
    
    ax5.set_xlabel('Angular Error (degrees)', fontsize=11)
    ax5.set_ylabel('Cumulative Percentage (%)', fontsize=11)
    ax5.set_title('Cumulative Distribution', fontsize=12, fontweight='bold')
    ax5.legend(fontsize=8, loc='lower right')
    ax5.grid(True, alpha=0.3)
    ax5.axhline(y=68, color='r', linestyle='--', alpha=0.5, label='68% CL')
    
    # 6. Mean comparison bar plot
    ax6 = plt.subplot(2, 3, 6)
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
    bars = ax6.bar(x_pos, means, yerr=stds, capsize=5, alpha=0.7, 
                   color=bar_colors, edgecolor='black')
    
    # Add value labels on bars
    for i, (bar, mean, std) in enumerate(zip(bars, means, stds)):
        height = bar.get_height()
        ax6.text(bar.get_x() + bar.get_width()/2., height,
                f'{mean:.1f}°\n±{std:.1f}°',
                ha='center', va='bottom', fontsize=8, fontweight='bold')
    
    ax6.set_xticks(x_pos)
    ax6.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
    ax6.set_ylabel('Mean Angular Error (degrees)', fontsize=11)
    ax6.set_title('Mean Resolution with Std Dev', fontsize=12, fontweight='bold')
    ax6.grid(True, alpha=0.3, axis='y')
    
    plt.suptitle('Emcee Angular Resolution Analysis - All Scenarios', 
                fontsize=14, fontweight='bold', y=0.995)
    plt.tight_layout()
    
    # Save figure
    output_file = 'emcee_resolution_analysis.png'
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\n✓ Saved plot to: {output_file}")
    
    # Print detailed statistics
    print("\n" + "="*80)
    print("DETAILED STATISTICS")
    print("="*80)
    
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
    
    print("\n" + "="*80)
    
    # Show the plot
    plt.show()

def main():
    print("Loading emcee results...")
    results, cat_names = load_results()
    
    # Summary
    total_cats = sum(len(cats) for cats in cat_names.values())
    print(f"\nLoaded results for {total_cats} total cat-scenario combinations:")
    for scenario in SCENARIOS:
        n = len(results[scenario])
        print(f"  {SCENARIO_LABELS[scenario]}: {n} cats")
    
    if total_cats == 0:
        print("\nNo results found!")
        return
    
    print("\nGenerating plots...")
    plot_results(results, cat_names)

if __name__ == '__main__':
    main()
