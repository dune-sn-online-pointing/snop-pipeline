# Scripts

This folder contains utility/service scripts and user-facing Python entrypoints.

## Initialization (required)

Before running pipeline commands, source the environment once per shell:

```bash
source scripts/init.sh
```

`init.sh` is idempotent: if `INIT_DONE=true` is already set, re-sourcing does nothing.

## Service scripts

- `scripts/init.sh`
	- sets `PYTHONPATH`, `SNOP_OUTPUT_BASE`, external environment, and helper shell functions.
	- exports `INIT_DONE=true` when initialization is complete.
- `scripts/manage-submodules.sh`
	- helper for repository/submodule maintenance only (not part of physics workflow execution).

## Scripts to actually run

After initialization, run these Python entrypoints:

- Full single-run pipeline:
	- `python3 scripts/run_pipeline.py -j json/full_pipeline_example_config.json`
- Production six-scenario run:
	- `./scripts/run_six_scenarios.sh`
	- uses `json/six_scenarios.json` as the canonical scenario catalog
	- optional filter: `SCENARIO_NAMES=scenario_1_best_case,scenario_3_full_pipeline`
- CT-only:
	- `python3 scripts/run_ct_inference.py -j json/ct_only_example_config.json`
- ED-only:
	- `python3 scripts/run_ed_only.py -j json/ed_only_example_config.json`
- Batch over many CAT folders:
	- `python3 python/app/pipeline_batch.py -j json/pipeline_100cats_config.json`
- Legacy neutrino-energy aggregation:
	- `python3 python/ana/plot_neutrino_energy.py -j json/neutrino_energy_100cats_config.json`
- Scenario report:
	- `python3 python/ana/scenario_cos_theta_report.py --scenarios-root output/test_pipeline_scenarios --output-pdf output/test_pipeline_scenarios/scenario_cos_theta_report.pdf`

### CT volume image auto-detection

`test/run_small_sample_pipeline.sh` automatically looks for a `cat_volume_images_*/X` subfolder inside the CAT directory and, if found, injects `cc_vol_folder` and `es_vol_folder` into the pipeline config. No manual path configuration is needed for Condor runs; the volume folder must exist alongside the cluster-image folders.

## Condor submission

Condor submission tooling is not under `scripts/`.

To submit or manage Condor production, go to the `condor/` folder and use the scripts there (for example `condor/submit_all_cats.sh`).
