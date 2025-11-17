#!/usr/bin/env python3
"""
Run full data selection pipeline on cat000001:
1. MT inference on cluster images
2. CT inference on volume images (with MT-identified clusters)
3. Generate comprehensive analysis and plots
"""

import argparse
import subprocess
import json
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


def angle_between(vec_a, vec_b):
    """Calculate angle in radians between vectors, handling zeros gracefully."""
    vec_a = np.asarray(vec_a, dtype=float)
    vec_b = np.asarray(vec_b, dtype=float)
    dot = np.sum(vec_a * vec_b, axis=-1)
    norm = np.linalg.norm(vec_a, axis=-1) * np.linalg.norm(vec_b, axis=-1)
    norm = np.where(norm == 0, 1.0, norm)
    cos_theta = np.clip(dot / norm, -1.0, 1.0)
    return np.arccos(cos_theta)


def run_mt_inference(args):
    """Run MT inference."""
    print("\n" + "="*70)
    print("STEP 1: MT INFERENCE")
    print("="*70)
    
    cmd = [
        'python3', 'scripts/run_mt_inference.py',
        '--model-path', args.mt_model,
        '--data-dir', args.data_dir,
        '--output-dir', args.output_dir / 'mt_results',
        '--plane', args.plane,
        '--threshold', str(args.mt_threshold),
        '--batch-size', str(args.batch_size),
    ]
    
    if args.max_files:
        cmd.extend(['--max-files', str(args.max_files)])
    
    result = subprocess.run(cmd, check=True)
    
    return args.output_dir / 'mt_results'

def run_ct_inference(args, mt_results_dir, ed_artifacts=None):
    """Run CT inference and optionally save ED artifacts."""
    print("\n" + "="*70)
    print("STEP 2: CT INFERENCE")
    print("="*70)
    
    mt_mapping = mt_results_dir / 'mt_cluster_id_mapping.json'
    
    cmd = [
        'python3', 'scripts/run_ct_inference.py',
        '--data-dir', args.data_dir,
        '--mt-mapping', str(mt_mapping),
        '--output-dir', args.output_dir / 'ct_results',
        '--plane', args.plane,
        '--batch-size', str(args.batch_size),
    ]
    
    if args.skip_ct:
        cmd.append('--skip-ct')
    else:
        cmd.extend(['--model-path', args.ct_model])
    
    if ed_artifacts:
        volumes_npz, mt_npz = ed_artifacts
        cmd.extend([
            '--ed-volumes-npz', str(volumes_npz),
            '--ed-mt-results-npz', str(mt_npz),
        ])
    
    result = subprocess.run(cmd, check=True)
    
    return args.output_dir / 'ct_results'


def run_ed_inference(args, volumes_npz, mt_results_npz, ed_dir):
    """Run ED inference and return output path."""
    print("\n" + "="*70)
    print("STEP 3: ED INFERENCE")
    print("="*70)
    
    ed_out = ed_dir / 'ed_inference_on_mt.npz'
    cmd = [
        'python3', 'python/ed_inference_from_mt.py',
        args.ed_model,
        str(volumes_npz),
        str(mt_results_npz),
        '--out', str(ed_out),
        '--batch-size', str(args.ed_batch_size),
    ]
    subprocess.run(cmd, check=True)
    return ed_out


def run_ed_mcmc(args, ed_npz_path, ed_dir):
    """Run MCMC refinement for ED outputs."""
    print("\n" + "="*70)
    print("STEP 4: MCMC REFINEMENT")
    print("="*70)
    
    mcmc_out = ed_dir / 'ed_mcmc_results.npz'
    cmd = [
        'python3', 'python/ed_mcmc.py',
        str(ed_npz_path),
        '--out', str(mcmc_out),
        '--nsteps', str(args.mcmc_steps),
        '--proposal-scale', str(args.mcmc_proposal_scale),
    ]
    subprocess.run(cmd, check=True)
    return mcmc_out


