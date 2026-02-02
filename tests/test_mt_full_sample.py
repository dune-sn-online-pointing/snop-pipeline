#!/usr/bin/env python3
"""
Test MT identification with FULL sample: 3300 CC + 325 ES events.
Shows detailed confusion matrix results in percentages.
"""

import sys
from pathlib import Path
import numpy as np

# Add python directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'python'))

from sample_loader import load_and_select_samples

# Test data paths
cc_folder = "/eos/home-e/evilla/dune/sn-tps/directions/prodmarley_nue_cc_gkvm_dune10kt_1x2x2_customDirection_cat1-triggerana_tree_1x2x2_simpleThr_production-40events/images_test_tick3_ch2_min2_tot3_e2p0"
es_folder = "/eos/home-e/evilla/dune/sn-tps/directions/prodmarley_nue_es_gkvm_dune10kt_1x2x2_customDirection_cat1-triggerana_tree_1x2x2_simpleThr_production-40events/images_test_tick3_ch2_min2_tot3_e2p0"

print("=" * 70)
print("MT IDENTIFICATION TEST - FULL SAMPLE (3300 CC + 325 ES events)")
print("=" * 70)

# Step 1: Load FULL samples
print("\n[Step 1] Loading samples...")
result = load_and_select_samples(
    cc_folder=cc_folder,
    es_folder=es_folder,
    n_cc_events=3300,
    n_es_events=325,
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

n_mt = np.sum(y_true == 1)
n_not_mt = np.sum(y_true == 0)
pct_mt = 100 * n_mt / total_clusters
pct_not_mt = 100 * n_not_mt / total_clusters

print(f"\n  True Labels:")
print(f"    Main Tracks:     {n_mt:5,} ({pct_mt:5.2f}%)")
print(f"    Not Main Tracks: {n_not_mt:5,} ({pct_not_mt:5.2f}%)")

# Step 3: Generate mock predictions (simulate realistic model)
print("\n[Step 3] Generating mock predictions (simulating trained model)...")

# Simulate a model with ~85-90% overall accuracy
np.random.seed(42)
y_pred_proba = np.zeros(len(y_true), dtype=np.float32)

# For actual main tracks, predict high probability (with ~15% error rate)
mt_indices = np.where(y_true == 1)[0]
y_pred_proba[mt_indices] = np.random.uniform(0.65, 0.95, len(mt_indices))
# Add some false negatives (15% of MTs)
if len(mt_indices) > 0:
    n_false_neg = int(0.15 * len(mt_indices))
    false_negatives = np.random.choice(mt_indices, size=n_false_neg, replace=False)
    y_pred_proba[false_negatives] = np.random.uniform(0.1, 0.45, len(false_negatives))

# For non-main tracks, predict low probability (with ~5% error rate)
not_mt_indices = np.where(y_true == 0)[0]
y_pred_proba[not_mt_indices] = np.random.uniform(0.05, 0.35, len(not_mt_indices))
# Add some false positives (5% of non-MTs)
if len(not_mt_indices) > 0:
    n_false_pos = int(0.05 * len(not_mt_indices))
    false_positives = np.random.choice(not_mt_indices, size=n_false_pos, replace=False)
    y_pred_proba[false_positives] = np.random.uniform(0.55, 0.85, len(false_positives))

threshold = 0.5
y_pred = (y_pred_proba >= threshold).astype(int)

n_pred_mt = np.sum(y_pred == 1)
n_pred_not_mt = np.sum(y_pred == 0)
pct_pred_mt = 100 * n_pred_mt / total_clusters
pct_pred_not_mt = 100 * n_pred_not_mt / total_clusters

print(f"\n  Predictions:")
print(f"    Predicted MT:     {n_pred_mt:5,} ({pct_pred_mt:5.2f}%)")
print(f"    Predicted non-MT: {n_pred_not_mt:5,} ({pct_pred_not_mt:5.2f}%)")

# Step 4: Calculate metrics
print("\n[Step 4] Performance Metrics...")

from sklearn.metrics import confusion_matrix, roc_curve, auc, classification_report

cm = confusion_matrix(y_true, y_pred)
tn, fp, fn, tp = cm.ravel()

total = tn + fp + fn + tp
accuracy = (tp + tn) / total
precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

fpr, tpr, thresholds = roc_curve(y_true, y_pred_proba)
roc_auc = auc(fpr, tpr)

# Print confusion matrix
print("\n" + "=" * 70)
print("CONFUSION MATRIX")
print("=" * 70)
print()
print("                    Predicted")
print("                    Non-MT              MT")
print("            ┌─────────────────┬─────────────────┐")
print(f"     Non-MT │  TN: {tn:6,}       │  FP: {fp:6,}      │")
print(f"            │  {100*tn/total:6.2f}%         │  {100*fp/total:6.2f}%        │")
print("  True      ├─────────────────┼─────────────────┤")
print(f"      MT    │  FN: {fn:6,}       │  TP: {tp:6,}      │")
print(f"            │  {100*fn/total:6.2f}%         │  {100*tp/total:6.2f}%        │")
print("            └─────────────────┴─────────────────┘")
print()

# Detailed breakdown
print("=" * 70)
print("DETAILED BREAKDOWN")
print("=" * 70)
print()
print(f"Total Samples: {total:,}")
print()
print(f"True Negatives (TN):  {tn:6,}  ({100*tn/total:6.2f}%)  - Correctly identified non-MT")
print(f"True Positives (TP):  {tp:6,}  ({100*tp/total:6.2f}%)  - Correctly identified MT")
print(f"False Positives (FP): {fp:6,}  ({100*fp/total:6.2f}%)  - Non-MT wrongly called MT")
print(f"False Negatives (FN): {fn:6,}  ({100*fn/total:6.2f}%)  - MT wrongly called non-MT")
print()

# Performance metrics
print("=" * 70)
print("PERFORMANCE METRICS")
print("=" * 70)
print()
print(f"Overall Accuracy:     {accuracy:6.4f}  ({100*accuracy:6.2f}%)")
print(f"Precision (MT):       {precision:6.4f}  ({100*precision:6.2f}%)")
print(f"Recall (MT):          {recall:6.4f}  ({100*recall:6.2f}%)")
print(f"Specificity (non-MT): {specificity:6.4f}  ({100*specificity:6.2f}%)")
print(f"F1-Score:             {f1_score:6.4f}")
print(f"AUC-ROC:              {roc_auc:6.4f}")
print()

# Class-specific metrics
print("=" * 70)
print("CLASS-SPECIFIC PERFORMANCE")
print("=" * 70)
print()
print("Main Track Class (Positive):")
print(f"  True MTs in dataset:     {n_mt:,}")
print(f"  Correctly identified:    {tp:,} ({100*tp/n_mt:.2f}% recall)")
print(f"  Missed (false negatives): {fn:,} ({100*fn/n_mt:.2f}%)")
print()
print("Non-Main Track Class (Negative):")
print(f"  True non-MTs in dataset: {n_not_mt:,}")
print(f"  Correctly identified:    {tn:,} ({100*tn/n_not_mt:.2f}% specificity)")
print(f"  Misclassified as MT:     {fp:,} ({100*fp/n_not_mt:.2f}%)")
print()

# Prediction quality
print("=" * 70)
print("PREDICTION QUALITY")
print("=" * 70)
print()
print("When model predicts 'Main Track':")
print(f"  Correct:   {tp:,} ({100*tp/(tp+fp):.2f}% precision)")
print(f"  Incorrect: {fp:,} ({100*fp/(tp+fp):.2f}%)")
print()
print("When model predicts 'Non-Main Track':")
print(f"  Correct:   {tn:,} ({100*tn/(tn+fn):.2f}% NPV)")
print(f"  Incorrect: {fn:,} ({100*fn/(tn+fn):.2f}%)")
print()

print("=" * 70)
print("✓ TEST COMPLETED")
print("=" * 70)
print()
print("NOTE: This test uses mock predictions to demonstrate the pipeline.")
print("With a real trained MT identification model, these metrics would")
print("reflect the actual model performance on the test data.")
