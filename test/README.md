# Small-Sample Whole-Pipeline Scenarios

This folder contains a lightweight runner that executes the full pipeline for multiple scenarios and checks that each run produces a report.

All tests expect the runtime environment to be initialized via `scripts/init.sh` (the test scripts source it automatically).

## Script

- `run_small_sample_pipeline.sh`
- `run_ct_only_test.sh`
- `run_ed_only_test.sh`
- `run_batch_one_burst_test.sh`
- `run_scripts_smoke_test.sh`
- `run_all_tests.sh`
- `run_all_pipeline_tests.sh`

## Default Paths

- Samples: `/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples`
- Networks: `/eos/project-e/ep-nu/evilla/sn-online-pointing/neural-networks`
- Default category: `cat000001`
- Output root: `output/test_pipeline_scenarios`

## Run

```bash
./test/run_small_sample_pipeline.sh
```

CT-only test:

```bash
./test/run_ct_only_test.sh
```

ED-only test:

```bash
./test/run_ed_only_test.sh
```

Run all tests (recommended):

```bash
./test/run_all_tests.sh
```

Legacy alias (kept for compatibility):

```bash
./test/run_all_pipeline_tests.sh
```

Run one-burst batch pipeline test (includes default emcee burst-direction report):

```bash
./test/run_batch_one_burst_test.sh
```

Run script entrypoint smoke tests (help/CLI coverage for all non-batch wrappers and batch python entrypoint):

```bash
./test/run_scripts_smoke_test.sh
```

Scenarios are generated from `json/example_config.json` and now include six legacy-style comparisons:

- `scenario_1_best_case`: true ES selection + true electron direction (reference baseline)
- `scenario_2_perfect_ct`: true ES selection + reconstructed direction
- `scenario_3_full_pipeline`: CT-enabled predicted ES selection
- `scenario_4_weighted_ct`: CT-enabled weighted selection by CT probability
- `scenario_5_perfect_ct_e_gt_10mev`: true ES with energy threshold `E > 10 MeV`
- `scenario_6_perfect_ct_e_gt_5mev`: true ES with energy threshold `E > 5 MeV`

The runner also generates a combined scenario report:

- `output/test_pipeline_scenarios/scenario_cos_theta_report.pdf`
- `output/test_pipeline_scenarios/scenario_cos_theta_report.json`

This report shows `cos(theta)` distributions and the 68% quantile for each scenario.
By default, burst-direction aggregation now uses `emcee`; disable with `--no-emcee` when running `python/ana/scenario_cos_theta_report.py`.

You can regenerate the report without rerunning scenarios:

```bash
source scripts/init.sh
python3 python/ana/scenario_cos_theta_report.py \
	--scenarios-root output/test_pipeline_scenarios \
	--output-pdf output/test_pipeline_scenarios/scenario_cos_theta_report.pdf
```

## Common Overrides

```bash
CAT=cat000002 ./test/run_small_sample_pipeline.sh
```

```bash
BASE_CONFIG=/path/to/custom_base_config.json \
OUTPUT_ROOT=/tmp/pipeline_scenarios \
./test/run_small_sample_pipeline.sh
```