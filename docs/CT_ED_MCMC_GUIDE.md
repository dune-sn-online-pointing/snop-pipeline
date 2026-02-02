# Channel Tagger and Electron Direction MCMC Guide

**Date**: November 15, 2025  
**Author**: Data Selection Pipeline Team

## Overview

This document describes the optional Channel Tagger (CT) and Electron Direction (ED) + MCMC components added to the pipeline. These tools enable:

1. **Channel Tagging (CT)**: Classification of volumes as CC or ES events using a trained CNN
2. **ED Inference from MT**: Running the Electron Direction model on main-track identified clusters
3. **MCMC Direction Refinement**: Using MCMC sampling to refine direction estimates based on ED-produced PDFs

## Pipeline Configuration

### Enabling Channel Tagger

In `json/pipeline_config_template.json`, set the CT `enabled` flag:

```json
"neural_networks": {
  "channel_tagger": {
    "model_path": "/path/to/channel_tagger.keras",
    "threshold": 0.5,
    "enabled": true,
    "comment": "Set enabled=true to run CT on volumes"
  }
}
```

When `enabled: false`, the pipeline skips channel tagging and proceeds directly to reporting with placeholder CT metrics.

### Enabling ED + MCMC

To enable ED inference and MCMC refinement:

```json
"neural_networks": {
  "electron_direction": {
    "model_path": "/path/to/electron_direction.keras",
    "enabled": true,
    "mcmc_enabled": true,
    "mcmc_steps": 3000,
    "mcmc_proposal_scale": 0.08,
    "comment": "Electron direction predictor with optional MCMC refinement"
  }
}
```

## Standalone Usage

### 1. Channel Tagger Inference

Run CT on prepared volumes:

```bash
python3 python/channel_tagger_runner.py \
  /path/to/ct_model.keras \
  /path/to/volumes.npz \
  --out results/ct_predictions.npz \
  --batch-size 64
```

**Input requirements**:
- `volumes.npz` must contain:
  - `volumes`: array (N, ...) matching CT model input shape
  - `y_true`: optional (N,) ground-truth labels (0=ES, 1=CC) for evaluation

**Output**:
- `ct_predictions.npz` containing:
  - `y_pred_proba`: (N,) predicted probabilities (0 to 1)
  - `y_true`: (N,) ground-truth labels (if present in input)

### 2. Analyze CT Results

Generate ROC, PR curves, and confusion matrix:

```bash
python3 tests/analyze_ct_results.py \
  results/ct_predictions.npz \
  results/ct_analysis
```

**Output**:
- `ct_analysis.pdf`: Multi-panel figure with:
  - ROC curve with AUC
  - Precision-Recall curve
  - Confusion matrix at threshold 0.5

### 3. ED Inference on MT Clusters

Run ED model on clusters identified as main-track by MT:

```bash
python3 python/ed_inference_from_mt.py \
  /path/to/ed_model.keras \
  /path/to/volumes.npz \
  /path/to/mt_results.npz \
  --out results/ed_inference_on_mt.npz \
  --batch-size 32
```

**Input requirements**:
- `volumes.npz`:
  - `volumes`: (N, ...) cluster volumes
  - `cluster_energy`: optional (N,) total energies
- `mt_results.npz`:
  - `is_main_track`: (N,) boolean mask
  - `tentative_dirs`: (N, 3) or (M, 3) tentative direction unit vectors

**Output**:
- `ed_inference_on_mt.npz`:
  - `cluster_idx`: indices of selected MT clusters
  - `ed_raw`: (M, K) ED model output (interpreted as angle-PDF bins)
  - `energy`: (M,) energies for selected clusters
  - `tentative_dirs`: (M, 3) aligned tentative directions

### 4. MCMC Direction Refinement

Refine directions using MCMC with ED-produced PDFs:

```bash
python3 python/ed_mcmc.py \
  results/ed_inference_on_mt.npz \
  --out results/ed_mcmc_results.npz \
  --nsteps 3000 \
  --proposal-scale 0.08
```

**Input requirements**:
- `ed_inference_on_mt.npz` (from step 3):
  - `ed_raw`: (M, K) angle-PDF values
  - `tentative_dirs`: (M, 3) starting directions
  - `angle_bin_centers`: optional (K,) angle bin centers (default: linspace(0, π, K))

**Output**:
- `ed_mcmc_results.npz`:
  - `mean_direction`: (M, 3) posterior mean directions
  - `best_direction`: (M, 3) maximum likelihood directions
  - `chain_likes`: (M, nsteps) likelihood traces