def compute_ed_metrics(ed_outputs):
    """Load ED + MCMC outputs and derive summary metrics."""
    if not ed_outputs:
        return None
    
    ed_npz_path = Path(ed_outputs['ed_npz'])
    mcmc_npz_path = Path(ed_outputs['mcmc_npz'])
    if not ed_npz_path.exists() or not mcmc_npz_path.exists():
        return None
    
    with np.load(ed_npz_path) as ed_data:
        ed_raw = ed_data['ed_raw']
        energies = ed_data['energy'] if 'energy' in ed_data.files else None
        tentative_dirs = ed_data['tentative_dirs'] if 'tentative_dirs' in ed_data.files else None
        true_dirs = ed_data['true_direction'] if 'true_direction' in ed_data.files else None
    
    with np.load(mcmc_npz_path) as mcmc_data:
        mean_dirs = mcmc_data['mean_direction']
        best_dirs = mcmc_data['best_direction']
        chain_likes = np.asarray(mcmc_data['chain_likes'], dtype=float)
    
    if chain_likes.ndim == 1:
        chain_likes = chain_likes[np.newaxis, :]
    
    final_likes = chain_likes[:, -1]
    metrics = {
        'ed_npz_path': ed_npz_path,
        'mcmc_npz_path': mcmc_npz_path,
        'n_clusters': int(ed_raw.shape[0]),
        'n_angle_bins': int(ed_raw.shape[1]) if ed_raw.ndim > 1 else 1,
        'mcmc_steps': int(chain_likes.shape[1]),
        'energies': energies,
        'final_likes': final_likes,
    }
    
    if tentative_dirs is not None:
        tent_dirs = tentative_dirs.astype(float)
        tent_vs_best = angle_between(tent_dirs, best_dirs.astype(float))
        tent_vs_mean = angle_between(tent_dirs, mean_dirs.astype(float))
        metrics['tent_vs_best_deg'] = np.degrees(tent_vs_best)
        metrics['tent_vs_mean_deg'] = np.degrees(tent_vs_mean)
        metrics['angle_median_deg'] = float(np.median(metrics['tent_vs_best_deg']))
        metrics['angle_p90_deg'] = float(np.percentile(metrics['tent_vs_best_deg'], 90))
        metrics['angle_mean_deg'] = float(np.mean(metrics['tent_vs_best_deg']))
    else:
        metrics['tent_vs_best_deg'] = None
        metrics['tent_vs_mean_deg'] = None
        metrics['angle_median_deg'] = None
        metrics['angle_p90_deg'] = None
        metrics['angle_mean_deg'] = None
    
    # Compute precision wrt true neutrino direction
    if true_dirs is not None:
        true_dirs_f = true_dirs.astype(float)
        true_vs_best = angle_between(true_dirs_f, best_dirs.astype(float))
        true_vs_mean = angle_between(true_dirs_f, mean_dirs.astype(float))
        metrics['true_vs_best_deg'] = np.degrees(true_vs_best)
        metrics['true_vs_mean_deg'] = np.degrees(true_vs_mean)
        metrics['precision_median_deg'] = float(np.median(metrics['true_vs_best_deg']))
        metrics['precision_p90_deg'] = float(np.percentile(metrics['true_vs_best_deg'], 90))
        metrics['precision_mean_deg'] = float(np.mean(metrics['true_vs_best_deg']))
        metrics['precision_p68_deg'] = float(np.percentile(metrics['true_vs_best_deg'], 68))
    else:
        metrics['true_vs_best_deg'] = None
        metrics['true_vs_mean_deg'] = None
        metrics['precision_median_deg'] = None
        metrics['precision_p90_deg'] = None
        metrics['precision_mean_deg'] = None
        metrics['precision_p68_deg'] = None
    
    if energies is not None:
        energy_vals = np.asarray(energies)
        valid = np.isfinite(energy_vals)
        if np.any(valid):
            metrics['energy_mean'] = float(np.mean(energy_vals[valid]))
            metrics['energy_median'] = float(np.median(energy_vals[valid]))
        else:
            metrics['energy_mean'] = None
            metrics['energy_median'] = None
    else:
        metrics['energy_mean'] = None
        metrics['energy_median'] = None
    
    metrics['final_like_mean'] = float(np.mean(final_likes))
    metrics['final_like_median'] = float(np.median(final_likes))
    return metrics


