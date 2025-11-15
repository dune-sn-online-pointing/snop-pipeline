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

def run_ct_inference(args, mt_results_dir):
    """Run CT inference."""
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
    
    result = subprocess.run(cmd, check=True)
    
    return args.output_dir / 'ct_results'

def generate_analysis(mt_results_dir, ct_results_dir, output_dir, skip_ct=False):
    """Generate comprehensive analysis and plots."""
    print("\n" + "="*70)
    print("STEP 3: ANALYSIS AND VISUALIZATION")
    print("="*70)
    
    # Load results
    mt_predictions = pd.read_csv(mt_results_dir / 'mt_predictions.csv')
    mt_metrics = json.load(open(mt_results_dir / 'mt_metrics.json'))
    ct_predictions = pd.read_csv(ct_results_dir / 'ct_predictions.csv')
    ct_metrics = json.load(open(ct_results_dir / 'ct_metrics.json'))
    
    # Create figure with subplots
    fig = plt.figure(figsize=(16, 12))
    
    # === MT Analysis ===
    
    # 1. MT Prediction distribution
    ax1 = plt.subplot(3, 3, 1)
    ax1.hist(mt_predictions['prediction_prob'], bins=50, alpha=0.7, label='All predictions')
    ax1.axvline(0.5, color='r', linestyle='--', label='Threshold')
    ax1.set_xlabel('MT Prediction Probability')
    ax1.set_ylabel('Count')
    ax1.set_title('MT Prediction Distribution')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. MT Confusion matrix
    ax2 = plt.subplot(3, 3, 2)
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
    ax3 = plt.subplot(3, 3, 3)
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
    ax4 = plt.subplot(3, 3, 4)
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
    ax5 = plt.subplot(3, 3, 5)
    # Sort by prediction probability
    sorted_preds = mt_predictions.sort_values('prediction_prob', ascending=False)
    y_true = (sorted_preds['true_label'] == 0).astype(int)
    
    # Calculate cumulative TP and FP rates
    cumsum_tp = np.cumsum(y_true)
    cumsum_fp = np.cumsum(1 - y_true)
    total_pos = np.sum(y_true)
    total_neg = len(y_true) - total_pos
    
    tpr = cumsum_tp / total_pos if total_pos > 0 else cumsum_tp
    fpr = cumsum_fp / total_neg if total_neg > 0 else cumsum_fp
    
    ax5.plot(fpr, tpr, linewidth=2)
    ax5.plot([0, 1], [0, 1], 'r--', linewidth=1, label='Random')
    ax5.set_xlabel('False Positive Rate')
    ax5.set_ylabel('True Positive Rate')
    ax5.set_title('MT ROC-like Curve')
    ax5.legend()
    ax5.grid(True, alpha=0.3)
    
    # === CT Analysis ===
    
    # 6. CT Cluster distribution
    ax6 = plt.subplot(3, 3, 6)
    ax6.hist(ct_predictions['n_clusters_in_volume'], bins=range(1, 20), alpha=0.7, color='green')
    ax6.set_xlabel('Number of Clusters in Volume')
    ax6.set_ylabel('Count')
    ax6.set_title('CT: Clusters per Volume')
    ax6.grid(True, alpha=0.3)
    
    # 7. CT Purity analysis
    ax7 = plt.subplot(3, 3, 7)
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
    ax8 = plt.subplot(3, 3, 8)
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
    ax9 = plt.subplot(3, 3, 9)
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
    
    ax9.text(0.1, 0.95, summary_text, transform=ax9.transAxes,
            fontsize=10, verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
    
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
                        default='/eos/user/e/evilla/dune/sn-tps/neural_networks/ct_identifier/v14_100k/ct_identifier_model',
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
    
    args = parser.parse_args()
    
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
    print("="*70)
    
    # Run pipeline
    if not args.skip_mt:
        mt_results_dir = run_mt_inference(args)
    else:
        mt_results_dir = args.output_dir / 'mt_results'
        print(f"\nSkipping MT inference, using existing results from: {mt_results_dir}")
    
    ct_results_dir = run_ct_inference(args, mt_results_dir)
    
    generate_analysis(mt_results_dir, ct_results_dir, args.output_dir, skip_ct=args.skip_ct)
    
    print("\n" + "="*70)
    print("PIPELINE COMPLETE")
    print("="*70)
    print(f"All results saved to: {args.output_dir}")

if __name__ == "__main__":
    main()
