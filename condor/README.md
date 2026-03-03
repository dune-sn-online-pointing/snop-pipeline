# Condor workflow: all-CAT scenario analysis

This folder provides a tidy HTCondor flow to run the 6-scenario pipeline test for many CATs and then aggregate results.

## 1) Submit all CAT jobs

```bash
./condor/submit_all_cats.sh
```

The script now auto-generates a submission file at runtime:

- `condor/submit_all_cats.generated.sub`
- with absolute repo/log/cat-list paths resolved from the current checkout
- with automatic user tagging in `batch_name`

This avoids hard-coded user directories in tracked `.sub` files and keeps the flow reproducible for any collaborator.

Useful overrides:

```bash
PIPELINE_BATCH_JSON=json/pipeline_100cats_config.json \
SAMPLES_BASE=/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples \
OUTPUT_BASE=output/condor_scenarios \
TEST_N_CC=1000 \
TEST_N_ES=100 \
./condor/submit_all_cats.sh
```

JSON defaults (used only when matching env var is not set):

- `pipeline_batch.samples.base_dir` → `SAMPLES_BASE`
- `pipeline_batch.samples.cat_glob` → `CAT_GLOB`
- `pipeline_batch.condor.output_base` → `OUTPUT_BASE` (optional key)

Dry-run (prepare queue without submitting):

```bash
DRY_RUN=1 CAT_LIMIT=5 ./condor/submit_all_cats.sh
```

Resource/flavour overrides:

```bash
REQUEST_CPUS=1 REQUEST_MEMORY="10 GB" REQUEST_DISK="6 GB" JOB_FLAVOUR="tomorrow" ./condor/submit_all_cats.sh
```

By default each job runs:

- `test/run_small_sample_pipeline.sh`
- with `CAT=<catNNNNNN>`
- writing to `OUTPUT_ROOT=<OUTPUT_BASE>/<catNNNNNN>`

This produces per-CAT artifacts including:

- `<OUTPUT_BASE>/<cat>/scenario_cos_theta_report.pdf`
- `<OUTPUT_BASE>/<cat>/scenario_cos_theta_report.json`

## 2) Aggregate all finished CAT reports

After jobs complete:

```bash
python3 python/ana/aggregate_scenario_reports.py \
  --input-root output/condor_scenarios \
  --output-pdf output/condor_scenarios/scenario_aggregate_allcats.pdf \
  --output-json output/condor_scenarios/scenario_aggregate_allcats.json
```

Or use helper:

```bash
./condor/aggregate_all_cats.sh
```

Helper overrides:

```bash
INPUT_ROOT=output/condor_scenarios \
OUTPUT_PDF=output/condor_scenarios/scenario_aggregate_allcats.pdf \
OUTPUT_JSON=output/condor_scenarios/scenario_aggregate_allcats.json \
./condor/aggregate_all_cats.sh
```

## Notes

- `test/run_small_sample_pipeline.sh` already defaults to memory-safe values (`TEST_N_CC=40`, `TEST_N_ES=8`).
- For larger statistics, raise `TEST_N_CC/TEST_N_ES` in submission environment.
- Aggregation script only uses CATs with valid `scenario_cos_theta_report.json` files.
