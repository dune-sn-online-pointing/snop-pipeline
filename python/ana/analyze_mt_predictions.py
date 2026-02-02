#!/usr/bin/env python3
"""
Analyze MT (Main Track) predictions from inference.
Generates comprehensive PDF report with:
- Energy vs prediction scatter plots
- Contamination vs threshold analysis
- Performance metrics and distributions
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import argparse
from matplotlib.backends.backend_pdf import PdfPages


def load_predictions(predictions_file):
    """Load MT predictions CSV."""
    df = pd.read_csv(predictions_file)
    print(f"Loaded {len(df)} predictions from {predictions_file}")
    return df


def compute_statistics(df):
    """Compute classification statistics."""
    tp = df[(df['is_main_track'] == 1) & (df['predicted_label'] == 1)]
    fp = df[(df['is_main_track'] == 0) & (df['predicted_label'] == 1)]
    fn = df[(df['is_main_track'] == 1) & (df['predicted_label'] == 0)]
    tn = df[(df['is_main_track'] == 0) & (df['predicted_label'] == 0)]
    
    stats = {
        'total': len(df),
        'true_main': (df['is_main_track'] == 1).sum(),
        'pred_main': (df['predicted_label'] == 1).sum(),
        'tp': len(tp),
        'fp': len(fp),
        'fn': len(fn),
        'tn': len(tn),
        'accuracy': (len(tp) + len(tn)) / len(df),
        'precision': len(tp) / (len(tp) + len(fp)) if (len(tp) + len(fp)) > 0 else 0,
        'recall': len(tp) / (len(tp) + len(fn)) if (len(tp) + len(fn)) > 0 else 0,
        'contamination': len(fp) / (len(tp) + len(fp)) if (len(tp) + len(fp)) > 0 else 0,
    }
    
    return stats, tp, fp, fn, tn


def plot_energy_vs_prediction(ax, df, true_mt, false_mt):
    """Plot scatter of energy vs prediction probability."""
    ax.scatter(false_mt['cluster_energy'], false_mt['prediction_prob'], 
               alpha=0.4, s=15, label='Background clusters', color='red', edgecolors='none')
    ax.scatter(true_mt['cluster_energy'], true_mt['prediction_prob'], 
               alpha=0.4, s=15, label='True main tracks', color='blue', edgecolors='none')
    ax.axhline(0.5, color='green', linestyle='--', linewidth=2, label='Threshold (0.5)')
    
    ax.set_xlabel('Cluster Energy (MeV)', fontsize=11)
    ax.set_ylabel('MT Prediction Probability', fontsize=11)
    ax.set_title('Cluster Energy vs Main Track Prediction', fontsize=12, fontweight='bold')
    ax.legend(loc='best', fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 70)


def plot_energy_distributions(ax, tp, fp, fn, tn):
    """Plot energy distributions by classification outcome."""
    bins = np.linspace(0, 50, 40)
    
    ax.hist(fp['cluster_energy'], bins=bins, alpha=0.6, 
            label=f'False Pos: n={len(fp)}', color='red', edgecolor='darkred')
    ax.hist(tp['cluster_energy'], bins=bins, alpha=0.6, 
            label=f'True Pos: n={len(tp)}', color='blue', edgecolor='darkblue')
    if len(fn) > 0:
        ax.hist(fn['cluster_energy'], bins=bins, alpha=0.6, 
                label=f'False Neg: n={len(fn)}', color='orange', edgecolor='darkorange')
    
    ax.set_xlabel('Cluster Energy (MeV)', fontsize=11)
    ax.set_ylabel('Count', fontsize=11)
    ax.set_title('Energy Distribution by Prediction Outcome', fontsize=12, fontweight='bold')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3, axis='y')


def plot_cumulative_energy(ax, tp, fp):
    """Plot cumulative energy distributions."""
    sorted_fp = np.sort(fp['cluster_energy'])
    sorted_tp = np.sort(tp['cluster_energy'])
    cumulative_fp = np.arange(1, len(sorted_fp) + 1) / len(sorted_fp) * 100
    cumulative_tp = np.arange(1, len(sorted_tp) + 1) / len(sorted_tp) * 100
    
    ax.plot(sorted_fp, cumulative_fp, label='False Positives', linewidth=2, color='red')
    ax.plot(sorted_tp, cumulative_tp, label='True Positives', linewidth=2, color='blue')
    
    # Add reference lines
    for energy in [5, 10, 20]:
        ax.axvline(energy, color='gray', linestyle=':', linewidth=1, alpha=0.5)
        ax.text(energy, 5, f'{energy} MeV', rotation=90, fontsize=8, alpha=0.7)
    
    ax.set_xlabel('Cluster Energy (MeV)', fontsize=11)
    ax.set_ylabel('Cumulative Percentage (%)', fontsize=11)
    ax.set_title('Cumulative Energy Distribution', fontsize=12, fontweight='bold')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)


def plot_energy_statistics(ax, tp, fp, fn, tn):
    """Plot bar chart of energy statistics."""
    categories = ['True\nPositives', 'False\nPositives', 'False\nNegatives', 'True\nNegatives']
    means = [tp['cluster_energy'].mean(), fp['cluster_energy'].mean(),
             fn['cluster_energy'].mean() if len(fn) > 0 else 0, tn['cluster_energy'].mean()]
    medians = [tp['cluster_energy'].median(), fp['cluster_energy'].median(),
               fn['cluster_energy'].median() if len(fn) > 0 else 0, tn['cluster_energy'].median()]
    counts = [len(tp), len(fp), len(fn), len(tn)]
    
    x = np.arange(len(categories))
    width = 0.35
    
    bars1 = ax.bar(x - width/2, means, width, label='Mean Energy', 
                   alpha=0.8, color='steelblue', edgecolor='navy')
    bars2 = ax.bar(x + width/2, medians, width, label='Median Energy', 
                   alpha=0.8, color='orange', edgecolor='darkorange')
    
    ax.set_ylabel('Energy (MeV)', fontsize=11)
    ax.set_title('Average Cluster Energy by Category', fontsize=12, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=9)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3, axis='y')
    
    # Add value labels
    for bars in [bars1, bars2]:
        for bar, count in zip(bars, counts):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.5,
                    f'{height:.1f}\n(n={count})', ha='center', va='bottom', fontsize=7)


def plot_prediction_distribution(ax, df):
    """Plot histogram of prediction probabilities."""
    bins = np.linspace(0, 1, 50)
    
    true_mt = df[df['is_main_track'] == 1]
    false_mt = df[df['is_main_track'] == 0]
    
    ax.hist(false_mt['prediction_prob'], bins=bins, alpha=0.6, 
            label='Background', color='red', edgecolor='darkred')
    ax.hist(true_mt['prediction_prob'], bins=bins, alpha=0.6, 
            label='True Main Track', color='blue', edgecolor='darkblue')
    ax.axvline(0.5, color='green', linestyle='--', linewidth=2, label='Threshold')
    
    ax.set_xlabel('Prediction Probability', fontsize=11)
    ax.set_ylabel('Count', fontsize=11)
    ax.set_title('Distribution of MT Predictions', fontsize=12, fontweight='bold')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3, axis='y')


def create_summary_text(ax, stats, tp, fp, fn, tn):
    """Create text summary of results."""
    ax.axis('off')
    
    summary = f"""