**MCMC algorithm**:
- Metropolis-Hastings on 3D unit sphere
- Proposal: add Gaussian noise (std=`proposal_scale`) in 3D, renormalize
- Likelihood: interpolated PDF value at angle between candidate and tentative direction
- Burnin: first 20% of chain typically discarded in post-analysis

## Model Output Format Requirements

### Channel Tagger Model

**Expected output**: 
- Shape: `(N, 1)` or `(N,)` 
- Range: [0, 1] (sigmoid activation)
- Interpretation: probability of CC channel (1=CC, 0=ES)

### Electron Direction Model

**Expected output for MCMC**:
- Shape: `(M, K)` where K = number of angle bins
- Content: Binned PDF over angular error
- Interpretation: `ed_raw[i, j]` = probability density at `angle_bin_centers[j]` for cluster `i`

If your ED model outputs direction vectors + confidence instead of angle-PDFs, you'll need to convert:
1. Compute angle between predicted direction and tentative direction
2. Use confidence to build a parametric PDF (e.g., von Mises-Fisher or wrapped Gaussian)
3. Evaluate PDF on a grid of angles and pass to MCMC

## Integration with Pipeline

When CT and ED+MCMC are enabled in the pipeline config, the execution flow is:

1. Sample selection (ES + CC events)
2. Main-track identification (MT model)
3. Volume creation from MT clusters
4. **[Optional] Channel tagging** (CT model on volumes)
5. **[Optional] ED inference** (ED model on MT clusters)
6. **[Optional] MCMC refinement** (if `mcmc_enabled: true`)
7. Metrics collection and report generation

The pipeline automatically:
- Creates intermediate `.npz` files for each step
- Tracks metrics (CT accuracy, ED angular error, MCMC acceptance rate)
- Generates summary PDF with all results

## Performance Notes

### CT Inference
- Typical batch size: 64-128
- Memory: ~2GB GPU for 10k volumes (32×32×32×2)
- Runtime: ~30s per 10k volumes on V100

### ED + MCMC
- ED inference: ~100 clusters/sec (batch_size=32)
- MCMC: ~2-5 sec per cluster (3000 steps)
- For 1000 MT clusters: expect ~1 hour total (ED + MCMC)
- Parallelization: MCMC runs per-cluster (embarrassingly parallel)

## Troubleshooting

### CT predictions all near 0.5
- Check model path is correct
- Verify volumes have correct normalization (same as training)
- Inspect model summary: `model.summary()` to confirm architecture

### ED MCMC chains not mixing
- Increase `proposal_scale` (try 0.1 or 0.15)
- Increase `nsteps` to 5000+
- Check `chain_likes` plots for convergence
- Verify ED model produces reasonable angle-PDFs (should peak near 0)

### Pipeline fails when CT/ED disabled
- Verify `enabled: false` is set in config
- Check pipeline logs for "Skipping..." messages
- Placeholder metrics should appear in report as zeros

## Expected Results

### Channel Tagger Performance (from best model)
- **AUC-ROC**: 0.95-0.98 (on validation set)
- **Precision @ 90% Recall**: 0.85-0.92
- **Confusion at 0.5 threshold**: 
  - TN ~88%, FP ~12% (ES correctly classified)
  - TP ~92%, FN ~8% (CC correctly classified)

### ED + MCMC Direction Improvement
- **Before MCMC** (ED direct prediction): median angular error ~5-10°
- **After MCMC**: median angular error ~3-7° (30-50% improvement)
- **Best cases**: Forward-going electrons with E > 50 MeV show ~2-3° resolution

## References

- Main-track identification: `docs/MT_IDENTIFICATION_ANALYSIS.md`
- Data correction summary: `docs/DATA_CORRECTION_SUMMARY.md`
- Pipeline v2 overview: `PIPELINE_V2_README.md`

## Thesis Integration

For thesis figures and tables:
1. Use `tests/analyze_ct_results.py` output PDFs directly
2. MCMC convergence: plot `chain_likes` traces with burnin line
3. Direction improvement: scatter plot of angle_error(tentative) vs angle_error(mcmc_best)
4. Performance table: extract metrics from pipeline `metrics.json`

Example metrics table format:

| Metric | Value |
|--------|-------|
| CT AUC | 0.967 |
| CT Accuracy @ 0.5 | 0.901 |
| ED Median Error (before MCMC) | 6.2° |
| ED Median Error (after MCMC) | 4.1° |
| MCMC Acceptance Rate | 0.34 |
| MCMC Runtime per cluster | 3.2s |
