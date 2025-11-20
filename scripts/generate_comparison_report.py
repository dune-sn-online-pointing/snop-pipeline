#!/usr/bin/env python3
"""
Generate comprehensive PDF report comparing all three scenarios.
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.patches as mpatches

def compute_angular_error(dir1, dir2):
    """Compute angular error in degrees between two directions."""
    cosine = np.clip(np.dot(dir1, dir2), -1.0, 1.0)
    return np.degrees(np.arccos(cosine))

def main():
    # Load results
    s1 = np.load('results/cat000001_scenario1_best_case.npz', allow_pickle=True)
    s2 = np.load('results/cat000001_scenario2_perfect_ct.npz', allow_pickle=True)
    s3 = np.load('results/cat000001_scenario3_full_pipeline.npz', allow_pickle=True)
    
    # Extract data
    true_dir = s1['best_case_true_nu_direction']
    
    scenarios = {
        'Scenario 1\nBest Case': {
            'n_clusters': int(s1['best_case_n_clusters_used']),
            'angular_error': float(s1['best_case_angular_error_deg']),
            'reconstructed': s1['best_case_reconstructed_direction'],
            'log_likelihood': float(s1['best_case_log_likelihood']),
            'all_directions': s1['best_case_all_trial_directions'],
            'all_log_likes': s1['best_case_all_trial_log_likes'],
            'description': 'True electron directions\nES main tracks only'
        },
        'Scenario 2\nPerfect CT': {
            'n_clusters': int(s2['perfect_ct_n_clusters_used']),
            'angular_error': float(s2['perfect_ct_angular_error_deg']),
            'reconstructed': s2['perfect_ct_reconstructed_direction'],
            'log_likelihood': float(s2['perfect_ct_log_likelihood']),
            'all_directions': s2['perfect_ct_all_trial_directions'],
            'all_log_likes': s2['perfect_ct_all_trial_log_likes'],
            'description': 'ED Network predictions\nES main tracks only'
        },
        'Scenario 3\nFull Pipeline': {
            'n_clusters': int(s3['full_pipeline_n_clusters_used']),
            'angular_error': float(s3['full_pipeline_angular_error_deg']),
            'reconstructed': s3['full_pipeline_reconstructed_direction'],
            'log_likelihood': float(s3['full_pipeline_log_likelihood']),
            'all_directions': s3['full_pipeline_all_trial_directions'],
            'all_log_likes': s3['full_pipeline_all_trial_log_likes'],
            'description': 'CT → ED → MCMC\nCT filtered clusters'
        }
    }
    
    # Create PDF report
    pdf_path = 'results/cat000001_comparison_report.pdf'
    with PdfPages(pdf_path) as pdf:
        
        # Page 1: Summary comparison
        fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
        fig.suptitle('CAT000001 SN Pointing Analysis - Three Scenarios Comparison', 
                     fontsize=14, fontweight='bold')
        
        # Angular error comparison
        ax = axes[0, 0]
        names = list(scenarios.keys())
        errors = [scenarios[n]['angular_error'] for n in names]
        colors = ['#2ecc71', '#3498db', '#e74c3c']
        bars = ax.bar(range(len(names)), errors, color=colors, alpha=0.7, edgecolor='black')
        ax.set_ylabel('Angular Error (degrees)', fontweight='bold')
        ax.set_title('Angular Resolution Comparison')
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, fontsize=9)
        ax.grid(axis='y', alpha=0.3)
        for i, (bar, err) in enumerate(zip(bars, errors)):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, 
                   f'{err:.2f}°', ha='center', fontweight='bold')
        
        # Cluster count comparison
        ax = axes[0, 1]
        n_clusters = [scenarios[n]['n_clusters'] for n in names]
        bars = ax.bar(range(len(names)), n_clusters, color=colors, alpha=0.7, edgecolor='black')
        ax.set_ylabel('Number of Clusters', fontweight='bold')
        ax.set_title('Clusters Used in MCMC')
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, fontsize=9)
        ax.grid(axis='y', alpha=0.3)
        for i, (bar, n) in enumerate(zip(bars, n_clusters)):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 50, 
                   f'{n}', ha='center', fontweight='bold')
        
        # Performance degradation
        ax = axes[1, 0]
        s1_err = scenarios['Scenario 1\nBest Case']['angular_error']
        s2_err = scenarios['Scenario 2\nPerfect CT']['angular_error']
        s3_err = scenarios['Scenario 3\nFull Pipeline']['angular_error']
        
        degradations = [0, s2_err - s1_err, s3_err - s1_err]
        bars = ax.bar(range(len(names)), degradations, color=colors, alpha=0.7, edgecolor='black')
        ax.axhline(y=0, color='k', linestyle='--', linewidth=1)
        ax.set_ylabel('Degradation vs Best Case (degrees)', fontweight='bold')
        ax.set_title('Performance Degradation')
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, fontsize=9)
        ax.grid(axis='y', alpha=0.3)
        for i, (bar, deg) in enumerate(zip(bars, degradations)):
            y_pos = deg + (0.5 if deg > 0 else -0.5)
            ax.text(bar.get_x() + bar.get_width()/2, y_pos, 
                   f'{deg:+.2f}°', ha='center', fontweight='bold')
        
        # Summary table
        ax = axes[1, 1]
        ax.axis('off')
        
        s1_name = 'Scenario 1\nBest Case'
        s2_name = 'Scenario 2\nPerfect CT'
        s3_name = 'Scenario 3\nFull Pipeline'
        
        table_data = [
            ['Metric', 'Scenario 1', 'Scenario 2', 'Scenario 3'],
            ['Angular Error', f'{s1_err:.2f}°', f'{s2_err:.2f}°', f'{s3_err:.2f}°'],
            ['Clusters Used', f'{scenarios[s1_name]["n_clusters"]}', 
             f'{scenarios[s2_name]["n_clusters"]}',
             f'{scenarios[s3_name]["n_clusters"]}'],
            ['Log-Likelihood', 
             f'{scenarios[s1_name]["log_likelihood"]:.1f}',
             f'{scenarios[s2_name]["log_likelihood"]:.1f}',
             f'{scenarios[s3_name]["log_likelihood"]:.1f}'],
            ['Relative Perf.', '1.00x', f'{s2_err/s1_err:.2f}x', f'{s3_err/s1_err:.2f}x']
        ]
        
        table = ax.table(cellText=table_data, loc='center', cellLoc='center',
                        colWidths=[0.3, 0.23, 0.23, 0.23])
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1, 2)
        
        # Style header row
        for i in range(4):
            table[(0, i)].set_facecolor('#34495e')
            table[(0, i)].set_text_props(weight='bold', color='white')
        
        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        # Page 2: MCMC convergence comparison - show chains converging
        fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
        fig.suptitle('MCMC Chain Convergence', fontsize=14, fontweight='bold')
        
        for idx, (name, data) in enumerate(scenarios.items()):
            row = idx // 2
            col = idx % 2
            ax = axes[row, col]
            
            all_dirs = data['all_directions']
            all_likes = data['all_log_likes']
            all_errs = np.array([compute_angular_error(d, true_dir) for d in all_dirs])
            
            # Plot chain with running average to show convergence
            window = 100
            if len(all_errs) > window:
                running_avg = np.convolve(all_errs, np.ones(window)/window, mode='valid')
                ax.plot(range(len(all_errs)), all_errs, '-', alpha=0.2, color=colors[idx], linewidth=0.5)
                ax.plot(range(window-1, len(all_errs)), running_avg, '-', alpha=0.8, 
                       color=colors[idx], linewidth=2, label='Running average (100 steps)')
            else:
                ax.plot(range(len(all_errs)), all_errs, '-', alpha=0.6, color=colors[idx])
            
            ax.axhline(y=data['angular_error'], color='red', linestyle='--', 
                      label=f'Best: {data["angular_error"]:.2f}°', linewidth=2)
            ax.set_xlabel('MCMC Step', fontweight='bold')
            ax.set_ylabel('Angular Error (degrees)', fontweight='bold')
            ax.set_title(f'{name}\n{len(all_dirs)} chain steps', fontsize=10)
            ax.legend(fontsize=8)
            ax.grid(alpha=0.3)
            
        axes[1, 1].axis('off')
        
        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        # Page 3: 3D direction visualization
        fig = plt.figure(figsize=(11, 8.5))
        fig.suptitle('Reconstructed vs True Neutrino Direction (3D)', 
                     fontsize=14, fontweight='bold')
        
        ax = fig.add_subplot(111, projection='3d')
        
        # Plot true direction
        ax.quiver(0, 0, 0, true_dir[0], true_dir[1], true_dir[2], 
                 color='black', arrow_length_ratio=0.1, linewidth=3,
                 label='True ν direction')
        
        # Plot reconstructed directions
        for idx, (name, data) in enumerate(scenarios.items()):
            rec_dir = data['reconstructed']
            ax.quiver(0, 0, 0, rec_dir[0], rec_dir[1], rec_dir[2],
                     color=colors[idx], arrow_length_ratio=0.1, linewidth=2,
                     alpha=0.7, label=f'{name}: {data["angular_error"]:.2f}°')
        
        ax.set_xlabel('X', fontweight='bold')
        ax.set_ylabel('Y', fontweight='bold')
        ax.set_zlabel('Z', fontweight='bold')
        ax.legend(loc='upper right')
        ax.set_xlim([-1, 1])
        ax.set_ylim([-1, 1])
        ax.set_zlim([-1, 1])
        
        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        # Page 4: Text summary
        fig = plt.figure(figsize=(11, 8.5))
        ax = fig.add_subplot(111)
        ax.axis('off')
        
        s1_data = scenarios['Scenario 1\nBest Case']
        s2_data = scenarios['Scenario 2\nPerfect CT']
        s3_data = scenarios['Scenario 3\nFull Pipeline']
        
        summary_text = f"""
