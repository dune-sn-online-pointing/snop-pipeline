#!/usr/bin/env python3
"""
Add cluster tracking page to existing PDF report
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from pathlib import Path

SCENARIOS = ['best_case', 'perfect_ct', 'full_pipeline', 'weighted_ct',
             'perfect_ct_e_gt_10mev', 'perfect_ct_e_gt_20mev']

SCENARIO_LABELS = {
    'best_case': 'Best Case\n(True e⁻)',
    'perfect_ct': 'Perfect CT\n(ES + ED)',
    'full_pipeline': 'Full Pipeline\n(CT + ED)',
    'weighted_ct': 'Weighted CT',
    'perfect_ct_e_gt_10mev': 'Perfect CT\n(E>10 MeV)',
    'perfect_ct_e_gt_20mev': 'Perfect CT\n(E>20 MeV)'
}

def load_cluster_stats(base_path, cat_names):
    """Load cluster statistics for given cats"""
    base = Path(base_path)
    
    tracking = {scenario: {
        'n_total_input': [],
        'n_es_main_input': [],
        'n_clusters_used': []
    } for scenario in SCENARIOS}
    
    for cat_name in cat_names:
        cat_dir = base / cat_name
        pipeline_dir = cat_dir / 'pipeline'
        
        # Count input clusters
        cluster_dir = cat_dir / f'{cat_name}_cluster_images_tick3_ch2_min2_tot3_e3p0'
        try:
            n_es_main = len(list(cluster_dir.glob('*/es_*.npz')))
            n_cc = len(list(cluster_dir.glob('*/cc_*.npz')))
            n_total = n_es_main + n_cc
            
            for scenario in SCENARIOS:
                file_path = pipeline_dir / f'{cat_name}_scenario_{scenario}_emcee.npz'
                if file_path.exists():
                    data = np.load(file_path)
                    key_n_clusters = f'{scenario}_emcee_n_clusters_used'
                    if key_n_clusters in data:
                        tracking[scenario]['n_total_input'].append(n_total)
                        tracking[scenario]['n_es_main_input'].append(n_es_main)
                        tracking[scenario]['n_clusters_used'].append(int(data[key_n_clusters]))
        except Exception as e:
            print(f"Warning: Could not process {cat_name}: {e}")
            continue
    
    return tracking

def create_tracking_table(tracking):
    """Create a summary table figure"""
    fig = plt.figure(figsize=(18, 10))
    ax = plt.gca()
    ax.axis('off')
    
    # Prepare table data
    table_data = [['Scenario', 'N Cats', 'Input\nTotal', 'Input\nES Main', 
                   'Clusters\nUsed', 'Total\nRetention', 'ES Loss']]
    
    for scenario in SCENARIOS:
        t = tracking[scenario]
        if len(t['n_clusters_used']) > 0:
            n_cats = len(t['n_clusters_used'])
            total_in = np.mean(t['n_total_input'])
            es_in = np.mean(t['n_es_main_input'])
            used = np.mean(t['n_clusters_used'])
            retention = (used / total_in * 100) if total_in > 0 else 0
            es_lost = es_in - (used * es_in / total_in)  # Rough estimate
            
            table_data.append([
                SCENARIO_LABELS[scenario].replace('\n', ' '),
                f'{n_cats}',
                f'{total_in:.0f}',
                f'{es_in:.0f}',
                f'{used:.0f}',
                f'{retention:.1f}%',
                f'{es_lost:.0f}'
            ])
    
    table = ax.table(cellText=table_data, cellLoc='center', loc='center',
                    colWidths=[0.25, 0.1, 0.1, 0.1, 0.1, 0.12, 0.1])
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 3)
    
    # Style header row
    for i in range(7):
        table[(0, i)].set_facecolor('#4CAF50')
        table[(0, i)].set_text_props(weight='bold', color='white')
    
    # Style data rows
    for i in range(1, len(table_data)):
        for j in range(7):
            table[(i, j)].set_facecolor('#f0f0f0' if i % 2 == 0 else 'white')
    
    plt.title('ES Main Track Retention Across Scenarios', fontsize=16, fontweight='bold', pad=20)
    
    return fig

if __name__ == '__main__':
    # Load cat names from previous analysis
    base_path = '/eos/project-e/ep-nu/evilla/sn-pointing'
    base = Path(base_path)
    
    # Find cats with all scenarios (quick check from first scenario only)
    cat_names = []
    for cat_dir in sorted(list(base.glob('cat*'))[:100]):  # Limit to first 100 for speed
        cat_name = cat_dir.name
        pipeline_dir = cat_dir / 'pipeline'
        first_file = pipeline_dir / f'{cat_name}_scenario_best_case_emcee.npz'
        if first_file.exists():
            cat_names.append(cat_name)
    
    print(f"Loading tracking stats for {len(cat_names)} cats...")
    tracking = load_cluster_stats(base_path, cat_names)
    
    print("\n=== CLUSTER TRACKING STATISTICS ===\n")
    for scenario in SCENARIOS:
        t = tracking[scenario]
        if len(t['n_clusters_used']) > 0:
            print(f"{SCENARIO_LABELS[scenario].replace(chr(10), ' ')}:")
            print(f"  Cats: {len(t['n_clusters_used'])}")
            print(f"  Input Total: {np.mean(t['n_total_input']):.1f} ± {np.std(t['n_total_input']):.1f}")
            print(f"  Input ES Main: {np.mean(t['n_es_main_input']):.1f} ± {np.std(t['n_es_main_input']):.1f}")
            print(f"  Used: {np.mean(t['n_clusters_used']):.1f} ± {np.std(t['n_clusters_used']):.1f}")
            retention = np.mean(t['n_clusters_used']) / np.mean(t['n_total_input']) * 100
            print(f"  Retention: {retention:.1f}%")
            print()
    
    # Create figure
    fig = create_tracking_table(tracking)
    fig.savefig('cluster_tracking_table.pdf', bbox_inches='tight')
    print("\n✓ Saved cluster tracking table to: cluster_tracking_table.pdf")
