#!/usr/bin/env python3
"""
Deep dive into false positives from MT identification.
Analyze: are they background or secondary Marley tracks?
"""

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Load predictions
data = np.load("results/mt_corrected_data_test/predictions.npz")
y_true = data['y_true']
y_pred_proba = data['y_pred_proba']
is_es = data['is_es']
metadata = data['metadata']

print("=" * 80)
print("FALSE POSITIVE ANALYSIS - MT IDENTIFICATION")
print("=" * 80)

# Metadata columns:
# 0: event, 1: is_marley, 2: is_main_track, 3: is_es_interaction
# 4-6: true_pos, 7-9: true_mom, 10: cluster_energy, 11: true_particle_energy, 12: plane

threshold = 0.5
y_pred = (y_pred_proba >= threshold).astype(int)

# Identify false positives
fp_mask = (y_true == 0) & (y_pred == 1)
tn_mask = (y_true == 0) & (y_pred == 0)
tp_mask = (y_true == 1) & (y_pred == 1)
fn_mask = (y_true == 1) & (y_pred == 0)

n_fp = np.sum(fp_mask)
n_tn = np.sum(tn_mask)
n_tp = np.sum(tp_mask)
n_fn = np.sum(fn_mask)

print(f"\nTotal clusters: {len(y_true):,}")
print(f"  True Positives:  {n_tp:5,} - Correctly identified main tracks")
print(f"  True Negatives:  {n_tn:5,} - Correctly rejected non-main tracks")
print(f"  False Positives: {n_fp:5,} - NON-main tracks wrongly called main")
print(f"  False Negatives: {n_fn:5,} - Main tracks missed")

# Extract metadata for FPs
fp_metadata = metadata[fp_mask]
tn_metadata = metadata[tn_mask]
tp_metadata = metadata[tp_mask]

# Column 1: is_marley (1 = marley, 0 = background)
fp_is_marley = fp_metadata[:, 1].astype(int)
tn_is_marley = tn_metadata[:, 1].astype(int)
tp_is_marley = tp_metadata[:, 1].astype(int)

# Column 3: is_es_interaction
fp_is_es = fp_metadata[:, 3].astype(int)
tn_is_es = tn_metadata[:, 3].astype(int)
tp_is_es = tp_metadata[:, 3].astype(int)

# Column 10: cluster_energy
fp_energy = fp_metadata[:, 10]
tn_energy = tn_metadata[:, 10]
tp_energy = tp_metadata[:, 10]

print("\n" + "=" * 80)
print("FALSE POSITIVE BREAKDOWN")
print("=" * 80)

# Key question: Are FPs background or secondary Marley tracks?
fp_marley = np.sum(fp_is_marley == 1)
fp_background = np.sum(fp_is_marley == 0)

print(f"\nFalse Positives Nature:")
print(f"  Marley clusters (secondary tracks): {fp_marley:5,} ({100*fp_marley/n_fp:5.2f}%)")
print(f"  Background clusters (noise):        {fp_background:5,} ({100*fp_background/n_fp:5.2f}%)")

# If they're Marley, are they ES or CC?
fp_marley_es = np.sum((fp_is_marley == 1) & (fp_is_es == 1))
fp_marley_cc = np.sum((fp_is_marley == 1) & (fp_is_es == 0))
fp_bg_es = np.sum((fp_is_marley == 0) & (fp_is_es == 1))
fp_bg_cc = np.sum((fp_is_marley == 0) & (fp_is_es == 0))

print(f"\n  Detailed breakdown:")
print(f"    Marley ES secondary: {fp_marley_es:5,} ({100*fp_marley_es/n_fp:5.2f}%)")
print(f"    Marley CC secondary: {fp_marley_cc:5,} ({100*fp_marley_cc/n_fp:5.2f}%)")
print(f"    Background in ES:    {fp_bg_es:5,} ({100*fp_bg_es/n_fp:5.2f}%)")
print(f"    Background in CC:    {fp_bg_cc:5,} ({100*fp_bg_cc/n_fp:5.2f}%)")

# Compare to True Negatives for context
tn_marley = np.sum(tn_is_marley == 1)
tn_background = np.sum(tn_is_marley == 0)

print(f"\nTrue Negatives (correctly rejected) Nature:")
print(f"  Marley clusters (secondary tracks): {tn_marley:5,} ({100*tn_marley/n_tn:5.2f}%)")
print(f"  Background clusters (noise):        {tn_background:5,} ({100*tn_background/n_tn:5.2f}%)")