def generate_analysis(mt_results_dir, ct_results_dir, output_dir, skip_ct=False, ed_metrics=None):
    """Generate comprehensive analysis and plots."""
    print("\n" + "="*70)
    print("STEP 3: ANALYSIS AND VISUALIZATION")
    print("="*70)
    
    # Load results
    mt_predictions = pd.read_csv(mt_results_dir / 'mt_predictions.csv')
    mt_metrics = json.load(open(mt_results_dir / 'mt_metrics.json'))
    ct_predictions = pd.read_csv(ct_results_dir / 'ct_predictions.csv')
    ct_metrics = json.load(open(ct_results_dir / 'ct_metrics.json'))
    
    # Create figure with subplots (add 4th row if ED enabled)
    grid_rows = 4 if ed_metrics else 3
    fig = plt.figure(figsize=(16, 4 * grid_rows))
    
    # === MT Analysis ===
    
    # 1. MT Prediction distribution
    ax1 = plt.subplot(grid_rows, 3, 1)
    ax1.hist(mt_predictions['prediction_prob'], bins=50, alpha=0.7, label='All predictions')
    ax1.axvline(0.5, color='r', linestyle='--', label='Threshold')
    ax1.set_xlabel('MT Prediction Probability')
    ax1.set_ylabel('Count')
    ax1.set_title('MT Prediction Distribution')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. MT Confusion matrix
    ax2 = plt.subplot(grid_rows, 3, 2)
    cm = np.array([
        [mt_metrics['true_positives'], mt_metrics['false_negatives']],
        [mt_metrics['false_positives'], mt_metrics['true_negatives']]
    ])
    im = ax2.imshow(cm, cmap='Blues', aspect='auto')
    ax2.set_xticks([0, 1])
    ax2.set_yticks([0, 1])
    ax2.set_xticklabels(['Pred MT', 'Pred Non-MT'])
    ax2.set_yticklabels(['True MT', 'True Non-MT'])
    ax2.set_title('MT Confusion Matrix')
    
    # Add text annotations
    for i in range(2):
        for j in range(2):
            text = ax2.text(j, i, cm[i, j],
                           ha="center", va="center", color="black", fontsize=14)
    plt.colorbar(im, ax=ax2)
    
    # 3. MT Metrics bar plot
    ax3 = plt.subplot(grid_rows, 3, 3)
    metrics_names = ['Accuracy', 'Precision', 'Recall', 'F1 Score']
    metrics_values = [
        mt_metrics['accuracy'],
        mt_metrics['precision'],
        mt_metrics['recall'],
        mt_metrics['f1_score']
    ]
    bars = ax3.bar(metrics_names, metrics_values, color=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728'])
    ax3.set_ylim([0, 1])
    ax3.set_ylabel('Score')
    ax3.set_title('MT Performance Metrics')
    ax3.grid(True, alpha=0.3, axis='y')
    
    # Add value labels on bars
    for bar, value in zip(bars, metrics_values):
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., height,
                f'{value:.3f}', ha='center', va='bottom', fontsize=10)
    
    # 4. MT Energy distribution
    ax4 = plt.subplot(grid_rows, 3, 4)
    true_mt = mt_predictions[mt_predictions['true_label'] == 0]
    pred_mt = mt_predictions[mt_predictions['predicted_label'] == 1]
    ax4.hist(true_mt['cluster_energy'], bins=30, alpha=0.5, label='True MT', color='blue')
    ax4.hist(pred_mt['cluster_energy'], bins=30, alpha=0.5, label='Predicted MT', color='orange')
    ax4.set_xlabel('Cluster Energy (MeV)')
    ax4.set_ylabel('Count')
    ax4.set_title('Cluster Energy Distribution')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    # 5. MT ROC-style plot (TP rate vs FP rate)
    ax5 = plt.subplot(grid_rows, 3, 5)
    # Sort by prediction probability
    sorted_preds = mt_predictions.sort_values('prediction_prob', ascending=False)
    y_true = (sorted_preds['true_label'] == 0).astype(int).to_numpy()
    
    # Calculate cumulative TP and FP rates
    cumsum_tp = np.cumsum(y_true)
    cumsum_fp = np.cumsum(1 - y_true)
    total_pos = np.sum(y_true)
    total_neg = len(y_true) - total_pos
    
    tpr = cumsum_tp / total_pos if total_pos > 0 else np.zeros_like(cumsum_tp, dtype=float)
    fpr = cumsum_fp / total_neg if total_neg > 0 else np.zeros_like(cumsum_fp, dtype=float)
    
    ax5.plot(fpr, tpr, linewidth=2)
    ax5.plot([0, 1], [0, 1], 'r--', linewidth=1, label='Random')
    ax5.set_xlabel('False Positive Rate')
    ax5.set_ylabel('True Positive Rate')
    ax5.set_title('MT ROC-like Curve')
    ax5.legend()
    ax5.grid(True, alpha=0.3)
    
    # === CT Analysis ===
    
    # 6. CT Cluster distribution
    ax6 = plt.subplot(grid_rows, 3, 6)
    ax6.hist(ct_predictions['n_clusters_in_volume'], bins=range(1, 20), alpha=0.7, color='green')
    ax6.set_xlabel('Number of Clusters in Volume')
    ax6.set_ylabel('Count')
    ax6.set_title('CT: Clusters per Volume')
    ax6.grid(True, alpha=0.3)
    
    # 7. CT Purity analysis
    ax7 = plt.subplot(grid_rows, 3, 7)
    purity = ct_predictions['n_marley_clusters'] / ct_predictions['n_clusters_in_volume']
    ax7.hist(purity, bins=20, alpha=0.7, color='purple')
    ax7.axvline(ct_metrics['purity'], color='r', linestyle='--', 
                label=f"Mean: {ct_metrics['purity']:.3f}")
    ax7.set_xlabel('Purity (Marley Clusters / Total)')
    ax7.set_ylabel('Count')
    ax7.set_title('CT: Volume Purity Distribution')
    ax7.legend()
    ax7.grid(True, alpha=0.3)
    
    # 8. CT Marley vs Non-Marley
    ax8 = plt.subplot(grid_rows, 3, 8)
    labels = ['Marley\nClusters', 'Non-Marley\nClusters']
    values = [ct_metrics['total_marley_clusters'], ct_metrics['total_non_marley_clusters']]
    colors = ['#2ca02c', '#d62728']
    wedges, texts, autotexts = ax8.pie(values, labels=labels, colors=colors, autopct='%1.1f%%',
                                         startangle=90)
    ax8.set_title('CT: Cluster Composition')
    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontsize(12)
        autotext.set_fontweight('bold')
    
    # 9. Summary text
    ax9 = plt.subplot(grid_rows, 3, 9)
    ax9.axis('off')
    
    summary_text = f"""
    PIPELINE SUMMARY
    {'='*40}
    
    MT IDENTIFICATION:
      Total clusters:        {mt_metrics['n_total']}
      True MT:               {mt_metrics['n_true_main_tracks']}
      Predicted MT:          {mt_metrics['n_predicted_main_tracks']}
      
      Accuracy:              {mt_metrics['accuracy']:.4f}
      Precision:             {mt_metrics['precision']:.4f}
      Recall (Efficiency):   {mt_metrics['recall']:.4f}
      Contamination:         {mt_metrics['contamination']:.4f}
    
    CT VOLUME SELECTION:
      Volumes processed:     {ct_metrics['n_volumes']}
      Total clusters:        {ct_metrics['total_clusters']}
      
      Marley clusters:       {ct_metrics['total_marley_clusters']}
      Non-Marley clusters:   {ct_metrics['total_non_marley_clusters']}
      
      Purity:                {ct_metrics['purity']:.4f}
      Contamination rate:    {ct_metrics['contamination_rate']:.4f}
    """
    
    if skip_ct:
        summary_text += "\n    *** SKIP_CT MODE ***\n    (Perfect tagging assumed)"
    
    if ed_metrics:
        median_angle = ed_metrics.get('angle_median_deg')
        p90_angle = ed_metrics.get('angle_p90_deg')
        energy_mean = ed_metrics.get('energy_mean')
        prec_median = ed_metrics.get('precision_median_deg')
        prec_p68 = ed_metrics.get('precision_p68_deg')
        prec_p90 = ed_metrics.get('precision_p90_deg')
        if median_angle is not None and energy_mean is not None:
            ed_text = f"""

    ED + MCMC DIRECTION:
      Clusters processed:   {ed_metrics['n_clusters']}
      Angle bins:           {ed_metrics['n_angle_bins']}
      Mean cluster energy:  {energy_mean:.2f} MeV
      Final like (mean):    {ed_metrics['final_like_mean']:.3e}"""
            if prec_median is not None:
                ed_text += f"""
      
      PRECISION vs TRUE ν DIRECTION:
      Median error:         {prec_median:.2f}°
      68% within:           {prec_p68:.2f}°
      90% within:           {prec_p90:.2f}°"""
            summary_text += ed_text
    
    ax9.text(0.1, 0.95, summary_text, transform=ax9.transAxes,
            fontsize=10, verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
    
    # === ED Analysis (if enabled) ===
    if ed_metrics:
        # 10. ED Energy distribution
        ax10 = plt.subplot(grid_rows, 3, 10)
        energies = ed_metrics.get('energies')
        if energies is not None and len(energies) > 0:
            energy_vals = np.asarray(energies)
            valid = np.isfinite(energy_vals)
            if np.any(valid):
                ax10.hist(energy_vals[valid], bins=40, color='teal', alpha=0.7)
                ax10.set_xlabel('Cluster Energy (MeV)')
                ax10.set_ylabel('Count')
            else:
                ax10.text(0.5, 0.5, 'No finite energies', ha='center', va='center')
        else:
            ax10.text(0.5, 0.5, 'Energy not provided', ha='center', va='center')
        ax10.set_title('ED Energy Distribution')
        ax10.grid(True, alpha=0.3)
        
        # 11. Precision: Reconstructed vs True direction
        ax11 = plt.subplot(grid_rows, 3, 11)
        true_angles = ed_metrics.get('true_vs_best_deg')
        if true_angles is not None:
            ax11.hist(true_angles, bins=30, color='crimson', alpha=0.7)
            prec_median = ed_metrics.get('precision_median_deg')
            prec_p68 = ed_metrics.get('precision_p68_deg')
            if prec_median is not None:
                ax11.axvline(prec_median, color='k', linestyle='--', label=f'Median: {prec_median:.1f}°')
                ax11.axvline(prec_p68, color='b', linestyle=':', label=f'68%: {prec_p68:.1f}°')
                ax11.legend()
            ax11.set_xlabel('Angular Error (deg)')
            ax11.set_ylabel('Count')
        else:
            ax11.text(0.5, 0.5, 'True direction unavailable', ha='center', va='center')
        ax11.set_title('Precision: Reconstructed vs True ν Direction')
        ax11.grid(True, alpha=0.3)
        
        # 12. Energy vs angle or likelihood histogram
        ax12 = plt.subplot(grid_rows, 3, 12)
        if angles is not None and energies is not None and len(energies) == len(angles):
            energy_vals = np.asarray(energies)
            valid = np.isfinite(energy_vals)
            ax12.scatter(energy_vals[valid], np.asarray(angles)[valid], s=10, alpha=0.5)
            ax12.set_xlabel('Energy (MeV)')
            ax12.set_ylabel('Angle Shift (deg)')
            ax12.set_title('Energy vs Angle Shift')
        else:
            final_likes = np.asarray(ed_metrics.get('final_likes', []))
            if final_likes.size:
                ax12.hist(final_likes, bins=30, color='slateblue', alpha=0.7)
                ax12.set_xlabel('Final Likelihood')
                ax12.set_ylabel('Count')
                ax12.set_title('MCMC Final Likelihoods')
            else:
                ax12.text(0.5, 0.5, 'No ED data', ha='center', va='center')
        ax12.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # Save figure
    output_file = output_dir / 'pipeline_analysis.pdf'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"Saved analysis plot to: {output_file}")
    
    # Generate text report
    report_file = output_dir / 'pipeline_report.txt'
    with open(report_file, 'w') as f:
        f.write("="*70 + "\n")
        f.write("DATA SELECTION PIPELINE REPORT - CAT000001\n")
        f.write("="*70 + "\n\n")
        
        f.write("STEP 1: MT (MAIN TRACK) IDENTIFICATION\n")
        f.write("-"*70 + "\n")
        f.write(f"Total clusters processed:        {mt_metrics['n_total']}\n")
        f.write(f"True main tracks:                {mt_metrics['n_true_main_tracks']}\n")
        f.write(f"Predicted main tracks:           {mt_metrics['n_predicted_main_tracks']}\n\n")
        
        f.write("Confusion Matrix:\n")
        f.write(f"  True Positives (TP):           {mt_metrics['true_positives']}\n")
        f.write(f"  True Negatives (TN):           {mt_metrics['true_negatives']}\n")
        f.write(f"  False Positives (FP):          {mt_metrics['false_positives']}\n")
        f.write(f"  False Negatives (FN):          {mt_metrics['false_negatives']}\n\n")
        
        f.write("Performance Metrics:\n")
        f.write(f"  Accuracy:                      {mt_metrics['accuracy']:.4f}\n")
        f.write(f"  Precision:                     {mt_metrics['precision']:.4f}\n")
        f.write(f"  Recall (Efficiency):           {mt_metrics['recall']:.4f}\n")
        f.write(f"  F1 Score:                      {mt_metrics['f1_score']:.4f}\n")
        f.write(f"  Contamination (FP rate):       {mt_metrics['contamination']:.4f}\n\n")
        
        f.write("\nSTEP 2: CT (CLUSTER TYPE) VOLUME SELECTION\n")
        f.write("-"*70 + "\n")
        f.write(f"Volumes processed:               {ct_metrics['n_volumes']}\n")
        f.write(f"Total clusters in volumes:       {ct_metrics['total_clusters']}\n")
        f.write(f"Marley clusters:                 {ct_metrics['total_marley_clusters']}\n")
        f.write(f"Non-Marley clusters:             {ct_metrics['total_non_marley_clusters']}\n\n")
        
        f.write("Per-Volume Statistics:\n")
        f.write(f"  Avg clusters per volume:       {ct_metrics['avg_clusters_per_volume']:.2f}\n")
        f.write(f"  Avg Marley per volume:         {ct_metrics['avg_marley_per_volume']:.2f}\n")
        f.write(f"  Avg non-Marley per volume:     {ct_metrics['avg_non_marley_per_volume']:.2f}\n\n")
        
        f.write("Purity Metrics:\n")
        f.write(f"  Purity (Marley %):             {ct_metrics['purity']:.4f}\n")
        f.write(f"  Contamination rate:            {ct_metrics['contamination_rate']:.4f}\n\n")
        
        if skip_ct:
            f.write("\n*** SKIP_CT MODE ACTIVE ***\n")
            f.write("CT inference was skipped - perfect tagging assumed\n")
        
        if ed_metrics:
            f.write("\nSTEP 3: ED + MCMC DIRECTION REFINEMENT\n")
            f.write("-"*70 + "\n")
            f.write(f"Clusters processed:            {ed_metrics['n_clusters']}\n")
            f.write(f"Angle bins:                    {ed_metrics['n_angle_bins']}\n")
            if ed_metrics.get('energy_mean') is not None:
                f.write(f"Mean cluster energy:           {ed_metrics['energy_mean']:.2f} MeV\n")
                f.write(f"Median cluster energy:         {ed_metrics['energy_median']:.2f} MeV\n")
            f.write(f"Final likelihood (mean):        {ed_metrics['final_like_mean']:.3e}\n")
            f.write(f"Final likelihood (median):      {ed_metrics['final_like_median']:.3e}\n")
            if ed_metrics.get('precision_median_deg') is not None:
                f.write(f"\nPRECISION vs TRUE NEUTRINO DIRECTION:\n")
                f.write(f"  Median angular error:        {ed_metrics['precision_median_deg']:.2f}°\n")
                f.write(f"  Mean angular error:          {ed_metrics['precision_mean_deg']:.2f}°\n")
                f.write(f"  68% of events within:        {ed_metrics['precision_p68_deg']:.2f}°\n")
                f.write(f"  90% of events within:        {ed_metrics['precision_p90_deg']:.2f}°\n")
            f.write("\n")
        
        f.write("\n" + "="*70 + "\n")
        f.write("END OF REPORT\n")
        f.write("="*70 + "\n")
    
    print(f"Saved text report to: {report_file}")

