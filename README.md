# snop-pipeline

Minimal entrypoints:

- Full pipeline: `./scripts/run_pipeline.sh -j json/full_pipeline_example_config.json`
- CT only: `./scripts/run_ct.sh -j json/ct_only_example_config.json`
- ED only: `./scripts/run_ed.sh -j json/ed_only_example_config.json`
- Batch pipeline over CAT folders: `python3 python/app/pipeline_batch.py -j json/pipeline_100cats_config.json`
- Legacy neutrino-energy aggregation: `./scripts/run_energy_plot.sh -j json/neutrino_energy_100cats_config.json`
- Scenario report from existing runs: `./scripts/run_scenario_report.sh --scenarios-root output/test_pipeline_scenarios --output-pdf output/test_pipeline_scenarios/scenario_cos_theta_report.pdf`

Tests:

- Run all tests: `./test/run_all_tests.sh`

More details:

- Scripts: [docs/scripts-description.md](docs/scripts-description.md)
- JSON configs: [docs/json-options.md](docs/json-options.md)
- Code description: [docs/code-description.md](docs/code-description.md)
