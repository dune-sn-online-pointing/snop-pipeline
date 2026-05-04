# Tests

All test scripts source `scripts/init.sh` automatically.

## Offline unit test (no EOS, no model files)

Runs the complete code path — sample loading, volume creation, pipeline report, and burst-direction reconstruction — using small synthetic NPZ files committed in `test/inputs/mock_clusters/`. CT and ED inference are disabled; direction reconstruction uses true-ES selection with true electron directions.

```bash
./test/run_unit_test.sh
```

Inputs committed to git:
- `test/inputs/mock_clusters/cc_001_planeX.npz` — 10 synthetic CC events (30 clusters, 10×10 images)
- `test/inputs/mock_clusters/es_001_planeX.npz` — 6 synthetic ES events (12 clusters, 10×10 images)

Config: `json/unit_test_config.json`

## EOS-dependent tests

These require CERN EOS access and trained model files.

- **Full six-scenario pipeline** (primary integration test):
  ```bash
  ./test/run_small_sample_pipeline.sh
  ```
  Uses `json/example_config.json` + `json/six_scenarios.json`. Reads cluster images and CT volume images from EOS, runs all six legacy scenarios, and generates `output/test_pipeline_scenarios/scenario_cos_theta_report.pdf`.

  Run a subset by name:
  ```bash
  SCENARIO_NAMES=scenario_1_best_case,scenario_3_full_pipeline ./test/run_small_sample_pipeline.sh
  ```

  Common overrides:
  ```bash
  CAT=cat000002 TEST_N_CC=1000 TEST_N_ES=100 ./test/run_small_sample_pipeline.sh
  ```

- **CT-only test**: `./test/run_ct_only_test.sh`
- **One-burst batch test**: `./test/run_batch_one_burst_test.sh`
- **Script smoke tests** (help/CLI coverage, no EOS needed): `./test/run_scripts_smoke_test.sh`

## Run all tests

```bash
./test/run_all_tests.sh
```

Runs the offline unit test and smoke tests first, then the EOS-dependent suite.

Legacy alias: `./test/run_all_pipeline_tests.sh`

## Scenarios (six_scenarios.json)

| Name | Selection | Direction | Notes |
|---|---|---|---|
| `scenario_1_best_case` | true ES | true | Reference upper bound |
| `scenario_2_perfect_ct` | true ES | reco | CT replaced by truth |
| `scenario_3_full_pipeline` | CT threshold 0.9, E>5 MeV | reco | Full realistic chain |
| `scenario_4_weighted_ct` | all events, P(ES) weight | reco | No hard threshold |
| `scenario_5_perfect_ct_e_gt_10mev` | true ES, E>10 MeV | reco | High-energy cut |
| `scenario_6_perfect_ct_e_gt_5mev` | true ES, E>5 MeV | reco | Medium-energy cut |

## Output conventions

- `test/output/` — runtime artifacts (gitignored except `.gitkeep`)
- `test/inputs/` — static inputs versioned in git