MT INFERENCE SUMMARY - CAT000001
{'='*60}

DATASET:
  Total clusters:              {stats['total']:,}
  True main tracks:            {stats['true_main']:,}
  True backgrounds:            {stats['total'] - stats['true_main']:,}

PREDICTIONS:
  Predicted main tracks:       {stats['pred_main']:,}
  Predicted backgrounds:       {stats['total'] - stats['pred_main']:,}

CONFUSION MATRIX:
  True Positives (TP):         {stats['tp']:,}
  False Positives (FP):        {stats['fp']:,}
  False Negatives (FN):        {stats['fn']:,}
  True Negatives (TN):         {stats['tn']:,}

PERFORMANCE METRICS:
  Accuracy:                    {stats['accuracy']:.1%}
  Precision:                   {stats['precision']:.1%}
  Recall (Efficiency):         {stats['recall']:.1%}
  Contamination (FP rate):     {stats['contamination']:.1%}

ENERGY ANALYSIS:
  True Positives:
    Mean:   {tp['cluster_energy'].mean():.2f} MeV
    Median: {tp['cluster_energy'].median():.2f} MeV
    Range:  {tp['cluster_energy'].min():.2f} - {tp['cluster_energy'].max():.2f} MeV
    
  False Positives:
    Mean:   {fp['cluster_energy'].mean():.2f} MeV
    Median: {fp['cluster_energy'].median():.2f} MeV
    Range:  {fp['cluster_energy'].min():.2f} - {fp['cluster_energy'].max():.2f} MeV

LOW ENERGY ANALYSIS (< 5 MeV):
  FP below 5 MeV:  {len(fp[fp['cluster_energy'] < 5]):,} ({len(fp[fp['cluster_energy'] < 5])/len(fp)*100:.1f}% of all FP)
  TP below 5 MeV:  {len(tp[tp['cluster_energy'] < 5]):,} ({len(tp[tp['cluster_energy'] < 5])/len(tp)*100:.1f}% of all TP)
  
