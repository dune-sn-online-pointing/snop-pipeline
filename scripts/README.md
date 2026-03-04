# Scripts

This folder contains the command entrypoints for the pipeline workflows.

Use these wrappers:

- `./scripts/run_pipeline.sh -j json/full_pipeline_example_config.json`
- `./scripts/run_ct.sh -j json/ct_only_example_config.json`
- `./scripts/run_ed.sh -j json/ed_only_example_config.json`
- `./scripts/run_energy_plot.sh -j json/neutrino_energy_100cats_config.json`
- `./scripts/run_scenario_report.sh --scenarios-root output/test_pipeline_scenarios --output-pdf output/test_pipeline_scenarios/scenario_cos_theta_report.pdf`

For batch processing across many CAT folders, use:

- `python3 python/app/pipeline_batch.py -j json/pipeline_100cats_config.json`
