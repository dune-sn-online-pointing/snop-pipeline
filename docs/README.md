# SNOP Pipeline - Supernova Online Pointing Analysis

Refactored pipeline for supernova neutrino online pointing analysis using deep learning models for channel tagging and electron direction reconstruction.

## Quick Start

### 1. Environment Setup
```bash
source scripts/init.sh
```

### 2. Run Analysis with JSON Config
```bash
# Production six-scenario run (shared catalog)
./scripts/run_six_scenarios.sh

# Scenario analysis
python3 python/ana/scenario_cos_theta_report.py json/scenario_analysis_config.json

# Burst direction analysis  
python3 python/ana/burst_direction_batch_report.py json/burst_direction_analysis_config.json

# Full pipeline
python3 scripts/run_pipeline.py json/example_config.json
```

## Configuration

All analysis is controlled through JSON configuration files in the `json/` directory:

### Key Configuration Files:
- **`scenario_analysis_config.json`** - Multi-scenario analysis
- **`burst_direction_analysis_config.json`** - Burst-level pointing analysis
- **`example_config.json`** - Main pipeline configuration template
- **`full_pipeline_example_config.json`** - Complete pipeline with all stages
- **`six_scenarios.json`** - Canonical six-scenario definition catalog used by scenario runners

### Important Parameters:
```json
{
  "analysis": {
    "min_energy_mev": 3.0,           // Energy threshold for cluster selection
    "selection_mode": "predicted-es", // ES selection method
    "direction_mode": "reco",         // Use reconstructed directions
    "emcee": {
      "nwalkers": 64,
      "nsteps": 2000,
      "discard": 400,
      "prior_kappa": 25.0,
      "likelihood_kappa": 25.0
    },
    "pdf_path": "data/cosine_energy_pdf.npz"  // PDF likelihood file
  }
}
```

## Directory Structure
```
├── scripts/         # Entrypoints: run_pipeline.py, run_six_scenarios.sh, init.sh
├── python/
│   ├── app/         # Executable workflows: pipeline.py, pipeline_batch.py, ed_inference.py
│   ├── lib/         # Core processing: sample_loader, volume_creator, channel_tagger, metrics_tracker
│   └── ana/         # Analysis & reports: scenario_cos_theta_report, burst_direction, aggregate_scenario_reports
├── condor/          # HTCondor submission: submit_all_cats.sh, submit_wait_aggregate.sh, run_cat_scenarios.sh
├── json/            # JSON configuration files (six_scenarios.json is the scenario catalog)
├── data/            # PDF likelihood data (cosine_energy_pdf.npz)
├── test/            # Test runners and run_small_sample_pipeline.sh (also used by Condor jobs)
├── docs/            # Detailed documentation
└── output/          # Generated results (gitignored)
```

## Pipeline Components

- **Channel Tagging (CT)**: ES vs CC classification using CNN
- **Electron Direction (ED)**: Direction reconstruction with MCMC refinement
- **PDF Likelihood**: Energy-cosine likelihood for improved MCMC sampling
- **Scenario Analysis**: Multi-scenario performance evaluation

## Documentation

- Scripts: [docs/scripts-description.md](docs/scripts-description.md)
- JSON options: [docs/json-options.md](docs/json-options.md)  
- Code description: [docs/code-description.md](docs/code-description.md)
