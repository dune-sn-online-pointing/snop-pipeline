#!/usr/bin/env python3
"""
Quick test to check data structure for a category.
Run on condor node to access EOS.
"""

from pathlib import Path
import numpy as np

BASE_PATH = Path("/eos/home-e/evilla/DUNE/supernova/train-40k-v3_100k")
CAT_NAME = "cat000030"

# Check cluster data
print(f"Checking {CAT_NAME}...")
print("\nCluster data (X plane):")
cluster_dir = BASE_PATH / "cluster_images_tick3_ch2_min2_tot3_e2p0" / "X" / CAT_NAME
npz_files = sorted(cluster_dir.glob("*.npz"))
print(f"  NPZ files found: {len(npz_files)}")

if npz_files:
    print(f"  First file: {npz_files[0].name}")
    print(f"  Last file: {npz_files[-1].name}")
    
    # Check if ES or CC is in filename
    for f in npz_files[:3]:
        print(f"    - {f.name}")

# Check TPS data
print("\nTPS data:")
tps_dir = BASE_PATH / "tps"
root_files = sorted(tps_dir.glob(f"{CAT_NAME}*.root"))
print(f"  ROOT files found: {len(root_files)}")

if root_files:
    print(f"  First file: {root_files[0].name}")
    print(f"  Last file: {root_files[-1].name}")
    
    # Check if ES or CC is in filename
    for f in root_files[:10]:
        interaction_type = "ES" if "es" in f.name.lower() else "CC" if "cc" in f.name.lower() else "UNKNOWN"
        print(f"    - {f.name} [{interaction_type}]")

# Load and check event counts
if npz_files:
    print("\nLoading first NPZ file to check structure...")
    data = np.load(npz_files[0])
    print(f"  Keys: {list(data.keys())}")
    print(f"  Images shape: {data['images'].shape}")
    print(f"  Metadata shape: {data['metadata'].shape}")
    
    # Check unique event IDs
    event_ids = data['metadata'][:, 0].astype(int)
    unique_events = np.unique(event_ids)
    print(f"  Event IDs in this file: {len(unique_events)}")
    print(f"  First few: {unique_events[:10]}")
    print(f"  Clusters per event (first 5): {[np.sum(event_ids == e) for e in unique_events[:5]]}")

print("\n✓ Done")
