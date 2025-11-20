#!/usr/bin/env python3
"""
Compute ES main track retention metrics for each scenario
"""
import numpy as np
from pathlib import Path

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

def compute_tracking_stats(base_path='/eos/project-e/ep-nu/evilla/sn-pointing'):
    """Compute cluster tracking statistics across all cats"""
    base = Path(base_path)
    
    tracking = {scenario: {
        'n_total_input': [],
        'n_es_main_input': [],
        'n_clusters_used': [],
        'n_es_after_energy_cut': [],
        'cat_names': []
    } for scenario in SCENARIOS}
    
    for cat_dir in sorted(base.glob('cat*')):
        cat_name = cat_dir.name
        pipeline_dir = cat_dir / 'pipeline'
        
        # Check if this cat has all 6 emcee scenarios
        has_all = all((pipeline_dir / f'{cat_name}_scenario_{scenario}_emcee.npz').exists() 
                     for scenario in SCENARIOS)
        
        if not has_all:
            continue
        
        # Count input clusters
        cluster_dir = cat_dir / f'{cat_name}_cluster_images_tick3_ch2_min2_tot3_e3p0'
        n_es_main = len(list(cluster_dir.glob('*/es_*.npz')))
        n_cc = len(list(cluster_dir.glob('*/cc_*.npz')))
        n_total = n_es_main + n_cc
        
        for scenario in SCENARIOS:
            file_path = pipeline_dir / f'{cat_name}_scenario_{scenario}_emcee.npz'
            data = np.load(file_path)
            
            key_n_clusters = f'{scenario}_emcee_n_clusters_used'
            if key_n_clusters in data:
                tracking[scenario]['n_total_input'].append(n_total)
                tracking[scenario]['n_es_main_input'].append(n_es_main)
                tracking[scenario]['n_clusters_used'].append(int(data[key_n_clusters]))
                tracking[scenario]['cat_names'].append(cat_name)
                
                # For energy cut scenarios, estimate ES main after cut
                # (This is approximate - actual count would need to be saved in emcee output)
                if 'e_gt' in scenario:
                    # Rough estimate: proportional to total used clusters
                    est_es_after_cut = int(n_es_main * int(data[key_n_clusters]) / n_total)
                    tracking[scenario]['n_es_after_energy_cut'].append(est_es_after_cut)
                else:
                    tracking[scenario]['n_es_after_energy_cut'].append(n_es_main)
    
    # Compute aggregated statistics
    stats = {}
    for scenario in SCENARIOS:
        if len(tracking[scenario]['n_clusters_used']) > 0:
            stats[scenario] = {
                'n_cats': len(tracking[scenario]['cat_names']),
                'total_input_mean': np.mean(tracking[scenario]['n_total_input']),
                'total_input_std': np.std(tracking[scenario]['n_total_input']),
                'es_main_input_mean': np.mean(tracking[scenario]['n_es_main_input']),
                'es_main_input_std': np.std(tracking[scenario]['n_es_main_input']),
                'clusters_used_mean': np.mean(tracking[scenario]['n_clusters_used']),
                'clusters_used_std': np.std(tracking[scenario]['n_clusters_used']),
                'es_after_cut_mean': np.mean(tracking[scenario]['n_es_after_energy_cut']),
                'es_after_cut_std': np.std(tracking[scenario]['n_es_after_energy_cut']),
                'retention_rate': np.mean(tracking[scenario]['n_clusters_used']) / np.mean(tracking[scenario]['n_total_input']) * 100,
                'es_retention_rate': np.mean(tracking[scenario]['n_es_after_energy_cut']) / np.mean(tracking[scenario]['n_es_main_input']) * 100
            }
        else:
            stats[scenario] = None
    
    return stats, tracking

if __name__ == '__main__':
    stats, tracking = compute_tracking_stats()
    
    print("\n=== CLUSTER TRACKING STATISTICS ===\n")
    for scenario in SCENARIOS:
        if stats[scenario] is not None:
            s = stats[scenario]
            print(f"{SCENARIO_LABELS[scenario]}:")
            print(f"  Cats: {s['n_cats']}")
            print(f"  Input Total Clusters: {s['total_input_mean']:.1f} ± {s['total_input_std']:.1f}")
            print(f"  Input ES Main: {s['es_main_input_mean']:.1f} ± {s['es_main_input_std']:.1f}")
            print(f"  Clusters Used: {s['clusters_used_mean']:.1f} ± {s['clusters_used_std']:.1f}")
            print(f"  Overall Retention: {s['retention_rate']:.1f}%")
            print(f"  ES Main Retention: {s['es_retention_rate']:.1f}%")
            print()
