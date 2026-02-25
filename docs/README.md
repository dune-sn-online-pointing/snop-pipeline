# SNOP Pipeline Docs

This folder is intentionally minimal and reflects only the current active flow.

## How to run

### 1) JSON-driven pipeline (recommended)

```bash
./scripts/run_pipeline.sh -j json/example_config.json
```

This executes `python/app/pipeline.py` using the provided JSON config.

### 2) Run a single CT step

```bash
python3 scripts/run_ct_inference.py --help
```

### 3) Run ED in batch on NPZ files

```bash
python3 scripts/run_ed_batch.py --help
```

### 4) Small EOS smoke test

```bash
./test/run_small_sample_pipeline.sh
```

Defaults are set for EOS sample and network locations:

- Samples: `/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples`
- Networks: `/eos/project-e/ep-nu/evilla/sn-online-pointing/neural-networks`

Outputs are written under `output/`.

## Notes

- Selection is handled directly during the sample-selection stage.
- The smoke test runs whole-pipeline scenarios and validates report generation.
- Runtime artifacts should remain untracked (`data/`, `results/`, `logs/`, `output/*`, `condor/*`, etc.).
- See `code-description.md` for a concise module-level map.
