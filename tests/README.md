# Tests and Analysis Scripts

This directory contains test scripts, analysis tools, and workflow examples for the data selection pipeline.

## Contents

### Analysis Scripts

#### `analyze_ct_results.py`
Analyzes Channel Tagger (CT) model predictions and generates comprehensive metrics.

**Usage**:
```bash
python3 tests/analyze_ct_results.py <predictions.npz> [output_dir]
```

**Outputs**:
- ROC curve with AUC
- Precision-Recall curve
- Confusion matrix at threshold 0.5
- All saved in `ct_analysis.pdf`

**Requirements**:
- Input `.npz` must contain `y_true` and `y_pred_proba` arrays

---

### Workflow Scripts

#### `full_ct_ed_workflow.sh`
Complete end-to-end workflow demonstrating CT inference, analysis, ED inference, and MCMC refinement.

**Usage**:
```bash
# Edit paths in script header first
./tests/full_ct_ed_workflow.sh
```

**Steps performed**:
1. Channel Tagger inference on volumes
2. CT results analysis (ROC, PR, confusion matrix)
3. Electron Direction inference on MT-selected clusters
4. MCMC direction refinement
5. Summary report generation

**Output**: Time-stamped directory in `results/` with all artifacts

---

#### `run_ct_on_samples.sh`
Simple example runner for CT inference only.

**Usage**:
```bash
# Edit MODEL_PATH and VOLUMES_NPZ variables
./tests/run_ct_on_samples.sh
```

**Output**: `results/ct_predictions.npz`

---

#### `run_ed_mcmc.sh`
Example runner for ED inference followed by MCMC refinement.

**Usage**:
```bash
# Edit model and data paths
./tests/run_ed_mcmc.sh
```

**Output**: 
- `results/ed_inference_on_mt.npz` (ED model outputs)
- `results/ed_mcmc_results.npz` (MCMC refined directions)

---

## Quick Start Examples

### 1. Analyze existing CT predictions
```bash
python3 tests/analyze_ct_results.py \
  results/pipeline_run_001/ct_predictions.npz \
  results/pipeline_run_001/ct_analysis
```

### 2. Run standalone CT inference
```bash
python3 python/channel_tagger_runner.py \
  /path/to/ct_model.keras \
  results/volumes.npz \
  --out results/ct_pred.npz \
  --batch-size 64
```

### 3. Run ED + MCMC on MT results
```bash
# First: ED inference
python3 python/ed_inference_from_mt.py \
  /path/to/ed_model.keras \
  results/volumes.npz \
  results/mt_predictions.npz \
  --out results/ed_on_mt.npz

# Then: MCMC refinement
python3 python/ed_mcmc.py \
  results/ed_on_mt.npz \
  --out results/mcmc_refined.npz \
  --nsteps 3000
```

### 4. Complete workflow
```bash
./tests/full_ct_ed_workflow.sh
```

---

## Input Data Formats

### For CT Analysis (`analyze_ct_results.py`)
```python
# predictions.npz structure:
{
  'y_true': np.array,      # (N,) ground truth labels (0 or 1)
  'y_pred_proba': np.array # (N,) predicted probabilities [0, 1]
}
```

### For CT Inference (`channel_tagger_runner.py`)
```python
# volumes.npz structure:
{
  'volumes': np.array,     # (N, H, W, D, C) volume images
  'y_true': np.array       # (N,) optional ground truth
}
```

### For ED Inference (`ed_inference_from_mt.py`)
```python
# volumes.npz:
{
  'volumes': np.array,         # (N, ...) cluster volumes
  'cluster_energy': np.array   # (N,) optional energies
}

# mt_results.npz:
{
  'is_main_track': np.array,   # (N,) boolean mask
  'tentative_dirs': np.array   # (N, 3) or (M, 3) unit vectors
}
```

