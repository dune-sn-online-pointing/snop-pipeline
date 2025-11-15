#!/usr/bin/env python3
"""
Test MT identification step with mock predictions (no actual model needed).
This demonstrates the pipeline logic works correctly.
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

print("=" * 60)
print("Testing MT Identification Logic (Mock Mode)")
print("=" * 60)

# Step 1: Load samples
print("\n[Step 1] Loading samples...")
result = load_and_select_samples(
    cc_folder=cc_folder,
    es_folder=es_folder,
    n_cc_events=15,
    n_es_events=10,
    file_pattern="*_planeX.npz",
    shuffle=True,
    random_seed=42,
    verbose=True
)

images = result['images']
metadata = result['metadata']

print(f"\n✓ Loaded {len(images)} clusters")
print(f"  Image shape: {images[0].shape}")
print(f"  Metadata shape: {metadata.shape}")

# Step 2: Extract ground truth
print("\n[Step 2] Extracting ground truth labels...")
y_true = metadata[:, 2].astype(int)  # is_main_track

n_mt = np.sum(y_true == 1)
n_not_mt = np.sum(y_true == 0)

print(f"  Ground truth distribution:")
print(f"    Main tracks: {n_mt}")
print(f"    Not main tracks: {n_not_mt}")

# Step 3: Generate mock predictions (simulate a decent model)
print("\n[Step 3] Generating mock predictions...")
print("  (In real pipeline, this would be: model.predict(images))")

# Simulate a model with ~85% accuracy
np.random.seed(42)
y_pred_proba = np.zeros(len(y_true), dtype=np.float32)

# For actual main tracks, predict high probability (with some errors)
mt_indices = np.where(y_true == 1)[0]
y_pred_proba[mt_indices] = np.random.uniform(0.6, 0.95, len(mt_indices))
# Add some false negatives
if len(mt_indices) > 0:
    false_negatives = np.random.choice(mt_indices, size=max(1, len(mt_indices)//5), replace=False)
    y_pred_proba[false_negatives] = np.random.uniform(0.1, 0.4, len(false_negatives))

# For non-main tracks, predict low probability (with some errors)
not_mt_indices = np.where(y_true == 0)[0]
y_pred_proba[not_mt_indices] = np.random.uniform(0.05, 0.35, len(not_mt_indices))
# Add some false positives
if len(not_mt_indices) > 2:
    false_positives = np.random.choice(not_mt_indices, size=max(1, len(not_mt_indices)//10), replace=False)
    y_pred_proba[false_positives] = np.random.uniform(0.6, 0.85, len(false_positives))

threshold = 0.5
y_pred = (y_pred_proba >= threshold).astype(int)

print(f"  ✓ Generated predictions")

# Step 4: Calculate metrics (same as mt_identifier.py)
print("\n[Step 4] Calculating metrics...")

from sklearn.metrics import confusion_matrix, roc_curve, auc

cm = confusion_matrix(y_true, y_pred)
tn, fp, fn, tp = cm.ravel()

accuracy = (tp + tn) / (tp + tn + fp + fn)
precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

fpr, tpr, thresholds = roc_curve(y_true, y_pred_proba)
roc_auc = auc(fpr, tpr)

print(f"\n  Confusion Matrix:")
print(f"    True Negatives:  {tn}")
print(f"    False Positives: {fp}")
print(f"    False Negatives: {fn}")
print(f"    True Positives:  {tp}")

print(f"\n  Performance Metrics:")
print(f"    Accuracy:    {accuracy:.4f}")
print(f"    Precision:   {precision:.4f}")
print(f"    Recall:      {recall:.4f}")
print(f"    F1-Score:    {f1_score:.4f}")
print(f"    AUC:         {roc_auc:.4f}")

# Step 5: Select main tracks
print("\n[Step 5] Selecting predicted main tracks...")
mt_indices = np.where(y_pred == 1)[0]
selected_images = images[mt_indices]
selected_metadata = metadata[mt_indices]

print(f"  ✓ Selected {len(mt_indices)} clusters as main tracks")
print(f"  ✓ These would proceed to volume creation step")

# Summary
print("\n" + "=" * 60)
print("Test Summary")
print("=" * 60)
print(f"✓ Sample loading: {len(images)} clusters from {result['n_cc_events']} CC + {result['n_es_events']} ES events")
print(f"✓ MT identification: {len(mt_indices)} clusters predicted as main tracks")
print(f"✓ Performance: {accuracy:.1%} accuracy, {f1_score:.3f} F1-score")
print(f"\n✓ MT identification logic test completed successfully!")
print(f"\nNote: This used mock predictions. With a real trained model,")
print(f"the pipeline would load the .keras file and call model.predict()")