INTERPRETATION:
  - Model has very high recall ({stats['recall']:.1%}) - catches almost all main tracks
  - Contamination is {stats['contamination']:.1%} - significant background leakage
  - False positives span wide energy range (not just low energy)
  - ~45% of FP are low energy (<5 MeV), but 55% are higher energy
"""
    
    ax.text(0.05, 0.95, summary, transform=ax.transAxes,
            fontsize=9, verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.2))


def compute_metrics_at_threshold(df, threshold):
    """Compute metrics at a specific threshold."""
    pred_labels = (df['prediction_prob'] >= threshold).astype(int)
    
    tp = ((df['is_main_track'] == 1) & (pred_labels == 1)).sum()
    fp = ((df['is_main_track'] == 0) & (pred_labels == 1)).sum()
    fn = ((df['is_main_track'] == 1) & (pred_labels == 0)).sum()
    tn = ((df['is_main_track'] == 0) & (pred_labels == 0)).sum()
    
    total_pred = tp + fp
    total_true = tp + fn
    
    metrics = {
        'threshold': threshold,
        'tp': tp,
        'fp': fp,
        'fn': fn,
        'tn': tn,
        'predicted_positives': total_pred,
        'accuracy': (tp + tn) / len(df) if len(df) > 0 else 0,
        'precision': tp / total_pred if total_pred > 0 else 0,
        'recall': tp / total_true if total_true > 0 else 0,
        'contamination': fp / total_pred if total_pred > 0 else 0,
        'f1': 0
    }
    
    if metrics['precision'] + metrics['recall'] > 0:
        metrics['f1'] = 2 * metrics['precision'] * metrics['recall'] / (metrics['precision'] + metrics['recall'])
    
    return metrics


def threshold_scan(df, thresholds):
    """Scan across multiple thresholds."""
    results = []
    for threshold in thresholds:
        metrics = compute_metrics_at_threshold(df, threshold)
        results.append(metrics)
    return pd.DataFrame(results)


def plot_contamination_vs_threshold(ax, scan_df):
    """Plot contamination as function of threshold."""
    ax.plot(scan_df['threshold'].values, scan_df['contamination'].values * 100, 
            linewidth=3, color='red', marker='o', markersize=4, label='Contamination')
    ax.axhline(50, color='gray', linestyle=':', linewidth=1, alpha=0.5)
    ax.axvline(0.5, color='green', linestyle='--', linewidth=2, alpha=0.7, label='Default (0.5)')
    ax.set_xlabel('Prediction Threshold', fontsize=10)
    ax.set_ylabel('Contamination (%)', fontsize=10)
    ax.set_title('Contamination vs Threshold', fontsize=11, fontweight='bold')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 100)


def plot_recall_vs_threshold(ax, scan_df):
    """Plot recall (efficiency) as function of threshold."""
    ax.plot(scan_df['threshold'].values, scan_df['recall'].values * 100, 
            linewidth=3, color='blue', marker='o', markersize=4, label='Recall')
    ax.axhline(90, color='gray', linestyle=':', linewidth=1, alpha=0.5)
    ax.axvline(0.5, color='green', linestyle='--', linewidth=2, alpha=0.7, label='Default (0.5)')
    ax.set_xlabel('Prediction Threshold', fontsize=10)
    ax.set_ylabel('Recall / Efficiency (%)', fontsize=10)
    ax.set_title('Recall vs Threshold', fontsize=11, fontweight='bold')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 100)


def plot_precision_vs_threshold(ax, scan_df):
    """Plot precision as function of threshold."""
    ax.plot(scan_df['threshold'].values, scan_df['precision'].values * 100, 
            linewidth=3, color='purple', marker='o', markersize=4, label='Precision')
    ax.axvline(0.5, color='green', linestyle='--', linewidth=2, alpha=0.7, label='Default (0.5)')
    ax.set_xlabel('Prediction Threshold', fontsize=10)
    ax.set_ylabel('Precision (%)', fontsize=10)
    ax.set_title('Precision vs Threshold', fontsize=11, fontweight='bold')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 100)


def plot_f1_vs_threshold(ax, scan_df):
    """Plot F1 score vs threshold."""
    ax.plot(scan_df['threshold'].values, scan_df['f1'].values, 
            linewidth=3, color='teal', marker='o', markersize=4, label='F1 Score')
    best_idx = scan_df['f1'].idxmax()
    best_thresh = scan_df.loc[best_idx, 'threshold']
    ax.axvline(best_thresh, color='red', linestyle='--', linewidth=2, 
               alpha=0.7, label=f'Best F1 at {best_thresh:.2f}')
    ax.axvline(0.5, color='green', linestyle='--', linewidth=2, alpha=0.7, label='Default (0.5)')
    ax.set_xlabel('Prediction Threshold', fontsize=10)
    ax.set_ylabel('F1 Score', fontsize=10)
    ax.set_title('F1 Score vs Threshold', fontsize=11, fontweight='bold')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)


def generate_report(predictions_file, output_pdf):
    """Generate comprehensive PDF report."""
    print(f"\nGenerating MT prediction analysis report...")
    print(f"Input: {predictions_file}")
    print(f"Output: {output_pdf}")
    
    # Load data
    df = load_predictions(predictions_file)
    
    # Compute statistics
    stats, tp, fp, fn, tn = compute_statistics(df)
    
    true_mt = df[df['is_main_track'] == 1]
    false_mt = df[df['is_main_track'] == 0]
    
    # Perform threshold scan
    print("Performing threshold scan...")
    thresholds = np.linspace(0.1, 0.95, 50)
    scan_df = threshold_scan(df, thresholds)
    
    # Create PDF with multiple pages
    with PdfPages(output_pdf) as pdf:
        # Page 1: Main scatter plot + summary
        fig = plt.figure(figsize=(11, 8.5))
        
        # Large scatter plot
        ax1 = plt.subplot2grid((3, 2), (0, 0), colspan=2, rowspan=2)
        plot_energy_vs_prediction(ax1, df, true_mt, false_mt)
        
        # Summary text
        ax2 = plt.subplot2grid((3, 2), (2, 0), colspan=2)
        create_summary_text(ax2, stats, tp, fp, fn, tn)
        
        plt.suptitle('MT Prediction Analysis - Energy vs Prediction', 
                     fontsize=14, fontweight='bold', y=0.98)
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        pdf.savefig(fig, dpi=150)
        plt.close()
        
        # Page 2: Detailed distributions
        fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
        
        plot_energy_distributions(axes[0, 0], tp, fp, fn, tn)
        plot_cumulative_energy(axes[0, 1], tp, fp)
        plot_energy_statistics(axes[1, 0], tp, fp, fn, tn)
        plot_prediction_distribution(axes[1, 1], df)
        
        plt.suptitle('MT Prediction Analysis - Detailed Distributions', 
                     fontsize=14, fontweight='bold')
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        pdf.savefig(fig, dpi=150)
        plt.close()
        
        # Page 3: Threshold scan analysis
        fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
        
        plot_contamination_vs_threshold(axes[0, 0], scan_df)
        plot_recall_vs_threshold(axes[0, 1], scan_df)
        plot_precision_vs_threshold(axes[1, 0], scan_df)
        plot_f1_vs_threshold(axes[1, 1], scan_df)
        
        plt.suptitle('MT Threshold Scan Analysis', 
                     fontsize=14, fontweight='bold')
        plt.tight_layout(rect=[0, 0, 1, 0.96])
        pdf.savefig(fig, dpi=150)
        plt.close()
    
    print(f"\n✓ Report saved to: {output_pdf}")
    
    # Save threshold scan CSV
    csv_output = output_pdf.replace('.pdf', '_threshold_data.csv')
    scan_df.to_csv(csv_output, index=False)
    print(f"✓ Threshold data saved to: {csv_output}")
    
    # Print summary to console
    print("\n" + "="*70)
    print("MT INFERENCE SUMMARY")
    print("="*70)
    print(f"Total clusters:           {stats['total']:,}")
    print(f"True main tracks:         {stats['true_main']:,}")
    print(f"Predicted main tracks:    {stats['pred_main']:,}")
    print(f"\nAccuracy:                 {stats['accuracy']:.1%}")
    print(f"Precision:                {stats['precision']:.1%}")
    print(f"Recall:                   {stats['recall']:.1%}")
    print(f"Contamination:            {stats['contamination']:.1%}")
    print(f"\nFP mean energy:           {fp['cluster_energy'].mean():.2f} MeV")
    print(f"TP mean energy:           {tp['cluster_energy'].mean():.2f} MeV")
    print("="*70)


def main():
    parser = argparse.ArgumentParser(
        description='Analyze MT predictions and generate PDF report',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('--predictions', type=str,
                        help='Path to MT predictions CSV file')
    parser.add_argument('--output', type=str,
                        help='Output PDF file')
    parser.add_argument('--cat', type=str,
                        help='Cat directory name (e.g., cat000001)')
    
    args = parser.parse_args()
    
    # Set defaults if cat is provided
    if args.cat:
        if not args.predictions:
            args.predictions = f'results/mt_inference_{args.cat}_v10/mt_predictions.csv'
        if not args.output:
            args.output = f'results/mt_inference_{args.cat}_v10/mt_analysis_report.pdf'
    
    if not args.predictions or not args.output:
        parser.error("Either provide --predictions and --output, or use --cat")
    
    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    generate_report(args.predictions, args.output)


if __name__ == '__main__':
    main()
