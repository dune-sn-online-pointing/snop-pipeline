# snop-pipeline

SN online-pointing pipeline for three practical workflows:

- run the **whole pipeline** (selection + volumes + CT + report),
- run **CT only** on prepared volumes,
- run **ED only** (single file or batch glob), with optional MCMC refinement.

## What this code does

- **Whole pipeline (`python/app/pipeline.py`)**
  - Selects CC/ES samples,
  - builds volume payloads,
  - runs channel tagging (optional),
  - writes metrics and a PDF report.
- **CT standalone (`scripts/run_ct_inference.py`)**
  - Runs channel tagging on selected volumes.
  - Can export ED-ready NPZ artifacts.
- **ED standalone (`python/app/ed_inference.py`, `python/app/ed_mcmc.py`)**
  - Runs ED model on selected clusters.
  - Optional MCMC direction refinement.
- **ED batch (`scripts/run_ed_batch.py`)**
  - Runs ED directly on a folder/glob of NPZ files in one command.

## 1) Run the whole pipeline

Use the canonical example config:

```bash
./scripts/run_pipeline.sh -j json/example_config.json
```

The JSON config under `json/example_config.json` is the only tracked config template.

Key toggles inside the config:

- `neural_networks.channel_tagger.enabled`: enable/disable CT step.
- `volume_creation.use_simple_mode`: simple internal volume mode vs external utility mode.
- `sample_selection.n_cc_events`, `sample_selection.n_es_events`: run size.

## 2) Run CT only

Run with model:

```bash
python3 scripts/run_ct_inference.py \
  --data-dir /path/to/volume_images_or_cat_dir \
  --selected-mapping /path/to/selected_cluster_mapping.json \
  --output-dir output/ct_step \
  --plane X \
  --model-path /path/to/ct_model.keras
```

BYPASS model (I/O validation):

```bash
python3 scripts/run_ct_inference.py \
  --data-dir /path/to/volume_images_or_cat_dir \
  --selected-mapping /path/to/selected_cluster_mapping.json \
  --output-dir output/ct_step \
  --plane X \
  --skip-ct
```

Export ED artifacts directly from CT run:

```bash
python3 scripts/run_ct_inference.py \
  --data-dir /path/to/volume_images_or_cat_dir \
  --selected-mapping /path/to/selected_cluster_mapping.json \
  --output-dir output/ct_step \
  --plane X \
  --model-path /path/to/ct_model.keras \
  --ed-volumes-npz output/ct_step/volumes_for_ed.npz \
  --ed-selected-mask-npz output/ct_step/selected_mask.npz
```

## 3) Run ED only

Single ED run:

```bash
python3 python/app/ed_inference.py /path/to/ed_model.keras volumes_for_ed.npz selected_mask.npz --out output/ed_inference.npz
python3 python/app/ed_mcmc.py output/ed_inference.npz --out output/ed_mcmc_results.npz
```

## 4) Run ED on many NPZ files (one command)

```bash
python3 scripts/run_ed_batch.py /path/to/ed_model.keras \
  --input-glob 'output/my_samples/*.npz' \
  --output-dir output/ed_batch
```

With MCMC enabled:

```bash
python3 scripts/run_ed_batch.py /path/to/ed_model.keras \
  --input-glob 'output/my_samples/*.npz' \
  --output-dir output/ed_batch \
  --run-mcmc --mcmc-steps 2000 --mcmc-proposal-scale 0.08
```

## 5) Run built-in scenario test (whole pipeline)

```bash
./test/run_small_sample_pipeline.sh
```

This test executes multiple pipeline scenarios and checks report generation for each scenario.

## Code organization

- `python/app`: executable pipeline/application entrypoints
- `python/lib`: reusable pipeline libraries
- `python/ana`: analysis and visualization utilities

Detailed technical behavior is documented in [docs/code-description.md](docs/code-description.md).
