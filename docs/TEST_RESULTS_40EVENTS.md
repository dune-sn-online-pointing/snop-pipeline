# Pipeline Testing with 40-Event Samples

## Test Data

**CC Sample**: `/eos/home-e/evilla/dune/sn-tps/directions/prodmarley_nue_cc_gkvm_dune10kt_1x2x2_customDirection_cat1-triggerana_tree_1x2x2_simpleThr_production-40events/images_test_tick3_ch2_min2_tot3_e2p0`

**ES Sample**: `/eos/home-e/evilla/dune/sn-tps/directions/prodmarley_nue_es_gkvm_dune10kt_1x2x2_customDirection_cat1-triggerana_tree_1x2x2_simpleThr_production-40events/images_test_tick3_ch2_min2_tot3_e2p0`

## Test Results

### ✅ Sample Loader Test

**Command**: `python3 tests/test_sample_loader.py`

**Results**:
- Successfully loaded 10 CC events (11 clusters) and 5 ES events (5 clusters)
- Total: 16 clusters
- Image shape: (128, 16) - X-plane clusters
- Metadata shape: (16, 13) - All 13 columns present
- Metadata verification:
  * Column 2 (is_main_track): 1 MT, 15 non-MT ✓
  * Column 3 (is_es_interaction): Present in ES files ✓
  * Column 12 (plane_number): All X-plane (2) ✓

**Status**: ✅ **PASSED**

### ✅ MT Identification Logic Test

**Command**: `python3 tests/test_mt_identification.py`

**Results**:
- Loaded 27 CC + 10 ES clusters (37 total)
- Ground truth: 4 main tracks, 33 non-main tracks
- Mock predictions: 6 clusters selected as MT
- Performance metrics:
  * Accuracy: 89.2%
  * Precision: 0.500
  * Recall: 0.750
  * F1-Score: 0.600
  * AUC: 0.833
- Confusion matrix: TP=3, TN=30, FP=3, FN=1

**Status**: ✅ **PASSED** (with mock predictions)

## Data Format Validation

The test samples have the **same format** as the training data:

### NPZ File Structure
```python
{
    'images': np.array of shape (N, 128, 16),  # X-plane cluster images
    'metadata': np.array of shape (N, 13)      # 13-column metadata
}
```

### Metadata Columns (Verified)
0. event: ✓ Present
1. is_marley: ✓ Present
2. is_main_track: ✓ Present (correct for MT identification)
3. is_es_interaction: ✓ Present (correct for channel tagging)
4-6. true_pos (x,y,z): ✓ Present
7-9. true_particle_mom (px,py,pz): ✓ Present
10. cluster_energy: ✓ Present
11. true_particle_energy: ✓ Present
12. plane_number: ✓ Present (all X-plane = 2)

## Pipeline Components Validated

### ✅ Environment Setup
- LCG environment sourced correctly
- TensorFlow 2.16.1 available
- scikit-learn 1.2.2 available
- All Python modules import successfully

### ✅ Sample Loader Module
- Event-based selection works correctly
- Counts events (not clusters)
- Preserves all 13 metadata columns
- Handles both CC and ES folders
- Shuffling works properly

### ✅ MT Identification Module
- Truth extraction from column 2 works
- Metrics calculation functions correctly
- Confusion matrix computed properly
- ROC curve and AUC calculated
- Selection of MT clusters works

## Next Steps for Full Pipeline Test

### Wait for Trained Models

Currently running jobs:
- 10611179: CT v9 (resize)
- 10611180: CT v10 (crop)
- 10611405: ED v5 (single-plane)
- 10611610: ED v6 (3-plane with corrected direction)

Need to wait for MT identification training to complete.

### Alternative: Use Existing Model (If Available)

If there's a previously trained MT identification model, we can test with:

```bash
./scripts/run_pipeline.sh \
    --config json/test_40events.json \
    --n-cc-events 20 \
    --n-es-events 10 \
    --verbose
```

### Create Test Configuration

```json
{
  "input_data": {
    "cc_folder": "/eos/home-e/evilla/dune/sn-tps/directions/prodmarley_nue_cc_gkvm_dune10kt_1x2x2_customDirection_cat1-triggerana_tree_1x2x2_simpleThr_production-40events/images_test_tick3_ch2_min2_tot3_e2p0",
    "es_folder": "/eos/home-e/evilla/dune/sn-tps/directions/prodmarley_nue_es_gkvm_dune10kt_1x2x2_customDirection_cat1-triggerana_tree_1x2x2_simpleThr_production-40events/images_test_tick3_ch2_min2_tot3_e2p0",
    "file_pattern": "*_planeX.npz"
  },
  "sample_selection": {
    "n_cc_events": 30,
    "n_es_events": 10
  },
  "neural_networks": {
    "mt_identifier": {
      "model_path": "/path/to/mt_v7_model.keras",
      "threshold": 0.5
    }
  },
  "volume_creation": {
    "use_simple_mode": true
  },
  "output": {
    "base_folder": "/afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline/test_output_40events"
  }
}
```

## Summary

✅ **Data Format**: Confirmed compatible with pipeline
✅ **Sample Loader**: Working correctly with event-based selection
✅ **MT Logic**: Validated with mock predictions
✅ **Environment**: All dependencies available
✅ **Metadata**: All 13 columns present and correctly formatted

⏳ **Pending**: Trained MT identification model to test full inference

The pipeline is **ready to run** as soon as we have a trained MT identification model!