# What fraction of Marley secondary tracks get wrongly called main?
total_marley_secondary = fp_marley + tn_marley  # All non-main Marley
marley_fp_rate = 100 * fp_marley / total_marley_secondary if total_marley_secondary > 0 else 0

total_background = fp_background + tn_background
background_fp_rate = 100 * fp_background / total_background if total_background > 0 else 0

print("\n" + "=" * 80)
print("FALSE POSITIVE RATES BY CLUSTER TYPE")
print("=" * 80)
print(f"\nMarley secondary tracks:")
print(f"  Total:           {total_marley_secondary:5,}")
print(f"  Wrongly called MT: {fp_marley:5,} ({marley_fp_rate:5.2f}%)")
print(f"  Correctly rejected: {tn_marley:5,} ({100-marley_fp_rate:5.2f}%)")

print(f"\nBackground clusters:")
print(f"  Total:           {total_background:5,}")
print(f"  Wrongly called MT: {fp_background:5,} ({background_fp_rate:5.2f}%)")
print(f"  Correctly rejected: {tn_background:5,} ({100-background_fp_rate:5.2f}%)")

# Energy analysis
print("\n" + "=" * 80)
print("ENERGY DISTRIBUTION ANALYSIS")
print("=" * 80)

print(f"\nCluster Energy Statistics (MeV):")
print(f"{'Category':<25} {'Mean':>8} {'Median':>8} {'Std':>8} {'Min':>8} {'Max':>8}")
print("-" * 80)
print(f"{'True Positives (MT)':<25} {np.mean(tp_energy):8.1f} {np.median(tp_energy):8.1f} "
      f"{np.std(tp_energy):8.1f} {np.min(tp_energy):8.1f} {np.max(tp_energy):8.1f}")
print(f"{'False Negatives (missed)':<25} {np.mean(metadata[fn_mask, 10]):8.1f} {np.median(metadata[fn_mask, 10]):8.1f} "
      f"{np.std(metadata[fn_mask, 10]):8.1f} {np.min(metadata[fn_mask, 10]):8.1f} {np.max(metadata[fn_mask, 10]):8.1f}")
print(f"{'False Positives (FP)':<25} {np.mean(fp_energy):8.1f} {np.median(fp_energy):8.1f} "
      f"{np.std(fp_energy):8.1f} {np.min(fp_energy):8.1f} {np.max(fp_energy):8.1f}")
print(f"{'  - Marley secondary':<25} {np.mean(fp_energy[fp_is_marley==1]):8.1f} {np.median(fp_energy[fp_is_marley==1]):8.1f} "
      f"{np.std(fp_energy[fp_is_marley==1]):8.1f} {np.min(fp_energy[fp_is_marley==1]):8.1f} {np.max(fp_energy[fp_is_marley==1]):8.1f}")
print(f"{'  - Background':<25} {np.mean(fp_energy[fp_is_marley==0]):8.1f} {np.median(fp_energy[fp_is_marley==0]):8.1f} "
      f"{np.std(fp_energy[fp_is_marley==0]):8.1f} {np.min(fp_energy[fp_is_marley==0]):8.1f} {np.max(fp_energy[fp_is_marley==0]):8.1f}")
print(f"{'True Negatives (TN)':<25} {np.mean(tn_energy):8.1f} {np.median(tn_energy):8.1f} "
      f"{np.std(tn_energy):8.1f} {np.min(tn_energy):8.1f} {np.max(tn_energy):8.1f}")

# Prediction confidence analysis
fp_confidence = y_pred_proba[fp_mask]
tn_confidence = y_pred_proba[tn_mask]
tp_confidence = y_pred_proba[tp_mask]

print("\n" + "=" * 80)
print("PREDICTION CONFIDENCE ANALYSIS")
print("=" * 80)

print(f"\nModel Confidence (prediction probability):")
print(f"{'Category':<25} {'Mean':>8} {'Median':>8} {'Std':>8} {'Q25':>8} {'Q75':>8}")
print("-" * 80)
print(f"{'True Positives':<25} {np.mean(tp_confidence):8.4f} {np.median(tp_confidence):8.4f} "
      f"{np.std(tp_confidence):8.4f} {np.percentile(tp_confidence, 25):8.4f} {np.percentile(tp_confidence, 75):8.4f}")
print(f"{'False Positives':<25} {np.mean(fp_confidence):8.4f} {np.median(fp_confidence):8.4f} "
      f"{np.std(fp_confidence):8.4f} {np.percentile(fp_confidence, 25):8.4f} {np.percentile(fp_confidence, 75):8.4f}")
