#!/usr/bin/env python3
"""
Unified MT identification analysis tool.
Runs inference, analyzes false positives, and generates comprehensive plots.
"""

import sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix, roc_curve, auc, precision_recall_curve
import tensorflow as tf

# Add python directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'python'))
from sample_loader import load_and_select_samples

def run_mt_analysis(n_cc_events, n_es_events, output_name="mt_analysis"):
    """
    Run complete MT identification analysis.
    
    Args:
        n_cc_events: Number of CC events to load
        n_es_events: Number of ES events to load
        output_name: Name for output files
    """
    
    # Corrected production data paths
    cc_folder = "/eos/home-e/evilla/dune/sn-tps/prod_cc/cc_production_cluster_images_tick3_ch2_min2_tot3_e2p0/X"
    es_folder = "/eos/home-e/evilla/dune/sn-tps/prod_es/es_production_cluster_images_tick3_ch2_min2_tot3_e2p0/X"
    
    # Best MT model
    mt_model_path = "/eos/user/e/evilla/dune/sn-tps/neural_networks/mt_identifier/v10_100k_nov13/mt_identifier_simple_cnn_20251113_145400/models/best_model.keras"
    
    output_dir = Path(f"results/{output_name}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 80)
    print(f"MT IDENTIFICATION ANALYSIS - {n_cc_events} CC + {n_es_events} ES events")
    print("=" * 80)
    
    # Load samples
    print("\n[Step 1] Loading samples from corrected production data...")
    result = load_and_select_samples(
        cc_folder=cc_folder,
        es_folder=es_folder,
        n_cc_events=n_cc_events,
        n_es_events=n_es_events,
        file_pattern="*_planeX.npz",
        shuffle=True,
        random_seed=42,
        verbose=True
    )
    
    images = result['images']
    metadata = result['metadata']
    total_clusters = len(images)
    
    print(f"\n✓ Loaded {total_clusters:,} clusters")
    print(f"  CC Events: {result['n_cc_events']:,} ({result['n_cc_clusters']:,} clusters)")
    print(f"  ES Events: {result['n_es_events']:,} ({result['n_es_clusters']:,} clusters)")
    
    # Extract ground truth
    print("\n[Step 2] Extracting ground truth labels...")
    y_true = metadata[:, 2].astype(int)  # is_main_track
    is_es = metadata[:, 3].astype(int)   # is_es_interaction
    is_marley = metadata[:, 1].astype(int)  # is_marley
    cluster_energy = metadata[:, 10]  # cluster_energy
    
    n_mt = np.sum(y_true == 1)
    n_not_mt = np.sum(y_true == 0)
    
    print(f"  Main Tracks:     {n_mt:5,} ({100*n_mt/total_clusters:5.2f}%)")
    print(f"  Not Main Tracks: {n_not_mt:5,} ({100*n_not_mt/total_clusters:5.2f}%)")
    
    # Load model and predict
    print(f"\n[Step 3] Loading MT model v10 and running inference...")
    model = tf.keras.models.load_model(mt_model_path)
    y_pred_proba = model.predict(images, batch_size=128, verbose=1)
    y_pred_proba = y_pred_proba.ravel()
    
    # Calculate metrics at threshold=0.5
    print("\n[Step 4] Calculating metrics...")
    threshold = 0.5
    y_pred = (y_pred_proba >= threshold).astype(int)
    
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel()
    
    accuracy = (tp + tn) / (tn + fp + fn + tp)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    fpr, tpr, _ = roc_curve(y_true, y_pred_proba)
    roc_auc = auc(fpr, tpr)
    
    print(f"\n  Accuracy:  {accuracy:.4f} ({100*accuracy:.2f}%)")
    print(f"  Precision: {precision:.4f} ({100*precision:.2f}%)")
    print(f"  Recall:    {recall:.4f} ({100*recall:.2f}%)")
    print(f"  F1-Score:  {f1_score:.4f}")
    print(f"  AUC-ROC:   {roc_auc:.4f}")
    
    # Analyze false positives
    print("\n[Step 5] Analyzing false positives...")
    fp_mask = (y_true == 0) & (y_pred == 1)
    tn_mask = (y_true == 0) & (y_pred == 0)
    tp_mask = (y_true == 1) & (y_pred == 1)
    fn_mask = (y_true == 1) & (y_pred == 0)
    
    n_fp = np.sum(fp_mask)
    fp_is_marley = is_marley[fp_mask]
    fp_marley = np.sum(fp_is_marley == 1)
    fp_background = np.sum(fp_is_marley == 0)
    
    total_marley_secondary = fp_marley + np.sum(is_marley[tn_mask] == 1)
    total_background = fp_background + np.sum(is_marley[tn_mask] == 0)
    
    marley_fp_rate = 100 * fp_marley / total_marley_secondary if total_marley_secondary > 0 else 0
    background_fp_rate = 100 * fp_background / total_background if total_background > 0 else 0
    
    print(f"\n  False Positive Nature:")
    print(f"    Marley secondary: {fp_marley:5,} ({100*fp_marley/n_fp:5.2f}%) - FP rate: {marley_fp_rate:.2f}%")
    print(f"    Background:       {fp_background:5,} ({100*fp_background/n_fp:5.2f}%) - FP rate: {background_fp_rate:.2f}%")
    
    # Save predictions
    np.savez(output_dir / "predictions.npz",
             y_true=y_true,
             y_pred_proba=y_pred_proba,
             is_es=is_es,
             is_marley=is_marley,
             cluster_energy=cluster_energy,
             metadata=metadata)
    
    print(f"\n✓ Saved predictions to {output_dir / 'predictions.npz'}")
    
    # Generate comprehensive plots
    print("\n[Step 6] Generating comprehensive plots...")
    
    fig = plt.figure(figsize=(20, 12))
    gs = fig.add_gridspec(3, 4, hspace=0.3, wspace=0.3)
    
    fig.suptitle(f'MT Identification Analysis - {n_cc_events} CC + {n_es_events} ES events (v10 model)', 
                 fontsize=18, fontweight='bold')
    
    # Plot 1: ROC Curve
    ax = fig.add_subplot(gs[0, 0])
    ax.plot(fpr, tpr, 'b-', linewidth=2, label=f'AUC = {roc_auc:.4f}')
    ax.plot([0, 1], [0, 1], 'k--', linewidth=1)
    ax.set_xlabel('False Positive Rate', fontsize=11)
    ax.set_ylabel('True Positive Rate', fontsize=11)
    ax.set_title('ROC Curve', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # Plot 2: Precision-Recall Curve
    ax = fig.add_subplot(gs[0, 1])
    prec_curve, rec_curve, _ = precision_recall_curve(y_true, y_pred_proba)
    ax.plot(rec_curve, prec_curve, 'g-', linewidth=2)
    ax.set_xlabel('Recall', fontsize=11)
    ax.set_ylabel('Precision', fontsize=11)
    ax.set_title('Precision-Recall Curve', fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # Plot 3: Confusion Matrix
    ax = fig.add_subplot(gs[0, 2])
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=ax, cbar=True, 
                annot_kws={'fontsize': 11})
    ax.set_xlabel('Predicted', fontsize=11)
    ax.set_ylabel('True', fontsize=11)
    ax.set_title(f'Confusion Matrix (thr=0.5)', fontsize=13, fontweight='bold')
    ax.set_xticklabels(['Non-MT', 'MT'])
    ax.set_yticklabels(['Non-MT', 'MT'])
    
    # Plot 4: Prediction histogram
    ax = fig.add_subplot(gs[0, 3])
    ax.hist(y_pred_proba[y_true == 0], bins=50, alpha=0.6, label='True Non-MT', 
            color='red', density=True)
    ax.hist(y_pred_proba[y_true == 1], bins=50, alpha=0.6, label='True MT', 
            color='blue', density=True)
    ax.axvline(0.5, color='k', linestyle='--', linewidth=2)
    ax.set_xlabel('Prediction Probability', fontsize=11)
    ax.set_ylabel('Density', fontsize=11)
    ax.set_title('Prediction Distribution', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # Plot 5: FP composition pie chart
    ax = fig.add_subplot(gs[1, 0])
    labels = ['Marley\nSecondary', 'Background']
    sizes = [fp_marley, fp_background]
    colors = ['#ff9999', '#66b3ff']
    explode = (0.05, 0.05)
    ax.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
           shadow=True, startangle=90, textprops={'fontsize': 11, 'fontweight': 'bold'})
    ax.set_title(f'False Positive Nature\n({n_fp:,} total)', fontsize=13, fontweight='bold')
    
    # Plot 6: FP rates by type
    ax = fig.add_subplot(gs[1, 1])
    categories = ['Marley\nSecondary', 'Background']
    fp_rates = [marley_fp_rate, background_fp_rate]
    colors = ['#ff9999', '#66b3ff']
    bars = ax.bar(categories, fp_rates, color=colors, edgecolor='black', linewidth=2)
    ax.set_ylabel('False Positive Rate (%)', fontsize=11)
    ax.set_title('FP Rate by Cluster Type', fontsize=13, fontweight='bold')
    ax.grid(True, axis='y', alpha=0.3)
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}%', ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    # Plot 7: Energy distribution comparison
    ax = fig.add_subplot(gs[1, 2])
    bins = np.linspace(0, 100, 40)
    ax.hist(cluster_energy[tp_mask], bins=bins, alpha=0.5, label=f'True MT (n={tp})', 
            color='green', density=True)
    ax.hist(cluster_energy[fp_mask & (is_marley==1)], bins=bins, alpha=0.5, 
            label=f'FP Marley (n={fp_marley})', color='red', density=True)
    ax.hist(cluster_energy[fp_mask & (is_marley==0)], bins=bins, alpha=0.5, 
            label=f'FP Bg (n={fp_background})', color='blue', density=True)
    ax.set_xlabel('Cluster Energy (MeV)', fontsize=11)
    ax.set_ylabel('Density', fontsize=11)
    ax.set_title('Energy Distribution', fontsize=13, fontweight='bold')
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    
    # Plot 8: Prediction vs Energy (NEW!)
    ax = fig.add_subplot(gs[1, 3])
    
    # Sample to avoid overplotting
    max_points = 5000
    if len(y_pred_proba) > max_points:
        sample_idx = np.random.choice(len(y_pred_proba), max_points, replace=False)
    else:
        sample_idx = np.arange(len(y_pred_proba))
    
    # Plot different categories
    tp_idx = sample_idx[tp_mask[sample_idx]]
    fp_marley_idx = sample_idx[fp_mask[sample_idx] & (is_marley[sample_idx] == 1)]
    fp_bg_idx = sample_idx[fp_mask[sample_idx] & (is_marley[sample_idx] == 0)]
    tn_idx = sample_idx[tn_mask[sample_idx]]
    
    ax.scatter(cluster_energy[tn_idx], y_pred_proba[tn_idx], 
               alpha=0.3, c='gray', s=10, label=f'TN (n={tn})', rasterized=True)
    ax.scatter(cluster_energy[fp_bg_idx], y_pred_proba[fp_bg_idx], 
               alpha=0.5, c='blue', s=15, label=f'FP Bg ({fp_background})', rasterized=True)
    ax.scatter(cluster_energy[fp_marley_idx], y_pred_proba[fp_marley_idx], 
               alpha=0.5, c='red', s=15, label=f'FP Marley ({fp_marley})', rasterized=True)
    ax.scatter(cluster_energy[tp_idx], y_pred_proba[tp_idx], 
               alpha=0.4, c='green', s=20, label=f'TP (n={tp})', rasterized=True)
    
    ax.axhline(0.5, color='k', linestyle='--', linewidth=1, alpha=0.5)
    ax.set_xlabel('Cluster Energy (MeV)', fontsize=11)
    ax.set_ylabel('Prediction Probability', fontsize=11)
    ax.set_title('Prediction vs Energy', fontsize=13, fontweight='bold')
    ax.legend(fontsize=8, loc='lower right')
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 60)
    
    # Plot 9: Energy vs Confidence for FPs
    ax = fig.add_subplot(gs[2, 0])
    ax.scatter(cluster_energy[fp_mask & (is_marley==1)], y_pred_proba[fp_mask & (is_marley==1)], 
               alpha=0.4, c='red', s=15, label='FP Marley')
    ax.scatter(cluster_energy[fp_mask & (is_marley==0)], y_pred_proba[fp_mask & (is_marley==0)], 
               alpha=0.4, c='blue', s=15, label='FP Background')
    ax.set_xlabel('Cluster Energy (MeV)', fontsize=11)
    ax.set_ylabel('Prediction Probability', fontsize=11)
    ax.set_title('FP: Energy vs Confidence', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 40)
    
    # Plot 10: Confidence distribution for FPs
    ax = fig.add_subplot(gs[2, 1])
    bins = np.linspace(0.5, 1.0, 30)
    ax.hist(y_pred_proba[fp_mask & (is_marley==1)], bins=bins, alpha=0.6, 
            label='Marley secondary', color='red', density=True)
    ax.hist(y_pred_proba[fp_mask & (is_marley==0)], bins=bins, alpha=0.6, 
            label='Background', color='blue', density=True)
    ax.set_xlabel('Prediction Probability', fontsize=11)
    ax.set_ylabel('Density', fontsize=11)
    ax.set_title('FP Prediction Confidence', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # Plot 11: Metrics vs Threshold
    ax = fig.add_subplot(gs[2, 2])
    thresholds_plot = np.linspace(0, 1, 100)
    accuracies, precisions, recalls, f1_scores = [], [], [], []
    
    for t in thresholds_plot:
        y_p = (y_pred_proba >= t).astype(int)
        cm_t = confusion_matrix(y_true, y_p)
        tn_t, fp_t, fn_t, tp_t = cm_t.ravel()
        
        acc = (tp_t + tn_t) / (tn_t + fp_t + fn_t + tp_t)
        prec = tp_t / (tp_t + fp_t) if (tp_t + fp_t) > 0 else 0.0
        rec = tp_t / (tp_t + fn_t) if (tp_t + fn_t) > 0 else 0.0
        f1 = 2 * (prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        
        accuracies.append(acc)
        precisions.append(prec)
        recalls.append(rec)
        f1_scores.append(f1)
    
    ax.plot(thresholds_plot, accuracies, 'b-', linewidth=2, label='Accuracy')
    ax.plot(thresholds_plot, precisions, 'g-', linewidth=2, label='Precision')
    ax.plot(thresholds_plot, recalls, 'r-', linewidth=2, label='Recall')
    ax.plot(thresholds_plot, f1_scores, 'm-', linewidth=2, label='F1-Score')
    ax.axvline(0.5, color='k', linestyle='--', linewidth=1, alpha=0.5)
    ax.set_xlabel('Threshold', fontsize=11)
    ax.set_ylabel('Score', fontsize=11)
    ax.set_title('Metrics vs Threshold', fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # Plot 12: Summary statistics table
    ax = fig.add_subplot(gs[2, 3])
    ax.axis('off')
    
    summary_text = f"""
PERFORMANCE SUMMARY

Dataset: {n_cc_events} CC + {n_es_events} ES events
Total clusters: {total_clusters:,}
Main tracks: {n_mt:,} ({100*n_mt/total_clusters:.1f}%)

Metrics @ threshold=0.5:
  Accuracy:  {100*accuracy:5.2f}%
  Precision: {100*precision:5.2f}%
  Recall:    {100*recall:5.2f}%
  F1-Score:  {f1_score:.4f}
  AUC-ROC:   {roc_auc:.4f}

Confusion Matrix:
  TP: {tp:5,}  FN: {fn:5,}
  FP: {fp:5,}  TN: {tn:5,}

False Positives:
  Total: {n_fp:,}
  Marley: {fp_marley:,} ({100*fp_marley/n_fp:.1f}%)
  Background: {fp_background:,} ({100*fp_background/n_fp:.1f}%)

FP Rates:
  Marley secondary: {marley_fp_rate:.1f}%
  Background: {background_fp_rate:.1f}%

Energy (MeV):
  True MT: {np.mean(cluster_energy[tp_mask]):.1f}±{np.std(cluster_energy[tp_mask]):.1f}
  FP Marley: {np.mean(cluster_energy[fp_mask & (is_marley==1)]):.1f}±{np.std(cluster_energy[fp_mask & (is_marley==1)]):.1f}
"""
    
    ax.text(0.05, 0.95, summary_text, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
    
    plt.savefig(output_dir / f"{output_name}.pdf", dpi=150, bbox_inches='tight')
    print(f"✓ Saved comprehensive plots to {output_dir / f'{output_name}.pdf'}")
    
    # Save summary statistics
    with open(output_dir / "summary.txt", 'w') as f:
        f.write(f"MT IDENTIFICATION ANALYSIS SUMMARY\n")
        f.write(f"={'=' * 70}\n\n")
        f.write(f"Dataset: {n_cc_events} CC + {n_es_events} ES events\n")
        f.write(f"Total clusters: {total_clusters:,}\n")
        f.write(f"Main tracks: {n_mt:,} ({100*n_mt/total_clusters:.2f}%)\n")
        f.write(f"Non-main tracks: {n_not_mt:,} ({100*n_not_mt/total_clusters:.2f}%)\n\n")
        f.write(f"Performance @ threshold=0.5:\n")
        f.write(f"  Accuracy:  {accuracy:.4f} ({100*accuracy:.2f}%)\n")
        f.write(f"  Precision: {precision:.4f} ({100*precision:.2f}%)\n")
        f.write(f"  Recall:    {recall:.4f} ({100*recall:.2f}%)\n")
        f.write(f"  F1-Score:  {f1_score:.4f}\n")
        f.write(f"  AUC-ROC:   {roc_auc:.4f}\n\n")
        f.write(f"Confusion Matrix:\n")
        f.write(f"  TP: {tp:,}  FN: {fn:,}\n")
        f.write(f"  FP: {fp:,}  TN: {tn:,}\n\n")
        f.write(f"False Positive Analysis:\n")
        f.write(f"  Total FPs: {n_fp:,}\n")
        f.write(f"  Marley secondary: {fp_marley:,} ({100*fp_marley/n_fp:.2f}%)\n")
        f.write(f"  Background: {fp_background:,} ({100*fp_background/n_fp:.2f}%)\n\n")
        f.write(f"  FP Rate - Marley secondary: {marley_fp_rate:.2f}%\n")
        f.write(f"  FP Rate - Background: {background_fp_rate:.2f}%\n")
    
    print(f"✓ Saved summary to {output_dir / 'summary.txt'}")
    
    print("\n" + "=" * 80)
    print("✓ ANALYSIS COMPLETE")
    print("=" * 80)
    
    return {
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1_score': f1_score,
        'auc_roc': roc_auc,
        'n_fp': n_fp,
        'fp_marley': fp_marley,
        'fp_background': fp_background
    }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='MT identification analysis tool')
    parser.add_argument('--n-cc', type=int, default=660, help='Number of CC events')
    parser.add_argument('--n-es', type=int, default=660, help='Number of ES events')
    parser.add_argument('--output', type=str, default='mt_analysis', help='Output name')
    
    args = parser.parse_args()
    run_mt_analysis(args.n_cc, args.n_es, args.output)
