# snop-pipeline

This repository contains the SN online-pointing workflow for:

- selecting CC/ES samples,
- building cluster volumes,
- running channel tagging (CT),
- running electron-direction (ED) inference and optional MCMC refinement,
- generating per-run and scenario-level reports.

## How to run

Run workflows through `scripts/` wrappers. They initialize the environment and call the underlying Python entrypoints.

- Full pipeline: `./scripts/run_pipeline.sh -j json/full_pipeline_example_config.json`
- CT only: `./scripts/run_ct.sh -j json/ct_only_example_config.json`
- ED only: `./scripts/run_ed.sh -j json/ed_only_example_config.json`
- Legacy neutrino-energy aggregation: `./scripts/run_energy_plot.sh -j json/neutrino_energy_100cats_config.json`
- Scenario report from existing runs: `./scripts/run_scenario_report.sh --scenarios-root output/test_pipeline_scenarios --output-pdf output/test_pipeline_scenarios/scenario_cos_theta_report.pdf`

Batch over many CAT folders is run from Python:

- `python3 python/app/pipeline_batch.py -j json/pipeline_100cats_config.json`

## Repository structure

- `scripts/`: user-facing commands (recommended entrypoints)
- `json/`: example JSON configurations
- `python/app/`: pipeline and inference executables
- `python/ana/`: analysis/report generation modules
- `test/`: test runners (`./test/run_all_tests.sh`)
- `docs/`: symlinked pointers to detailed READMEs

## Documentation

- Scripts: [docs/scripts-description.md](docs/scripts-description.md)
- JSON options: [docs/json-options.md](docs/json-options.md)
- Code description: [docs/code-description.md](docs/code-description.md)
