# Quick Reference: Data Selection Pipeline

**Last Updated:** November 14, 2025

## Key Results Summary

### Main Track Identification (200 CATs)
- **Accuracy:** 83.90%
- **Precision:** 54.34% (half of predictions are false positives)
- **Recall:** 96.03% (finds 96% of main tracks)
- **AUC-ROC:** 0.9214
- **Key Finding:** 85% of FPs are Marley secondary tracks, not background

### False Positive Analysis
| Type | Count | % of FPs | FP Rate |
|------|-------|----------|---------|
| Marley Secondary | 8,045 | 85.1% | 74.9% |
| Background | 1,409 | 14.9% | 3.6% |

**Interpretation:** Model correctly identifies Marley clusters but cannot distinguish main from secondary without energy information.

## Data Paths

### Corrected Production Data (November 2025)
```bash
ES: /eos/home-e/evilla/dune/sn-tps/prod_es/es_production_*_tick3_ch2_min2_tot3_e2p0/
CC: /eos/home-e/evilla/dune/sn-tps/prod_cc/cc_production_*_tick3_ch2_min2_tot3_e2p0/

# Subdirectories:
├── X/  (or U/, V/)           # Cluster images by plane
├── *_clusters/               # Cluster metadata
├── *_matched_clusters/       # Truth-matched
└── *_volume_images/          # 3D volumes
```

### Neural Network Models
```bash
MT v10:  /eos/user/e/evilla/dune/sn-tps/neural_networks/mt_identifier/v10_100k_nov13/
         └── mt_identifier_simple_cnn_20251113_145400/models/best_model.keras

ED v19:  /eos/user/e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_v19_lr_schedule_*/

CT:      Training in progress (v40-42)
```

## Analysis Tools

### Unified MT Analysis
```bash
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

# Run analysis on N CATs (33 events/CAT)
python3 tests/analyze_mt_full.py --n-cc 6600 --n-es 6600 --output mt_analysis_200cats

# Outputs:
# - results/mt_analysis_200cats/mt_analysis_200cats.pdf  (12-plot comprehensive analysis)
# - results/mt_analysis_200cats/predictions.npz          (all predictions + metadata)
# - results/mt_analysis_200cats/summary.txt              (text summary)
```

### Verification
```bash
cd /afs/cern.ch/work/e/evilla/private/dune/online-pointing-utils
source scripts/init.sh
python3 python/ana/verify_main_cluster.py

# Expected: ES ~86% with main (0% incorrect), CC ~93% with main (0% incorrect)
```

## Key Commands

### Environment Setup
```bash
# Data selection pipeline
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline
source scripts/init.sh

# Online pointing utils
cd /afs/cern.ch/work/e/evilla/private/dune/online-pointing-utils
source scripts/init.sh

# ML training
cd /afs/cern.ch/work/e/evilla/private/dune/refactor_ml
source ../scripts/init.sh
```

### Job Monitoring
```bash
# Check running jobs
condor_q

# Check specific jobs
condor_q -af ClusterId JobStatus RequestMemory RequestGPUs | grep <job_id>

# Check completed jobs
condor_history <job_id> -af ExitCode RemoteWallClockTime

# Check hold reason
condor_q -hold

# Release held job
condor_release <job_id>
```

### Training Jobs Status (Nov 14, 2025)
```bash
# Running
CT v40 (12876957): 10k samples, 40GB, running
CT v41 (12876958): 50k samples, 45GB, running

# Queued
CT v42 (12882049): 100k samples, 42GB
ED v28 (12882076): 50k samples, 24GB, lr=0.0001, clipnorm=5.0
ED v29 (12882077): 100k samples, 32GB, lr=0.0001, clipnorm=5.0
MT v10 (12882063): 50k samples, 21GB
MT v11 (12882064): 100k samples, 30GB

# Failed (fixed and resubmitted)
ED v26/v27: NaN loss at epoch 73 (learning rate too high)
CT v42 old: argmax bug (fixed)
MT v10/v11 old: json import bug (fixed)
```

## Important Findings

### Main Cluster Selection Bug (FIXED)
- **Issue:** C++ code used `true_energy` instead of `total_energy`
- **Impact:** 2-3% incorrect main cluster assignments
- **Resolution:** Fixed, regenerated all data (Nov 14, 2025)
- **Verification:** 0% incorrect in new data

### MT Model Limitations
- **Cannot distinguish Marley secondary from main tracks** (no energy in input images)
- **76% of Marley secondaries wrongly predicted as main**
- **Only 3.6% of background wrongly predicted as main** (background rejection excellent)
- **Potential fix:** Add energy as input feature or post-processing filter

### ED Training Issues
- **NaN loss at epoch 73** with lr=0.0005, clipnorm=1.0
- **Cause:** Gradient explosion in `tf.acos()` near singularities
- **Solution:** Lower lr (0.0001), higher clipnorm (5.0) in v28/v29

### CT Performance
- **Plateau at ~67% accuracy** across many architectures
- **Hypothesis:** Task is inherently difficult (ES/CC separation)
- **Corrected data:** Testing if main cluster fix improves performance

## Documentation

- **MT Analysis:** `docs/MT_IDENTIFICATION_ANALYSIS.md`
- **Data Correction:** `docs/DATA_CORRECTION_SUMMARY.md`
- **Pipeline README:** `PIPELINE_V2_README.md`
- **Test Results:** `TEST_RESULTS_40EVENTS.md`

## Contact & Notes

For thesis: Use documents in `docs/` for detailed explanations and tables. All numbers verified on 200 CATs (13,202 events) with corrected production data as of November 14, 2025.

**Key insight for thesis:** The "low" precision (54%) is not a failure - it's a fundamental limitation from using only spatial information. The model successfully learned to identify Marley-origin physics but needs energy information to distinguish primary from secondary particles. For burst selection pipelines, the high recall (96%) is more important than precision.