print(f"{'  - Marley secondary':<25} {np.mean(fp_confidence[fp_is_marley==1]):8.4f} {np.median(fp_confidence[fp_is_marley==1]):8.4f} "
      f"{np.std(fp_confidence[fp_is_marley==1]):8.4f} {np.percentile(fp_confidence[fp_is_marley==1], 25):8.4f} {np.percentile(fp_confidence[fp_is_marley==1], 75):8.4f}")
print(f"{'  - Background':<25} {np.mean(fp_confidence[fp_is_marley==0]):8.4f} {np.median(fp_confidence[fp_is_marley==0]):8.4f} "
      f"{np.std(fp_confidence[fp_is_marley==0]):8.4f} {np.percentile(fp_confidence[fp_is_marley==0], 25):8.4f} {np.percentile(fp_confidence[fp_is_marley==0], 75):8.4f}")
print(f"{'True Negatives':<25} {np.mean(tn_confidence):8.4f} {np.median(tn_confidence):8.4f} "
      f"{np.std(tn_confidence):8.4f} {np.percentile(tn_confidence, 25):8.4f} {np.percentile(tn_confidence, 75):8.4f}")

# Check if there's a labeling issue
print("\n" + "=" * 80)
print("POTENTIAL LABELING ISSUE CHECK")
print("=" * 80)

# In corrected data, main cluster should be highest energy Marley cluster
# Check events with FPs to see if FP has higher energy than the true main track

# Get event numbers for analysis
fp_events = fp_metadata[:, 0].astype(int)
unique_fp_events = np.unique(fp_events)

print(f"\nEvents with false positives: {len(unique_fp_events):,}")
print(f"Total false positives: {n_fp:,}")
print(f"Average FPs per event: {n_fp/len(unique_fp_events):.2f}")

# Sample a few events to check
print(f"\nSampling 5 events with FPs for detailed inspection:")
sample_events = np.random.choice(unique_fp_events, size=min(5, len(unique_fp_events)), replace=False)

for evt in sample_events:
    evt_mask = metadata[:, 0] == evt
    evt_clusters = metadata[evt_mask]
    evt_is_mt = y_true[evt_mask]
    evt_pred = y_pred[evt_mask]
    evt_is_marley = evt_clusters[:, 1].astype(int)
    evt_energy = evt_clusters[:, 10]
    evt_is_es = evt_clusters[:, 3].astype(int)
    
    true_mt_idx = np.where(evt_is_mt == 1)[0]
    pred_mt_idx = np.where(evt_pred == 1)[0]
    marley_idx = np.where(evt_is_marley == 1)[0]
    
    print(f"\n  Event {evt}:")
    print(f"    Total clusters: {len(evt_clusters)}")
    print(f"    Marley clusters: {len(marley_idx)}")
    print(f"    True MT count: {len(true_mt_idx)}")
    print(f"    Predicted MT count: {len(pred_mt_idx)}")
    print(f"    Interaction type: {'ES' if evt_is_es[0] == 1 else 'CC'}")
    
    if len(true_mt_idx) > 0:
        true_mt_energy = evt_energy[true_mt_idx[0]]
        print(f"    True MT energy: {true_mt_energy:.1f} MeV")
    
    if len(marley_idx) > 0:
        marley_energies = evt_energy[marley_idx]
        print(f"    Marley energies: {', '.join([f'{e:.1f}' for e in marley_energies])} MeV")
        print(f"    Highest Marley: {np.max(marley_energies):.1f} MeV")

# Generate plots
print("\n" + "=" * 80)
print("GENERATING DIAGNOSTIC PLOTS")
print("=" * 80)

fig, axes = plt.subplots(2, 3, figsize=(18, 12))
fig.suptitle('False Positive Deep Dive Analysis', fontsize=16, fontweight='bold')

# Plot 1: FP composition pie chart
ax = axes[0, 0]
labels = ['Marley\nSecondary', 'Background']
sizes = [fp_marley, fp_background]
colors = ['#ff9999', '#66b3ff']
explode = (0.05, 0.05)
ax.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%',
       shadow=True, startangle=90, textprops={'fontsize': 12, 'fontweight': 'bold'})
ax.set_title(f'False Positive Nature\n({n_fp:,} total)', fontsize=14, fontweight='bold')

# Plot 2: FP rates by cluster type
ax = axes[0, 1]
categories = ['Marley\nSecondary', 'Background']
fp_rates = [marley_fp_rate, background_fp_rate]
colors = ['#ff9999', '#66b3ff']
bars = ax.bar(categories, fp_rates, color=colors, edgecolor='black', linewidth=2)
ax.set_ylabel('False Positive Rate (%)', fontsize=12)
ax.set_title('FP Rate by Cluster Type', fontsize=14, fontweight='bold')
ax.grid(True, axis='y', alpha=0.3)
for bar in bars:
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height,
            f'{height:.1f}%', ha='center', va='bottom', fontsize=12, fontweight='bold')