### For MCMC (`ed_mcmc.py`)
```python
# ed_inference_on_mt.npz (output of ed_inference_from_mt.py):
{
  'ed_raw': np.array,          # (M, K) angle-PDF bins
  'tentative_dirs': np.array,  # (M, 3) starting directions
  'cluster_idx': np.array,     # (M,) selected indices
  'energy': np.array,          # (M,) optional
  'angle_bin_centers': np.array # (K,) optional
}
```

---

## Output Formats

### CT Analysis Output
- **File**: `ct_analysis.pdf`
- **Content**: 3-panel figure (ROC, PR, Confusion Matrix)
- **Metrics**: Printed to stdout (AUC, accuracy, etc.)

### CT Inference Output
```python
# ct_predictions.npz:
{
  'y_pred_proba': np.array,  # (N,) predicted probabilities
  'y_true': np.array         # (N,) ground truth (if available)
}
```

### ED Inference Output
```python
# ed_inference_on_mt.npz:
{
  'cluster_idx': np.array,      # (M,) selected cluster indices
  'ed_raw': np.array,           # (M, K) model outputs
  'energy': np.array,           # (M,) optional
  'tentative_dirs': np.array    # (M, 3) optional
}
```

### MCMC Output
```python
# ed_mcmc_results.npz:
{
  'mean_direction': np.array,   # (M, 3) posterior mean dirs
  'best_direction': np.array,   # (M, 3) max likelihood dirs
  'chain_likes': np.array       # (M, nsteps) likelihood traces
}
```

---

## Performance Notes

| Operation | Typical Time | Memory |
|-----------|-------------|--------|
| CT inference (10k volumes) | ~30s | 2GB GPU |
| CT analysis | ~5s | <500MB |
| ED inference (1k clusters) | ~30s | 1GB GPU |
| MCMC per cluster (3000 steps) | 2-5s | <100MB |
| Full workflow (typical) | 15-60 min | 2-3GB |

---

## Troubleshooting

### Import errors
```bash
# Ensure environment is activated
source /cvmfs/sft.cern.ch/lcg/views/LCG_105/x86_64-el9-gcc13-opt/setup.sh
```

### CT predictions look wrong
- Check model path is correct
- Verify volume normalization matches training
- Inspect first few volumes: `volumes[0].min()`, `volumes[0].max()`

### MCMC chains not converging
- Increase `--nsteps` to 5000+
- Adjust `--proposal-scale` (try 0.05-0.15)
- Check `chain_likes` plots for mixing

### File not found errors
- Update paths in script headers
- Check that volumes and MT results exist
- Verify model paths on EOS

---

## Integration with Pipeline

These scripts can be run standalone or integrated into `pipeline_v2.py` by enabling flags in `pipeline_config_template.json`:

```json
{
  "neural_networks": {
    "channel_tagger": {
      "enabled": true,
      "model_path": "/path/to/ct_model.keras"
    },
    "electron_direction": {
      "enabled": true,
      "mcmc_enabled": true,
      "model_path": "/path/to/ed_model.keras"
    }
  }
}
```

See `docs/CT_ED_MCMC_GUIDE.md` for full pipeline integration details.

---

## Developer Notes

### Adding new analysis scripts
1. Place in `tests/` directory
2. Use argparse for CLI
3. Document inputs/outputs in docstring
4. Add example to this README

### Testing changes
```bash
# Run on small sample first
head -n 100 large_file.npz  # not valid for npz, use slicing instead
python3 -c "import numpy as np; d=np.load('large.npz'); np.savez('small.npz', **{k: v[:100] for k,v in d.items()})"
```

### Code style
- Follow PEP 8
- Use type hints where helpful
- Add `if __name__ == '__main__'` guard
- Include usage in docstring

---

## References

- Pipeline documentation: `../PIPELINE_V2_README.md`
- CT/ED guide: `../docs/CT_ED_MCMC_GUIDE.md`
- MT analysis: `../docs/MT_IDENTIFICATION_ANALYSIS.md`
