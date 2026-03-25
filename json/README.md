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

### Analysis Section
```json
{
  "analysis": {
    "min_energy_mev": 3.0,           // Energy threshold for cluster selection
    "selection_mode": "predicted-es", // ES selection method
    "direction_mode": "reco",         // Use reconstructed directions
    "emcee": {
      "enabled": true,
      "nwalkers": 64,
      "nsteps": 2000,
      "discard": 400,
      "prior_kappa": 25.0,
      "likelihood_kappa": 25.0,
      "random_seed": 42
    },
    "pdf_path": "data/cosine_energy_pdf.npz"
  }
}
```

### Neural Networks Section
```json
{
  "neural_networks": {
    "electron_direction": {
      "enabled": true,
      "model_path": "path/to/ed_model.keras",
      "pdf_file": "path/to/cosine_energy_pdf.npz"  // PDF likelihood file
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
