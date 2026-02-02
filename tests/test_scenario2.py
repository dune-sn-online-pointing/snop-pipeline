#!/usr/bin/env python3
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import sys
import time

print("START - Importing modules...", flush=True)
sys.path.insert(0, '/afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline')

import tensorflow as tf
from pathlib import Path

print("Imported TensorFlow", flush=True)

cat_name = "cat000002"
cat_dir = f"/eos/project-e/ep-nu/evilla/sn-pointing/{cat_name}"
pdf_path = "/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz"
ed_path = "/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras"

print(f"Testing scenario 2 on {cat_name}", flush=True)

# Import the actual script functions
print("Importing script functions...", flush=True)
t0 = time.time()
from scripts.run_cat000001_full_analysis import load_matched_cluster_images_3plane, run_scenario2_perfect_ct
print(f"Imported in {time.time()-t0:.2f}s", flush=True)

# Load PDF
print("Loading PDF...", flush=True)
t0 = time.time()
import numpy as np
from scipy.interpolate import RegularGridInterpolator
pdf_data = np.load(pdf_path)
pdf_interpolator = RegularGridInterpolator(
    (pdf_data['energy_bins'], pdf_data['cosine_bins']),
    pdf_data['pdf'],
    bounds_error=False,
    fill_value=1e-10
)
print(f"PDF loaded in {time.time()-t0:.2f}s", flush=True)

# Run scenario 2
print("Running scenario 2...", flush=True)
t0 = time.time()
result = run_scenario2_perfect_ct(cat_dir, cat_name, ed_path, pdf_interpolator, verbose=True)
print(f"Scenario 2 completed in {time.time()-t0:.2f}s", flush=True)
print(f"Angular error: {result['angular_error_deg']:.2f}°")
print("SUCCESS")
