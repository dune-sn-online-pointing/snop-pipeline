# Code Description

## Pipeline logic

Reference model versions and canonical EOS model paths are maintained in:

- `submodules/ml-pointing-tools/docs/BestModels.dat`

The main orchestrator is `python/app/pipeline.py` and executes a fixed sequence:

1. **Sample selection** (`python/lib/sample_loader.py`)
   - Reads CC and ES NPZ files from the configured folders.
   - Selects by **event count** (`n_cc_events`, `n_es_events`), not by cluster count.
   - Includes all clusters belonging to selected events.
   - Optional random shuffle controlled by `processing.shuffle` and `processing.random_seed`.

2. **Cluster selection stage** (in `pipeline.py`)
   - In the current implementation, this is a pass-through stage.
   - No separate model inference is run here; selected clusters are forwarded directly.

3. **Volume creation** (`python/lib/volume_creator.py`)
   - Two modes:
     - `volume_creation.use_simple_mode = true`: keeps selected arrays as simplified volume payloads.
     - `use_simple_mode = false`: calls `online-pointing-utils/python/create_volumes.py`.
   - Outputs array bundles used by downstream CT/ED.

4. **Channel tagging** (`python/lib/channel_tagger.py`)
   - Controlled by `neural_networks.channel_tagger.enabled`.
   - If enabled, loads Keras model from `neural_networks.channel_tagger.model_path`.
   - Predicts ES probability per volume and thresholds at `channel_tagger.threshold`.
   - Computes confusion matrix, accuracy, precision, recall, specificity, F1, ROC/AUC.
   - If disabled, pipeline emits a zeroed placeholder metrics block.

5. **Report generation** (`python/lib/report_generator.py`)
   - Builds a PDF report containing:
     - run summary,
     - step flow diagram,
     - CT performance plots and scalar metrics.

## Step toggles and configuration points

- `neural_networks.channel_tagger.enabled` toggles CT on/off.
- `volume_creation.use_simple_mode` toggles simple vs external volume builder.
- `sample_selection.n_cc_events` / `sample_selection.n_es_events` define sample size.
- `input_data.file_pattern` filters candidate NPZ files.
- `output.base_folder` defines output run root; `output.report_file` names PDF report.

## Standalone CT step

`scripts/run_ct_inference.py` runs CT independently from the full pipeline.

- Inputs:
  - volume NPZ source (`--data-dir`),
  - selected-cluster mapping JSON (`--selected-mapping`),
  - optional model (`--model-path`) unless `--skip-ct` is used.
- It can optionally export ED-ready payloads:
  - `--ed-volumes-npz` containing `volumes`, optional energy and true direction,
  - `--ed-selected-mask-npz` containing `is_selected_cluster` and `tentative_dirs`.

## ED inference and MCMC refinement

### ED inference (`python/app/ed_inference.py`)

- Inputs:
  - ED model path,
  - `volumes_npz` with `volumes` (and optional `cluster_energy`, `true_direction`),
  - `selection_npz` with `is_selected_cluster` and optional `tentative_dirs`.
- Behavior:
  - selects entries where `is_selected_cluster == True`,
  - runs Keras `model.predict` on selected volumes,
  - writes `ed_raw` plus aligned metadata arrays (`energy`, `tentative_dirs`, `true_direction` when available).

### MCMC (`python/app/ed_mcmc.py`)

- Purpose: refine direction hypothesis per selected cluster from ED angular PDFs.
- Assumption: `ed_raw[i]` approximates an angular likelihood/PDF over error angle to tentative direction.
- If `angle_bin_centers` is absent, bins are assumed uniformly in $[0, \pi]$.
- Proposal model (Metropolis-Hastings):
  - start from tentative direction,
  - add isotropic Gaussian perturbation in 3D,
  - renormalize to unit vector,
  - accept with ratio $\min(1, \mathcal{L}_{prop}/\mathcal{L}_{cur})$.
- Outputs:
  - `mean_direction`, `best_direction` (max-likelihood sample), `chain_likes`.

## One-command batch ED

`scripts/run_ed_batch.py` runs ED directly on many NPZ files from a folder/glob.

- Accepts `--input-glob` (e.g. `output/my_volumes/*.npz`).
- Supports NPZ files containing either `volumes` or `images`.
- Builds selection mask automatically (`is_selected_cluster=True` for all entries).
- Derives `tentative_dirs` from `metadata.main_track_momentum_{x,y,z}` if present, or uses `tentative_dirs` key directly.
- Optional `--run-mcmc` executes MCMC per file when tentative directions are available.
- Produces per-input output folders with `ed_inference.npz` and optional `ed_mcmc_results.npz`.

## Main generated artifacts per run

- `config_used.json`: exact config snapshot used for reproducibility.
- `metrics.json`: step-wise scalar metrics and run timing.
- `predictions/ct_predictions.csv`: per-volume CT outputs.
- `predictions/ct_metrics.json`: CT aggregate metrics.
- `pipeline_report.pdf`: report with summary, flow, and CT diagnostics.
