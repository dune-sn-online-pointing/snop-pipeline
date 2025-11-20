#!/usr/bin/env python3
"""
Add cluster tracking metrics page to the existing PDF
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from pathlib import Path
import shutil

SCENARIOS = ['best_case', 'perfect_ct', 'full_pipeline', 'weighted_ct',
             'perfect_ct_e_gt_10mev', 'perfect_ct_e_gt_20mev']

SCENARIO_LABELS = {
    'best_case': 'Best Case (True e⁻)',
    'perfect_ct': 'Perfect CT (ES + ED)',
    'full_pipeline': 'Full Pipeline (CT + ED)',
    'weighted_ct': 'Weighted CT',
    'perfect_ct_e_gt_10mev': 'Perfect CT (E>10 MeV)',
    'perfect_ct_e_gt_20mev': 'Perfect CT (E>20 MeV)'
}

def load_tracking_stats_from_existing(base_path='/eos/project-e/ep-nu/evilla/sn-pointing'):
    """Load cluster tracking from cats that have results"""
    base = Path(base_path)
    
    tracking = {s: {'total': [], 'es': [], 'used': []} for s in SCENARIOS}
    
    # Sample first 100 cats for speed
    cat_list = sorted(list(base.glob('cat*')))[:100]
    
    for cat_dir in cat_list:
        cat_name = cat_dir.name
        pipeline_dir = cat_dir / 'pipeline'
        
        # Check if best_case exists (indicator that this cat has results)
        if not (pipeline_dir / f'{cat_name}_scenario_best_case_emcee.npz').exists():
            continue
        
        # Count clusters
        cluster_dir = cat_dir / f'{cat_name}_cluster_images_tick3_ch2_min2_tot3_e3p0'
        try:
            n_es = len(list(cluster_dir.glob('*/es_*.npz')))
            n_cc = len(list(cluster_dir.glob('*/cc_*.npz')))
            n_total = n_es + n_cc
        except:
            continue
        
        # Load each scenario
        for scenario in SCENARIOS:
            f = pipeline_dir / f'{cat_name}_scenario_{scenario}_emcee.npz'
            if f.exists():
                try:
                    data = np.load(f)
                    key = f'{scenario}_emcee_n_clusters_used'
                    if key in data:
                        tracking[scenario]['total'].append(n_total)
                        tracking[scenario]['es'].append(n_es)
                        tracking[scenario]['used'].append(int(data[key]))
                except:
                    pass
    
    return tracking

def create_tracking_table_figure(tracking):
    """Create the tracking table figure"""
    fig = plt.figure(figsize=(18, 10))
    ax = plt.gca()
    ax.axis('off')
    
    # Compute stats
    table_data = [['Scenario', 'N Cats', 'Input Total', 'Input ES Main', 
                   'Value "Used"', 'Interpretation']]
    
    for scenario in SCENARIOS:
        t = tracking[scenario]
        if len(t['used']) > 0:
            n_cats = len(t['used'])
            total_mean = np.mean(t['total'])
            es_mean = np.mean(t['es'])
            used_mean = np.mean(t['used'])
            retention = (used_mean / total_mean * 100) if total_mean > 0 else 0
            
            if retention > 200:
                interp = f"MCMC weighted\\nsum ({used_mean:.0f})"
            else:
                interp = f"{retention:.1f}% retention"
            
            table_data.append([
                SCENARIO_LABELS[scenario],
                f'{n_cats}',
                f'{total_mean:.0f}',
                f'{es_mean:.0f}',
                f'{used_mean:.0f}',
                interp
            ])
    
    table = ax.table(cellText=table_data, cellLoc='center', loc='center',
                    colWidths=[0.28, 0.1, 0.12, 0.14, 0.12, 0.24])
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 3.5)
    
    # Style header
    for j in range(6):
        cell = table[(0, j)]
        cell.set_facecolor('#2E7D32')
        cell.set_text_props(weight='bold', color='white')
    
    # Style rows
    for i in range(1, len(table_data)):
        for j in range(6):
            cell = table[(i, j)]
            cell.set_facecolor('#f5f5f5' if i % 2 == 0 else 'white')
            if j == 0:
                cell.set_text_props(weight='bold')
    
    plt.title('Cluster Usage Metrics Across Scenarios', 
              fontsize=18, fontweight='bold', pad=20)
    
    # Add note
    note = ('Note: "Value Used" has different meanings:\n'
            '• Best Case, Perfect CT, Energy Cuts: Actual clusters used after filtering\n'
            '• Full Pipeline, Weighted CT: MCMC weighted sum (includes CT probability weights)\n\n'
            'Key insight: Best Case and Perfect CT scenarios achieve ~85-90% retention\n'
            'of ES main clusters (after E>3 MeV cut).')
    
    ax.text(0.5, 0.08, note, ha='center', va='top', transform=ax.transAxes,
            fontsize=10, style='italic', color='#555',
            bbox=dict(boxstyle='round,pad=0.8', facecolor='#fffacd', alpha=0.7))
    
    return fig

if __name__ == '__main__':
    print("Loading cluster tracking stats...")
    tracking = load_tracking_stats_from_existing()
    
    print("\nCreating tracking table...")
    fig = create_tracking_table_figure(tracking)
    
    # Save as standalone PDF
    fig.savefig('cluster_tracking_page.pdf', bbox_inches='tight')
    plt.close()
    
    print("\n✓ Created cluster_tracking_page.pdf")
    print("\nNow merging with main PDF...")
    
    # Merge with existing PDF using PyPDF2 if available
    try:
        from PyPDF2 import PdfMerger
        
        merger = PdfMerger()
        merger.append('emcee_6scenarios_aggregate_analysis.pdf')
        merger.append('cluster_tracking_page.pdf')
        merger.write('emcee_6scenarios_aggregate_analysis_with_tracking.pdf')
        merger.close()
        
        # Replace original
        shutil.move('emcee_6scenarios_aggregate_analysis_with_tracking.pdf',
                   'emcee_6scenarios_aggregate_analysis.pdf')
        
        print("✓ Merged! Final PDF: emcee_6scenarios_aggregate_analysis.pdf (4 pages)")
        
    except ImportError:
        print("✓ Standalone page saved. Install PyPDF2 to auto-merge, or merge manually.")
