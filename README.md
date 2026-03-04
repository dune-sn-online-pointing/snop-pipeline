# snop-pipeline

This repository contains the SN online-pointing workflow for:

- selecting CC/ES samples,
- building cluster volumes,
- running channel tagging (CT),
- running electron-direction (ED) inference and optional MCMC refinement,
- generating per-run and scenario-level reports.

## How to run

Initialize environment once per shell:

- `source scripts/init.sh`

Then run workflows directly via Python entrypoints.

- Full pipeline: `python3 python/app/pipeline.py -j json/full_pipeline_example_config.json`
- CT only: `python3 scripts/run_ct_inference.py -j json/ct_only_example_config.json`
- ED only: `python3 scripts/run_ed_only.py -j json/ed_only_example_config.json`
- Legacy neutrino-energy aggregation: `python3 python/ana/plot_neutrino_energy.py -j json/neutrino_energy_100cats_config.json`
- Scenario report from existing runs: `python3 python/ana/scenario_cos_theta_report.py --scenarios-root output/test_pipeline_scenarios --output-pdf output/test_pipeline_scenarios/scenario_cos_theta_report.pdf`

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
