#!/usr/bin/env python3
"""
Test MT identification on CORRECTED production data (20 CATs).
Uses best MT model v10 and generates comparison plots.
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

# Corrected production data paths (X plane subdirectory)
cc_folder = "/eos/home-e/evilla/dune/sn-tps/prod_cc/cc_production_cluster_images_tick3_ch2_min2_tot3_e2p0/X"
es_folder = "/eos/home-e/evilla/dune/sn-tps/prod_es/es_production_cluster_images_tick3_ch2_min2_tot3_e2p0/X"

# Best MT model
mt_model_path = "/eos/user/e/evilla/dune/sn-tps/neural_networks/mt_identifier/v10_100k_nov13/mt_identifier_simple_cnn_20251113_145400/models/best_model.keras"

output_dir = Path("results/mt_corrected_data_test")
output_dir.mkdir(parents=True, exist_ok=True)

print("=" * 80)
print("MT IDENTIFICATION TEST - CORRECTED DATA (20 CATs)")
print("=" * 80)

# Step 1: Load samples from ~20 CAT files  
print("\n[Step 1] Loading samples from corrected production data...")
print(f"  CC folder: {cc_folder}")
print(f"  ES folder: {es_folder}")

result = load_and_select_samples(
    cc_folder=cc_folder,
    es_folder=es_folder,
    n_cc_events=660,  # 20 CATs * 33 events/CAT
    n_es_events=660,  # Balance CC and ES
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

# Step 2: Extract ground truth
print("\n[Step 2] Ground Truth Analysis...")
y_true = metadata[:, 2].astype(int)  # is_main_track
is_es = metadata[:, 3].astype(int)   # is_es_interaction

n_mt = np.sum(y_true == 1)
n_not_mt = np.sum(y_true == 0)
n_cc = np.sum(is_es == 0)
n_es = np.sum(is_es == 1)

print(f"\n  True Labels:")
print(f"    Main Tracks:     {n_mt:5,} ({100*n_mt/total_clusters:5.2f}%)")
print(f"    Not Main Tracks: {n_not_mt:5,} ({100*n_not_mt/total_clusters:5.2f}%)")
print(f"\n  Interaction Types:")
print(f"    CC: {n_cc:5,} ({100*n_cc/total_clusters:5.2f}%)")
print(f"    ES: {n_es:5,} ({100*n_es/total_clusters:5.2f}%)")

# Step 3: Load model and predict
print(f"\n[Step 3] Loading MT model: v10...")
print(f"  Model: {mt_model_path}")

model = tf.keras.models.load_model(mt_model_path)
print(f"  Model loaded successfully")

print(f"\n[Step 4] Running predictions on {total_clusters:,} clusters...")
y_pred_proba = model.predict(images, batch_size=128, verbose=1)
y_pred_proba = y_pred_proba.ravel()

# Step 5: Calculate metrics at different thresholds
print("\n[Step 5] Calculating metrics...")

thresholds = [0.3, 0.4, 0.5, 0.6, 0.7]
results_list = []

for threshold in thresholds:
    y_pred = (y_pred_proba >= threshold).astype(int)
    
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel()
    
    total = tn + fp + fn + tp
    accuracy = (tp + tn) / total
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    results_list.append({
        'threshold': threshold,
        'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn,
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'specificity': specificity,
        'f1_score': f1_score
    })

# Calculate AUC
fpr, tpr, _ = roc_curve(y_true, y_pred_proba)
roc_auc = auc(fpr, tpr)

# Print results
print("\n" + "=" * 80)
print("RESULTS AT DIFFERENT THRESHOLDS")
print("=" * 80)
print(f"\n{'Thresh':<8} {'Acc':<7} {'Prec':<7} {'Recall':<7} {'Spec':<7} {'F1':<7} {'TP':>6} {'TN':>6} {'FP':>6} {'FN':>6}")
print("-" * 80)

for r in results_list:
    print(f"{r['threshold']:<8.2f} {r['accuracy']:<7.4f} {r['precision']:<7.4f} {r['recall']:<7.4f} "
          f"{r['specificity']:<7.4f} {r['f1_score']:<7.4f} {r['tp']:>6,} {r['tn']:>6,} {r['fp']:>6,} {r['fn']:>6,}")

print(f"\nAUC-ROC: {roc_auc:.4f}")

# Save numerical results
np.savez(output_dir / "predictions.npz",
         y_true=y_true,
         y_pred_proba=y_pred_proba,
         is_es=is_es,
         metadata=metadata)

print(f"\n✓ Saved predictions to {output_dir / 'predictions.npz'}")

# Step 6: Generate plots
print("\n[Step 6] Generating plots...")

fig, axes = plt.subplots(2, 3, figsize=(18, 12))
fig.suptitle('MT Identification on Corrected Data (20 CATs, v10 model)', fontsize=16, fontweight='bold')

# Plot 1: ROC Curve
ax = axes[0, 0]
ax.plot(fpr, tpr, 'b-', linewidth=2, label=f'ROC (AUC = {roc_auc:.4f})')
ax.plot([0, 1], [0, 1], 'k--', linewidth=1)
ax.set_xlabel('False Positive Rate', fontsize=12)
ax.set_ylabel('True Positive Rate', fontsize=12)
ax.set_title('ROC Curve', fontsize=14, fontweight='bold')
ax.legend(fontsize=11)
ax.grid(True, alpha=0.3)

# Plot 2: Precision-Recall Curve
ax = axes[0, 1]
precision_curve, recall_curve, _ = precision_recall_curve(y_true, y_pred_proba)
ax.plot(recall_curve, precision_curve, 'g-', linewidth=2)
ax.set_xlabel('Recall', fontsize=12)
ax.set_ylabel('Precision', fontsize=12)
ax.set_title('Precision-Recall Curve', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3)

# Plot 3: Confusion Matrix at threshold=0.5
ax = axes[0, 2]
y_pred_05 = (y_pred_proba >= 0.5).astype(int)
cm_05 = confusion_matrix(y_true, y_pred_05)
sns.heatmap(cm_05, annot=True, fmt='d', cmap='Blues', ax=ax, cbar=True)
ax.set_xlabel('Predicted', fontsize=12)
ax.set_ylabel('True', fontsize=12)
ax.set_title('Confusion Matrix (threshold=0.5)', fontsize=14, fontweight='bold')
ax.set_xticklabels(['Non-MT', 'MT'])
ax.set_yticklabels(['Non-MT', 'MT'])

# Plot 4: Prediction histogram
ax = axes[1, 0]
ax.hist(y_pred_proba[y_true == 0], bins=50, alpha=0.6, label='True Non-MT', color='red', density=True)
ax.hist(y_pred_proba[y_true == 1], bins=50, alpha=0.6, label='True MT', color='blue', density=True)
ax.axvline(0.5, color='k', linestyle='--', linewidth=2, label='Threshold=0.5')
ax.set_xlabel('Prediction Probability', fontsize=12)
ax.set_ylabel('Density', fontsize=12)
ax.set_title('Prediction Distribution', fontsize=14, fontweight='bold')
ax.legend(fontsize=11)
ax.grid(True, alpha=0.3)

# Plot 5: Metrics vs Threshold
ax = axes[1, 1]
thresholds_plot = np.linspace(0, 1, 100)
accuracies = []
precisions = []
recalls = []
f1_scores = []

for t in thresholds_plot:
    y_p = (y_pred_proba >= t).astype(int)
    cm = confusion_matrix(y_true, y_p)
    tn, fp, fn, tp = cm.ravel()
    
    acc = (tp + tn) / (tn + fp + fn + tp)
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
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
ax.set_xlabel('Threshold', fontsize=12)
ax.set_ylabel('Score', fontsize=12)
ax.set_title('Metrics vs Threshold', fontsize=14, fontweight='bold')
ax.legend(fontsize=11)
ax.grid(True, alpha=0.3)

# Plot 6: CC vs ES breakdown
ax = axes[1, 2]
cc_mask = is_es == 0
es_mask = is_es == 1

# For each interaction type, show MT identification performance
cc_mt_true = np.sum((y_true == 1) & cc_mask)
cc_mt_pred = np.sum((y_pred_05 == 1) & cc_mask)
es_mt_true = np.sum((y_true == 1) & es_mask)
es_mt_pred = np.sum((y_pred_05 == 1) & es_mask)

categories = ['CC\nTrue MT', 'CC\nPred MT', 'ES\nTrue MT', 'ES\nPred MT']
values = [cc_mt_true, cc_mt_pred, es_mt_true, es_mt_pred]
colors = ['#1f77b4', '#aec7e8', '#ff7f0e', '#ffbb78']

bars = ax.bar(categories, values, color=colors, edgecolor='black', linewidth=1.5)
ax.set_ylabel('Number of Clusters', fontsize=12)
ax.set_title('MT Identification by Interaction Type', fontsize=14, fontweight='bold')
ax.grid(True, axis='y', alpha=0.3)

# Add value labels on bars
for bar in bars:
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
            f'{int(height):,}',
            ha='center', va='bottom', fontsize=11, fontweight='bold')

plt.tight_layout()
plt.savefig(output_dir / "mt_analysis_corrected_data.pdf", dpi=150, bbox_inches='tight')
print(f"✓ Saved plots to {output_dir / 'mt_analysis_corrected_data.pdf'}")

print("\n" + "=" * 80)
print("✓ ANALYSIS COMPLETED")
print("=" * 80)
print(f"\nBest threshold appears to be around 0.5")
print(f"Model achieves {results_list[2]['accuracy']:.2%} accuracy at threshold=0.5")
print(f"Overall AUC-ROC: {roc_auc:.4f}")
