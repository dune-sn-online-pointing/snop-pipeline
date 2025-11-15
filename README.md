# Data-selection-pipeline

Pipeline for DUNE supernova burst event selection and neural network inference, including main-track identification, channel tagging, and electron direction reconstruction.

## Quick Links

- **Setup Guide**: [`ENVIRONMENT_SETUP.md`](ENVIRONMENT_SETUP.md)
- **Pipeline v2 Documentation**: [`PIPELINE_V2_README.md`](PIPELINE_V2_README.md)
- **Quick Start**: [`QUICKSTART.md`](QUICKSTART.md)
- **Channel Tagger & ED+MCMC Guide**: [`docs/CT_ED_MCMC_GUIDE.md`](docs/CT_ED_MCMC_GUIDE.md)

## Installation

```bash
git clone https://github.com/dune-sn-online-pointing/data-selection-pipeline.git
cd data-selection-pipeline
```

Update submodules (first time only):
```bash
./scripts/manage_submodules.sh --up
```

## Features

### Core Pipeline (Pipeline v2)
- **Sample Selection**: Automatic ES/CC event sampling from cluster images
- **Main-Track Identification**: CNN-based main track cluster identification
- **Volume Creation**: 3D volume generation around selected clusters
- **Channel Tagging** *(optional)*: CC/ES classification of volumes
- **Electron Direction** *(optional)*: Direction reconstruction with MCMC refinement
- **Automated Reporting**: PDF reports with metrics, plots, and analysis

### Optional Components
- **Channel Tagger (CT)**: Toggle via `channel_tagger.enabled` in config
- **Electron Direction + MCMC**: Refine directions using ED-produced PDFs and Metropolis-Hastings sampling
- **Standalone Analysis**: Tools for CT/ED/MCMC can run independently of pipeline

## Usage

### Run Complete Pipeline
```bash
python3 python/app/pipeline_v2.py json/pipeline_config.json
```

### Run Standalone CT Analysis
```bash
# CT inference
python3 python/channel_tagger_runner.py /path/to/ct_model.keras volumes.npz --out ct_pred.npz

# Analyze results
python3 tests/analyze_ct_results.py ct_pred.npz results/ct_analysis
```

### Run ED + MCMC Workflow
```bash
./tests/run_ed_mcmc.sh  # Edit paths in script first
```

See [`tests/README.md`](tests/README.md) for complete standalone examples.

## Configuration

Edit `json/pipeline_config_template.json`:

```json
{
  "neural_networks": {
    "main_track_identifier": {
      "model_path": "/path/to/mt_model.keras",
      "threshold": 0.5
    },
    "channel_tagger": {
      "enabled": true,
      "model_path": "/path/to/ct_model.keras",
      "threshold": 0.5
    },
    "electron_direction": {
      "enabled": true,
      "mcmc_enabled": true,
      "model_path": "/path/to/ed_model.keras"
    }
  }
}
```

## Documentation

| Document | Description |
|----------|-------------|
| [`PIPELINE_V2_README.md`](PIPELINE_V2_README.md) | Complete pipeline architecture and usage |
| [`docs/CT_ED_MCMC_GUIDE.md`](docs/CT_ED_MCMC_GUIDE.md) | Channel Tagger and ED+MCMC detailed guide |
| [`docs/MT_IDENTIFICATION_ANALYSIS.md`](docs/MT_IDENTIFICATION_ANALYSIS.md) | Main-track ID analysis and results |
| [`docs/DATA_CORRECTION_SUMMARY.md`](docs/DATA_CORRECTION_SUMMARY.md) | Data generation bug fixes and corrections |
| [`tests/README.md`](tests/README.md) | Analysis scripts and workflow examples |

## Project Structure

```
data-selection-pipeline/
├── python/
│   ├── app/
│   │   ├── pipeline_v2.py              # Main pipeline orchestrator
│   │   └── create_volumes.py           # Volume creation from clusters
│   ├── channel_tagger_runner.py        # CT standalone inference
│   ├── ed_inference_from_mt.py         # ED inference on MT clusters
│   └── ed_mcmc.py                      # MCMC direction refinement
├── tests/
│   ├── analyze_ct_results.py           # CT metrics and plots
│   ├── full_ct_ed_workflow.sh          # Complete workflow example
│   ├── run_ct_on_samples.sh            # CT quick runner
│   └── run_ed_mcmc.sh                  # ED+MCMC quick runner
├── json/
│   ├── pipeline_config_template.json   # Pipeline configuration template
│   └── volume_creation.json            # Volume creation parameters
├── docs/                               # Detailed documentation
├── results/                            # Pipeline outputs
└── submodules/
    └── online-pointing-utils/          # Volume creation utilities
```

## Requirements

- Python 3.9+
- TensorFlow 2.x (for neural network inference)
- NumPy, SciPy, Matplotlib, Seaborn, scikit-learn
- CERN CVMFS access (for lxplus environment)

See [`ENVIRONMENT_SETUP.md`](ENVIRONMENT_SETUP.md) for complete setup instructions.

## Contributing

When adding new features:
1. Update relevant documentation in `docs/`
2. Add examples to `tests/`
3. Update this README with new capabilities
4. Test on small sample before full dataset

## License

This project is part of the DUNE experiment's supernova neutrino program.
