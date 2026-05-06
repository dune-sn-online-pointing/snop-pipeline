# JSON Configuration Files

This directory contains JSON configuration files for the SNOP pipeline analysis. **All analysis should be driven through JSON configs, not CLI arguments.**

## Configuration Files

### Scenario / Analysis Configurations
- **`six_scenarios.json`** — canonical catalog of the six benchmark scenarios (read by `run_small_sample_pipeline.sh` and `run_six_scenarios.sh`)
- **`scenario_analysis_config.json`** — input for `scenario_cos_theta_report.py`
- **`burst_direction_analysis_config.json`** — input for `burst_direction_batch_report.py`

### Pipeline Configurations
- **`example_config.json`** — main single-run pipeline template (source of truth for all scenario runs)
- **`full_pipeline_example_config.json`** — full pipeline with ED enabled
- **`pipeline_100cats_config.json`** — batch run over 100 CATs via `pipeline_batch.py`
- **`pipeline_batch_one_burst_test_config.json`** — single-CAT batch test config

### Component-Specific Configurations
- **`ct_only_example_config.json`** — CT inference only (`run_ct_inference.py`)
- **`ct_example_config.json`** — alternate CT config
- **`ed_only_example_config.json`** — ED inference only

### Test Configuration
- **`unit_test_config.json`** — offline unit test using synthetic data in `test/inputs/`; no EOS or model files required

## Key Configuration Sections

### Input Data Section
```json
{
  "input_data": {
    "cc_folder": "/path/to/cc/cluster/images/X",
    "es_folder": "/path/to/es/cluster/images/X",
    "cc_vol_folder": "/path/to/cat_volume_images_xxx",
    "es_vol_folder": "/path/to/cat_volume_images_xxx"
  }
}
```

`cc_vol_folder` / `es_vol_folder` (optional): paths to the large-format CT volume image directories (`cat_volume_images_*`). When set, the sample loader records `(file_path, match_id)` references for each selected cluster instead of loading the full volume array into RAM. The CT tagger then reads each source file exactly once during inference. **The CT model requires these large-format images (208×1242 pixels); the small cluster images used by the ED model are not valid CT inputs.**

In test/Condor runs, `test/run_small_sample_pipeline.sh` auto-detects `cat_volume_images_*/X` under the CAT directory and injects the path automatically.

### Analysis Section
```json
{
  "analysis": {
    "min_energy_mev": 3.0,            // Energy threshold for cluster selection
    "selection_mode": "predicted-es", // ES selection method (see below)
    "direction_mode": "reco",         // "reco" or "true"
    "emcee": {
      "enabled": true,
      "nwalkers": 128,
      "nsteps": 500,
      "discard": 100,
      "prior_type": "uniform",        // "uniform" (default) or "gaussian_around_mean"
      "random_seed": 42
    },
    "pdf_path": "data/cosine_energy_pdf.npz"
  }
}
```

**`selection_mode` values**:
- `"predicted-es"`: keep clusters where CT model predicted ES (binary, uses `channel_tagger_threshold`).
- `"true-es"`: keep only ground-truth ES clusters (benchmark only).
- `"weighted-ct"`: keep **all** clusters; weight each by `P(ES)` from CT model output. No threshold. With a typical CC:ES ratio of ~10:1, CT model discrimination quality determines whether this mode outperforms `predicted-es`.
- `"all"`: keep all clusters with uniform weight.

**`prior_type` values**:
- `"uniform"` (recommended): flat prior on sphere; walkers initialized ±45° around the weighted mean electron direction. Robust to CC contamination.
- `"gaussian_around_mean"`: Gaussian prior on the weighted mean direction. Biases the fit toward the mean electron direction, which is ~27° away from the true neutrino direction even for pure ES — use only for specific studies.

### Neural Networks Section
```json
{
  "neural_networks": {
    "channel_tagger": {
      "enabled": true,
      "model_path": "path/to/ct_model.keras",
      "threshold": 0.9
    },
    "electron_direction": {
      "enabled": true,
      "model_path": "path/to/ed_model.keras",
      "pdf_file": "path/to/cosine_energy_pdf.npz"
    }
  }
}
```

## Usage Examples

### Full single-run pipeline
```bash
python3 scripts/run_pipeline.py -j json/example_config.json
```

### Six-scenario production run
```bash
./scripts/run_six_scenarios.sh
# or for a single CAT test:
./test/run_small_sample_pipeline.sh
```

### Scenario cos(theta) report from existing outputs
```bash
python3 python/ana/scenario_cos_theta_report.py json/scenario_analysis_config.json
```

### Per-burst direction report from batch runs
```bash
python3 python/ana/burst_direction_batch_report.py \
  --runs-root output/runs \
  --output-pdf output/burst_report.pdf \
  --output-json output/burst_report.json \
  --selection-mode predicted-es
```

### Batch run over many CATs (single machine)
```bash
python3 python/app/pipeline_batch.py -j json/pipeline_100cats_config.json
```