def main():
    parser = argparse.ArgumentParser(
        description='Run full data selection pipeline on cat000001',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  # Run full pipeline with default models
  python3 scripts/run_pipeline.py
  
  # Test on limited data
  python3 scripts/run_pipeline.py --max-files 5
  
  # Skip CT inference (assume perfect tagging)
  python3 scripts/run_pipeline.py --skip-ct
        """
    )
    
    parser.add_argument('--mt-model', type=str,
                        default='/eos/user/e/evilla/dune/sn-tps/neural_networks/mt_identifier/v10_100k_nov13/mt_identifier_simple_cnn_20251113_145400',
                        help='Path to MT model')
    parser.add_argument('--ct-model', type=str,
                        default='/eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/v40_corrected_10k/20251114_225600/best_model.keras',
                        help='Path to CT model (ignored if --skip-ct)')
    parser.add_argument('--data-dir', type=str,
                        default='/eos/project-e/ep-nu/public/sn-pointing/cat000001',
                        help='Base directory containing cat000001 data')
    parser.add_argument('--output-dir', type=str,
                        default='results/pipeline_cat000001',
                        help='Directory to save all results')
    parser.add_argument('--plane', type=str, default='X',
                        choices=['U', 'V', 'X'],
                        help='Which plane to process')
    parser.add_argument('--mt-threshold', type=float, default=0.5,
                        help='MT classification threshold')
    parser.add_argument('--batch-size', type=int, default=128,
                        help='Batch size for inference')
    parser.add_argument('--max-files', type=int, default=None,
                        help='Maximum number of files to process (for testing)')
    parser.add_argument('--skip-ct', action='store_true',
                        help='Skip CT inference, assume perfect tagging')
    parser.add_argument('--skip-mt', action='store_true',
                        help='Skip MT inference (use existing results)')
    parser.add_argument('--enable-ed', action='store_true',
                        help='Run ED inference and MCMC refinement')
    parser.add_argument('--ed-model', type=str,
                        default='/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v18_200k_aug_20251112_114654/checkpoints/model_epoch_26_val_loss_0.8232.keras',
                        help='Path to ED model (used when --enable-ed)')
    parser.add_argument('--ed-batch-size', type=int, default=32,
                        help='Batch size for ED inference')
    parser.add_argument('--mcmc-steps', type=int, default=2000,
                        help='Number of MCMC steps per cluster')
    parser.add_argument('--mcmc-proposal-scale', type=float, default=0.08,
                        help='Gaussian proposal std-dev for MCMC sampler')
    parser.add_argument('--cat', type=str, default=None,
                        help='Quick test mode: specify category name (e.g., cat000010) to use standard paths')
    parser.add_argument('--use-condor', action='store_true',
                        help='Submit pipeline steps to condor GPU queue instead of running locally')
    parser.add_argument('--condor-flavour', type=str, default='microcentury',
                        choices=['espresso', 'microcentury', 'longlunch', 'workday', 'tomorrow', 'testmatch', 'nextweek'],
                        help='Condor job duration: espresso(20min), microcentury(1h), longlunch(2h), workday(8h)')
    parser.add_argument('--condor-memory', type=str, default='8GB',
                        help='Memory request for condor jobs (default: 8GB)')

    
    args = parser.parse_args()
    

    # Handle --cat shortcut for testing
    if args.cat:
        cat_name = args.cat
        # Use the base path - scripts will find cluster/volume subdirs
        args.data_dir = f'/eos/project-e/ep-nu/public/sn-pointing/{cat_name}'
        if args.output_dir == 'results/pipeline':
            args.output_dir = f'results/pipeline_{cat_name}'
        print(f"Quick test mode: Using {cat_name}")
        print(f"  Data: {args.data_dir}")
        print(f"  Output: {args.output_dir}")
    
    # Handle condor submission
    if args.use_condor:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / 'python'))
        from condor_helper import submit_condor_job
        
        # Reconstruct command line args (excluding --use-condor itself)
        cmd_args = []
        for arg in sys.argv[1:]:
            if arg == '--use-condor':
                continue
            cmd_args.append(arg)
        
        job_id = submit_condor_job(
            cat_name=args.cat or 'pipeline',
            step='full',
            pipeline_args_list=cmd_args,
            gpu=not args.skip_ct and not args.skip_mt,  # Need GPU for inference
            memory=args.condor_memory,
            flavour=args.condor_flavour,
        )
        
        print(f"\n{'='*70}")
        print(f"Pipeline submitted to condor as job {job_id}")
        print(f"{'='*70}")
        print(f"\nMonitor with: condor_q {job_id}")
        print(f"Check logs: logs/pipeline_full_*_{job_id}.*")
        print(f"View output: condor_tail {job_id}")
        return

    # Convert paths to Path objects
    args.output_dir = Path(args.output_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    
    print("="*70)
    print("DATA SELECTION PIPELINE - CAT000001")
    print("="*70)
    print(f"Data directory:    {args.data_dir}")
    print(f"Output directory:  {args.output_dir}")
    print(f"Plane:             {args.plane}")
    print(f"MT model:          {args.mt_model}")
    if not args.skip_ct:
        print(f"CT model:          {args.ct_model}")
    else:
        print(f"CT mode:           SKIPPED (perfect tagging assumed)")
    if args.enable_ed:
        print(f"ED model:          {args.ed_model}")
    else:
        print("ED step:           DISABLED")
    print("="*70)
    
    # Run pipeline
    if not args.skip_mt:
        mt_results_dir = run_mt_inference(args)
    else:
        mt_results_dir = args.output_dir / 'mt_results'
        print(f"\nSkipping MT inference, using existing results from: {mt_results_dir}")
    
    # Prepare ED artifacts if enabled
    ed_artifacts = None
    ed_dir = args.output_dir / 'ed_results'
    if args.enable_ed:
        ed_dir.mkdir(parents=True, exist_ok=True)
        ed_artifacts = (
            ed_dir / 'volumes_for_ed.npz',
            ed_dir / 'mt_mask_for_ed.npz',
        )
    
    ct_results_dir = run_ct_inference(args, mt_results_dir, ed_artifacts=ed_artifacts)
    
    # Run ED + MCMC if enabled
    ed_outputs = None
    if args.enable_ed and ed_artifacts:
        volumes_npz, mt_npz = ed_artifacts
        if volumes_npz.exists() and mt_npz.exists():
            ed_npz = run_ed_inference(args, volumes_npz, mt_npz, ed_dir)
            mcmc_npz = run_ed_mcmc(args, ed_npz, ed_dir)
            ed_outputs = {'ed_npz': ed_npz, 'mcmc_npz': mcmc_npz}
        else:
            print("Warning: ED artifacts missing; skipping ED stage")
    
    ed_metrics = compute_ed_metrics(ed_outputs)
    generate_analysis(mt_results_dir, ct_results_dir, args.output_dir, skip_ct=args.skip_ct, ed_metrics=ed_metrics)
    
    print("\n" + "="*70)
    print("PIPELINE COMPLETE")
    print("="*70)
    print(f"All results saved to: {args.output_dir}")

if __name__ == "__main__":
    main()