# Plot 3: Energy distribution comparison
ax = axes[0, 2]
bins = np.linspace(0, 200, 40)
ax.hist(tp_energy, bins=bins, alpha=0.5, label=f'True MT (n={n_tp})', color='green', density=True)
ax.hist(fp_energy[fp_is_marley==1], bins=bins, alpha=0.5, label=f'FP Marley (n={fp_marley})', color='red', density=True)
ax.hist(fp_energy[fp_is_marley==0], bins=bins, alpha=0.5, label=f'FP Bg (n={fp_background})', color='blue', density=True)
ax.set_xlabel('Cluster Energy (MeV)', fontsize=12)
ax.set_ylabel('Density', fontsize=12)
ax.set_title('Energy Distribution', fontsize=14, fontweight='bold')
ax.legend(fontsize=10)
ax.grid(True, alpha=0.3)

# Plot 4: Confidence distribution for FPs
ax = axes[1, 0]
bins = np.linspace(0.5, 1.0, 30)
ax.hist(fp_confidence[fp_is_marley==1], bins=bins, alpha=0.6, label='Marley secondary', color='red', density=True)
ax.hist(fp_confidence[fp_is_marley==0], bins=bins, alpha=0.6, label='Background', color='blue', density=True)
ax.set_xlabel('Prediction Probability', fontsize=12)
ax.set_ylabel('Density', fontsize=12)
ax.set_title('FP Prediction Confidence', fontsize=14, fontweight='bold')
ax.legend(fontsize=11)
ax.grid(True, alpha=0.3)

# Plot 5: 2D scatter - energy vs confidence
ax = axes[1, 1]
scatter1 = ax.scatter(fp_energy[fp_is_marley==1], fp_confidence[fp_is_marley==1], 
                     alpha=0.4, c='red', s=20, label='FP Marley')
scatter2 = ax.scatter(fp_energy[fp_is_marley==0], fp_confidence[fp_is_marley==0], 
                     alpha=0.4, c='blue', s=20, label='FP Background')
ax.set_xlabel('Cluster Energy (MeV)', fontsize=12)
ax.set_ylabel('Prediction Probability', fontsize=12)
ax.set_title('FP: Energy vs Confidence', fontsize=14, fontweight='bold')
ax.legend(fontsize=11)
ax.grid(True, alpha=0.3)
ax.set_xlim(0, 200)

# Plot 6: Summary table
ax = axes[1, 2]
ax.axis('off')

summary_text = f"""
KEY FINDINGS

Total False Positives: {n_fp:,}

Marley Secondary: {fp_marley:,} ({100*fp_marley/n_fp:.1f}%)
  - ES events: {fp_marley_es:,}
  - CC events: {fp_marley_cc:,}
  - FP rate: {marley_fp_rate:.1f}%
  
Background Noise: {fp_background:,} ({100*fp_background/n_fp:.1f}%)
  - ES events: {fp_bg_es:,}
  - CC events: {fp_bg_cc:,}
  - FP rate: {background_fp_rate:.1f}%

Energy (MeV):
  True MT:     {np.mean(tp_energy):.1f} ± {np.std(tp_energy):.1f}
  FP Marley:   {np.mean(fp_energy[fp_is_marley==1]):.1f} ± {np.std(fp_energy[fp_is_marley==1]):.1f}
  FP Bg:       {np.mean(fp_energy[fp_is_marley==0]):.1f} ± {np.std(fp_energy[fp_is_marley==0]):.1f}

Confidence:
  True MT:     {np.mean(tp_confidence):.3f}
  FP Marley:   {np.mean(fp_confidence[fp_is_marley==1]):.3f}
  FP Bg:       {np.mean(fp_confidence[fp_is_marley==0]):.3f}
"""

ax.text(0.1, 0.95, summary_text, transform=ax.transAxes, fontsize=11,
        verticalalignment='top', fontfamily='monospace',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))

plt.tight_layout()
plt.savefig("results/mt_corrected_data_test/false_positive_analysis.pdf", dpi=150, bbox_inches='tight')
print("✓ Saved diagnostic plots to results/mt_corrected_data_test/false_positive_analysis.pdf")

print("\n" + "=" * 80)
print("✓ ANALYSIS COMPLETE")
print("=" * 80)
