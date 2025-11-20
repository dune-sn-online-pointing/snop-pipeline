#!/usr/bin/env python3
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import sys
import time
sys.path.insert(0, '/afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline')
from pathlib import Path
import numpy as np

cat_name = "cat000002"
cat_dir = f"/eos/project-e/ep-nu/evilla/sn-pointing/{cat_name}"

print(f"Testing {cat_name}")
print(f"Cat dir exists: {Path(cat_dir).exists()}")

# Test loading matched 3-plane images
cluster_dir_base = Path(cat_dir) / f"{cat_name}_cluster_images_tick3_ch2_min2_tot3_e3p0"
print(f"Cluster dir exists: {cluster_dir_base.exists()}")

if cluster_dir_base.exists():
    cluster_dir_x = cluster_dir_base / 'X'
    npz_files_x = sorted(cluster_dir_x.glob("*.npz"))
    print(f"Found {len(npz_files_x)} npz files in X plane")
    
    # Try loading first file
    if npz_files_x:
        print(f"Testing load of first file: {npz_files_x[0].name}")
        t0 = time.time()
        data = np.load(npz_files_x[0])
        print(f"Loaded in {time.time()-t0:.2f}s")
        print(f"Keys: {list(data.keys())}")
        print(f"Images shape: {data['images'].shape}")
        print(f"Metadata shape: {data['metadata'].shape}")
        print("SUCCESS - Data loads fine")
