#!/usr/bin/env python3
"""
Simple test of sample loader with the 40-event test samples.
"""

import sys
from pathlib import Path

# Add python directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'python'))

from sample_loader import load_and_select_samples

# Test data paths
cc_folder = "/eos/home-e/evilla/dune/sn-tps/directions/prodmarley_nue_cc_gkvm_dune10kt_1x2x2_customDirection_cat1-triggerana_tree_1x2x2_simpleThr_production-40events/images_test_tick3_ch2_min2_tot3_e2p0"
es_folder = "/eos/home-e/evilla/dune/sn-tps/directions/prodmarley_nue_es_gkvm_dune10kt_1x2x2_customDirection_cat1-triggerana_tree_1x2x2_simpleThr_production-40events/images_test_tick3_ch2_min2_tot3_e2p0"

print("=" * 60)
print("Testing Sample Loader with 40-event samples")
print("=" * 60)

# Test with small numbers first (10 CC, 5 ES events)
print("\nLoading samples...")
result = load_and_select_samples(
    cc_folder=cc_folder,
    es_folder=es_folder,
    n_cc_events=10,
    n_es_events=5,
    file_pattern="*_planeX.npz",
    shuffle=True,
    random_seed=42,
    verbose=True
)

print("\n" + "=" * 60)
print("Results Summary:")
print("=" * 60)
print(f"CC Events: {result['n_cc_events']}")
print(f"CC Clusters: {result['n_cc_clusters']}")
print(f"ES Events: {result['n_es_events']}")
print(f"ES Clusters: {result['n_es_clusters']}")
print(f"Total Clusters: {result['total_clusters']}")
print(f"\nImage shape: {result['images'][0].shape}")
print(f"Metadata shape: {result['metadata'].shape}")
print(f"Metadata columns: {result['metadata'].shape[1]}")

# Check metadata
import numpy as np
print(f"\nMetadata column 2 (is_main_track): {np.unique(result['metadata'][:, 2], return_counts=True)}")
print(f"Metadata column 3 (is_es_interaction): {np.unique(result['metadata'][:, 3], return_counts=True)}")
print(f"Metadata column 12 (plane_number): {np.unique(result['metadata'][:, 12], return_counts=True)}")

print("\n✓ Sample loading test completed successfully!")
