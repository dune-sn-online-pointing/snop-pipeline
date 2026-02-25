# Small-Sample Whole-Pipeline Scenarios

This folder contains a lightweight runner that executes the full pipeline for multiple scenarios and checks that each run produces a report.

## Script

- `run_small_sample_pipeline.sh`

## Default Paths

- Samples: `/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples`
- Networks: `/eos/project-e/ep-nu/evilla/sn-online-pointing/neural-networks`
- Default category: `cat000001`
- Output root: `output/test_pipeline_scenarios`

## Run

```bash
./test/run_small_sample_pipeline.sh
```

Scenarios are generated from `json/example_config.json` and vary event counts / channel tagging enable flag.

## Common Overrides

```bash
CAT=cat000002 ./test/run_small_sample_pipeline.sh
```

```bash
BASE_CONFIG=/path/to/custom_base_config.json \
OUTPUT_ROOT=/tmp/pipeline_scenarios \
./test/run_small_sample_pipeline.sh
```