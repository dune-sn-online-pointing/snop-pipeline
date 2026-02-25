# snop-pipeline

SN online-pointing pipeline with three practical workflows:

- run the **whole pipeline** (selection + volumes + CT + report),
- run **CT only** on prepared volumes,
- run **ED only** (single file or batch glob), with optional MCMC refinement.

## Model reference (authoritative)

Reference models are listed in:

- `submodules/ml-pointing-tools/docs/BestModels.dat`

Use this file as the source of truth for recommended CT/ED model versions and EOS paths.
If an entry points to a legacy SavedModel directory, set `--model-path` to a compatible `.keras` checkpoint for Keras 3 environments.

## 1) Run the whole pipeline

```bash
./scripts/run_pipeline.sh -j json/example_config.json
```

Core config toggles:

- `neural_networks.channel_tagger.enabled`
- `volume_creation.use_simple_mode`
- `sample_selection.n_cc_events`, `sample_selection.n_es_events`
- `input_data.cc_file_pattern`, `input_data.es_file_pattern`

## 2) Run CT only

```bash
python3 scripts/run_ct_inference.py \
	--data-dir /path/to/volume_images_or_cat_dir \
	--selected-mapping /path/to/selected_cluster_mapping.json \
	--output-dir output/ct_step \
	--plane X \
	--model-path /path/to/ct_model
```

I/O validation mode (no model call):

```bash
python3 scripts/run_ct_inference.py \
	--data-dir /path/to/volume_images_or_cat_dir \
	--selected-mapping /path/to/selected_cluster_mapping.json \
	--output-dir output/ct_step \
	--plane X \
	--skip-ct
```

Export ED-ready artifacts from CT run:

```bash
python3 scripts/run_ct_inference.py \
	--data-dir /path/to/volume_images_or_cat_dir \
	--selected-mapping /path/to/selected_cluster_mapping.json \
	--output-dir output/ct_step \
	--plane X \
	--model-path /path/to/ct_model \
	--ed-volumes-npz output/ct_step/volumes_for_ed.npz \
	--ed-selected-mask-npz output/ct_step/selected_mask.npz
```

## 3) Run ED only

```bash
python3 python/app/ed_inference.py /path/to/ed_model volumes_for_ed.npz selected_mask.npz --out output/ed_inference.npz
python3 python/app/ed_mcmc.py output/ed_inference.npz --out output/ed_mcmc_results.npz
```

## 4) Run ED on many NPZ files (one command)

```bash
python3 scripts/run_ed_batch.py /path/to/ed_model \
	--input-glob 'output/my_samples/*.npz' \
	--output-dir output/ed_batch
```

With MCMC:

```bash
python3 scripts/run_ed_batch.py /path/to/ed_model \
	--input-glob 'output/my_samples/*.npz' \
	--output-dir output/ed_batch \
	--run-mcmc --mcmc-steps 2000 --mcmc-proposal-scale 0.08
```

## 5) Run built-in scenario test (whole pipeline)

```bash
./test/run_small_sample_pipeline.sh
```

This runs multiple whole-pipeline scenarios and verifies report generation.

## More technical details

- `docs/code-description.md`