CAT000001 SUPERNOVA POINTING ANALYSIS
Three-Scenario Performance Comparison

TRUE NEUTRINO DIRECTION: [{true_dir[0]:.4f}, {true_dir[1]:.4f}, {true_dir[2]:.4f}]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SCENARIO 1: BEST CASE (True Electron Directions)
├─ Clusters Used: {s1_data['n_clusters']} ES main tracks
├─ Angular Error: {s1_data['angular_error']:.2f}°
├─ Reconstructed Direction: [{s1_data['reconstructed'][0]:.4f}, {s1_data['reconstructed'][1]:.4f}, {s1_data['reconstructed'][2]:.4f}]
└─ Log-Likelihood: {s1_data['log_likelihood']:.2f}

Description: Uses true particle momentum directions for ES main tracks only.
             Represents the physics limit of the analysis method.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SCENARIO 2: PERFECT CT (ED Network on ES Main Tracks)
├─ Clusters Used: {s2_data['n_clusters']} ES main tracks  
├─ Angular Error: {s2_data['angular_error']:.2f}°
├─ Reconstructed Direction: [{s2_data['reconstructed'][0]:.4f}, {s2_data['reconstructed'][1]:.4f}, {s2_data['reconstructed'][2]:.4f}]
└─ Log-Likelihood: {s2_data['log_likelihood']:.2f}

