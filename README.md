# SNOP Pipeline - Supernova Online Pointing Analysis

Refactored pipeline for supernova neutrino online pointing analysis using deep learning models for channel tagging and electron direction reconstruction.

## Quick Start

### 1. Environment Setup
```bash
source scripts/init.sh
```

### 2. Run Analysis with JSON Config
```bash
# Default catalog (json/eight_scenarios_v63_acceptance.json) on one CAT; scenario 8 = deployed
CAT=cat000623 PRODUCT_SUFFIX=_matchfix OUTPUT_ROOT=<eos dir>/cat000623 ./test/run_small_sample_pipeline.sh

# Legacy six-scenario run (json/six_scenarios.json)
./scripts/run_six_scenarios.sh

# Scenario analysis
python3 python/ana/scenario_cos_theta_report.py json/scenario_analysis_config.json

# Burst direction analysis  
python3 python/ana/burst_direction_batch_report.py json/burst_direction_analysis_config.json

# Full pipeline (selection + CT + ED only; the burst fit is scenario_cos_theta_report.py)
python3 scripts/run_pipeline.py -j json/example_config.json
```

### Default configuration (deployed 2026-09-30)
`json/example_config.json` is the **acceptance-normalised per-event mixture at CT v80 >= 0.30**
(ED v63, E >= 5 MeV, `selection_mode` `mixture-ct`, exact grid fit, `grid_n` 12000), identical to
`scenario_8_full_pipeline_acc_t030` of `json/eight_scenarios_v63_acceptance.json`, which is now the
default scenario catalog of the condor runners. It needs, next to the ED v63 model on EOS
(`.../neural-networks/electron_direction/three_plane_v63_matchfix_ft58_20260921_132520/`),
`cosine_energy_pdf_es_burstaxis_ct030_r3.npz`, `reco_acceptance_r3_v63_l6_ct030.npz` and
`ct_v80_calibration_r3slice_e5.npz`, plus the CT v80 model
(`.../neural-networks/channel_tagging/ct_volume_v80_20260706_224935/best_model.keras`).
The previous cut-based configuration (CT v80 >= 0.80, `predicted-es`, emcee) is still available as
`scenario_3_full_pipeline` of the same catalog. Details:
[docs/pipeline_fixes_2026-09.md](docs/pipeline_fixes_2026-09.md) ("Acceptance term deployed") and
[docs/json-options.md](docs/json-options.md).

## Configuration

All analysis is controlled through JSON configuration files in the `json/` directory:

### Key Configuration Files:
- **`scenario_analysis_config.json`** - Multi-scenario analysis
- **`burst_direction_analysis_config.json`** - Burst-level pointing analysis
- **`example_config.json`** - Main pipeline configuration template (the deployed default, see above)
- **`full_pipeline_example_config.json`** - Complete pipeline with all stages
- **`eight_scenarios_v63_acceptance.json`** - Default scenario catalog (scenario 8 = deployed, scenario 3 = previous cut-based)
- **`six_scenarios.json`** - Legacy six-scenario catalog (default of `scripts/run_six_scenarios.sh`)

### Important Parameters:
```json
{
  "analysis": {
    "min_energy_mev": 5.0,            // Energy threshold for cluster selection
    "selection_mode": "mixture-ct",   // per-event ES/CC mixture, hard CT cut in mixture.ct_hard_cut
    "direction_mode": "reco",         // Use reconstructed directions
    "pdf_path": ".../cosine_energy_pdf_es_burstaxis_ct030_r3.npz",   // ES table of the t=0.30 selection
    "acceptance_path": ".../reco_acceptance_r3_v63_l6_ct030.npz",    // acceptance of the same selection
    "mixture": { "ct_hard_cut": 0.3, "grid_n": 12000, "pi_mode": "fixed", "pi_fixed": 0.068421, ... },
    "emcee": { "prior_type": "uniform", "init_mode": "grid", ... }  // non-mixture scenarios only
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
├── json/            # JSON configuration files (eight_scenarios_v63_acceptance.json is the default catalog)
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
