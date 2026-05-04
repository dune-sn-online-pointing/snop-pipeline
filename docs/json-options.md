# JSON Configuration Files

This directory contains JSON configuration files for the SNOP pipeline analysis. **All analysis should be driven through JSON configs, not CLI arguments.**

## Configuration Files

### Analysis Configurations
- **`scenario_analysis_config.json`** - Multi-scenario analysis
- **`burst_direction_analysis_config.json`** - Burst-level pointing analysis

### Pipeline Configurations  
- **`example_config.json`** - Main pipeline configuration template
- **`full_pipeline_example_config.json`** - Complete pipeline configuration
- **`pipeline_100cats_config.json`** - Batch processing configuration

### Component-Specific Configurations
- **`ct_example_config.json`** - Channel tagging only
- **`ed_only_example_config.json`** - Electron direction only
- **`ct_only_example_config.json`** - CT-only analysis

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

### Scenario Analysis
```bash
python3 python/ana/scenario_cos_theta_report.py json/scenario_analysis_config.json
```

### Burst Direction Analysis
```bash  
python3 python/ana/burst_direction_batch_report.py json/burst_direction_analysis_config.json
```

### Full Pipeline
```bash
python3 scripts/run_pipeline.py json/example_config.json
```

## Parameter Notes

The `min_energy_mev` parameter controls the minimum energy threshold for cluster selection. A value of 3.0 MeV is recommended for optimal performance as it filters out low-energy clusters that can introduce noise in the reconstruction process.