Description: Uses ED neural network to predict electron directions for ES main tracks.
             Assumes perfect channel tagging (CT) - no CC contamination.
             
Performance vs Scenario 1: {s2_data['angular_error'] - s1_data['angular_error']:+.2f}° ({s2_data['angular_error']/s1_data['angular_error']:.2f}x)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SCENARIO 3: FULL PIPELINE (CT → ED → MCMC)
├─ Clusters Used: {s3_data['n_clusters']} CT-selected clusters
├─ Angular Error: {s3_data['angular_error']:.2f}°
├─ Reconstructed Direction: [{s3_data['reconstructed'][0]:.4f}, {s3_data['reconstructed'][1]:.4f}, {s3_data['reconstructed'][2]:.4f}]
└─ Log-Likelihood: {s3_data['log_likelihood']:.2f}

Description: Complete realistic pipeline with CT model filtering followed by ED inference.
             Includes potential CC contamination from imperfect channel tagging.
             
Performance vs Scenario 1: {s3_data['angular_error'] - s1_data['angular_error']:+.2f}° ({s3_data['angular_error']/s1_data['angular_error']:.2f}x)
Performance vs Scenario 2: {s3_data['angular_error'] - s2_data['angular_error']:+.2f}° ({s3_data['angular_error']/s2_data['angular_error']:.2f}x)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

KEY FINDINGS:

1. ED Network Performance: Scenario 2 achieves {s2_data['angular_error']:.2f}° with only {s2_data['n_clusters']} 
   ES clusters, slightly better than Scenario 1's {s1_data['angular_error']:.2f}° with {s1_data['n_clusters']} clusters.
   This suggests the ED network learns optimal direction features.

2. CT Impact: Full pipeline (Scenario 3) uses {s3_data['n_clusters']/s1_data['n_clusters']*100:.1f}% of available clusters
   after CT filtering, but includes some CC contamination leading to 
   {s3_data['angular_error'] - s2_data['angular_error']:.2f}° degradation vs perfect CT.

3. Overall Performance: Full pipeline achieves {s3_data['angular_error']:.2f}° angular resolution,
   only {s3_data['angular_error'] - s1_data['angular_error']:.2f}° worse than the physics limit.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Analysis Date: November 19, 2025
Category: cat000001
MCMC Configuration: 50 trials × 1000 steps, proposal_scale=0.1
        """
        
        ax.text(0.05, 0.95, summary_text, transform=ax.transAxes,
               fontfamily='monospace', fontsize=8, verticalalignment='top')
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
    
    print(f"\nPDF report saved to: {pdf_path}")

if __name__ == '__main__':
    main()
