# Python Code Description

This package implements the core SN online-pointing workflow: from sampled detector clusters to ML-based classification and direction reconstruction products, then summary metrics at burst and multi-burst level.

## Why this code exists (analysis goal)

At a high level, the pipeline uses trained ML models to extract directional information from supernova-burst-like samples:

- CT model (channel tagging) estimates whether each selected cluster is ES-like or CC-like.
- ED model predicts per-cluster angular/directional information for selected clusters.
- Burst-direction logic aggregates cluster-level directions into one reconstructed burst direction per burst.
- Batch reporting aggregates many bursts (CAT folders) into summary statistics and plots.

This is the code path that connects model inference to SN burst pointing performance metrics (angular error, cos(theta), omega68, etc.).

## Code layout

- `python/app/`: executable workflows
	- `pipeline.py`: single-run full chain (selection → volumes → CT → optional ED reco export → report)
	- `pipeline_batch.py`: multi-CAT orchestration + aggregate summaries + burst-direction report
	- `ed_inference.py`: ED model inference on selected clusters
	- `ed_mcmc.py`: per-cluster MCMC refinement based on ED outputs
- `python/lib/`: core processing utilities used by `pipeline.py`
	- `sample_loader.py`, `volume_creator.py`, `channel_tagger.py`, `metrics_tracker.py`
- `python/ana/`: analysis/aggregation/report logic
	- `report_generator.py`, `burst_direction.py`, `burst_direction_batch_report.py`, etc.

Most users run via `scripts/*.sh`; those wrappers set environment and invoke these Python entrypoints.

## Single-run full pipeline (`python/app/pipeline.py`)

### 1) Sample selection

`sample_loader.load_and_select_samples(...)`:

- Reads CC and ES NPZ files from configured folders/patterns.
- Selects by event counts (`n_cc_events`, `n_es_events`) and includes all clusters from selected events.
- Produces `images`, `metadata`, counts and selection summary artifacts.
- Optional `cc_vol_folder` / `es_vol_folder` parameters: when provided, the loader also records a `ct_vol_refs` list — one `(file_path, match_id)` tuple per cluster — pointing into the large-format CT volume image files (`cat_volume_images_*/X/*.npz`). These tuples are loaded lazily by the CT tagger (see §4) to avoid loading ~3 GB of volume data into RAM at once.

### 2) Track-selection stage (current behavior)

Current flow is pass-through (no separate model-based pre-selection yet): selected clusters are forwarded directly.

### 3) Volume creation

`volume_creator.py` supports two modes:

- `create_volumes_simple(...)`: test mode, repackages selected images/metadata.
- `create_volumes(...)`: calls `online-pointing-utils/python/create_volumes.py` to create proper volume payloads.

### 4) Channel tagging (CT model application)

`channel_tagger.tag_channels(...)`:

- Loads Keras model (`tf.keras.models.load_model(..., compile=False)`).
- **Input images**: the CT model was trained on large-format wire-plane volume images (208×1242 pixels), not the small cluster images (128×32) used by the ED model. The correct inputs come from the `cat_volume_images_*` directories — a separate data product.
- **Two inference paths**:
  - **`vol_refs` path (default for production)**: receives a list of `(file_path, match_id)` tuples from the sample loader. Loads each source file once and batches all clusters from it, keeping peak RAM usage low (~few hundred MB instead of ~3 GB).
  - **Pre-loaded path**: falls back to a pre-loaded image array when `vol_refs` is `None`.
- **Class index convention**: the CT model was trained with ES=0, CC=1. P(ES) is therefore taken from output index 0 for 2-class softmax, or `1 - output[:,0]` for single-sigmoid output.
- **Preprocessing**: raw ADC values only — no log1p or per-image normalization (matches legacy training).
- Applies configurable threshold to classify ES/CC; saves `predictions/channel_predictions.npz` and text metrics.
- Computes confusion matrix, accuracy, precision, recall, specificity, F1, ROC/AUC.

### 5) Run report

`ana.report_generator.generate_report(...)` builds PDF and metrics summary for the run.

## ED model path (`python/app/ed_inference.py` + `python/app/ed_mcmc.py`)

### ED inference

`ed_inference.py` takes:

- ED Keras model path,
- `volumes_npz` (`volumes` + optional `cluster_energy`, `true_direction`),
- `selection_npz` (`is_selected_cluster`, optional `tentative_dirs`).

It selects clusters by mask, runs model prediction, and writes `ed_inference.npz` containing:

- `cluster_idx`,
- `ed_raw`,
- optional aligned arrays (`energy`, `tentative_dirs`, `true_direction`).

### ED per-cluster MCMC refinement

`ed_mcmc.py` interprets `ed_raw` as angular-likelihood bins and runs Metropolis-Hastings per selected cluster around tentative directions.

Outputs include:

- `mean_direction`,
- `best_direction`,
- `chain_likes`.

## Burst-level direction aggregation (`python/ana/burst_direction.py`)

This is where cluster-level direction information is aggregated into one burst direction.

### Selection and direction inputs

`select_electrons_from_run(...)` loads run `volume_images/volumes.npz` metadata and applies:

- selection modes: `predicted-es`, `weighted-ct`, `true-es`, `all`,
- optional energy threshold (`min_energy_mev`),
- direction mode (`true` or `reco`).

**Selection mode details**:

- `predicted-es`: keeps only clusters where the CT model predicted ES (binary threshold applied).
- `true-es`: keeps only ground-truth ES clusters (for benchmark scenarios).
- `weighted-ct`: keeps **all** clusters; assigns each a weight equal to `P(ES)` from the CT model (`y_pred_proba`). No threshold is applied. Note: with a typical CC:ES ratio of ~10:1 in the full sample, CC events with low but non-zero P(ES) can collectively outweigh the ES signal — this mode works best when the CT model has high AUC.
- `all`: keeps all clusters with uniform weight.

`direction_mode` note: `"reco"` reads `predictions/reco_directions.npz` when available; falls back to true-electron vectors and labels this as `"true (fallback: reco unavailable)"`.

### Reco-direction persistence contract (v1)

When `neural_networks.electron_direction.enabled=true` in pipeline config, `pipeline.py` runs ED inference + MCMC and writes:

- `predictions/reco_directions.npz`

Contract keys:

- `reco_dirs`: `(N,3)` normalized reconstructed vectors
- `has_reco`: `(N,)` validity mask
- `cluster_idx`: `(N,)` row index mapping aligned to `volume_images/volumes.npz`
- `contract_version`: `v1`

The intended alignment is one row per cluster/volume in the run output, so burst selection modes (`predicted-es`, `weighted-ct`, `true-es`, `all`) can all use the same reco vector table safely.

### Per-burst reconstruction methods

`reconstruct_burst_direction(...)` uses one of two methods:

1. **Default emcee posterior aggregation**
	 - Parameters from `emcee_cfg`: `nwalkers`, `nsteps`, `discard`, `prior_type`, `random_seed`.
	 - **Prior** (controlled by `prior_type` config key):
		 - `"uniform"` (default): flat prior on the sphere. Walkers are initialized within ±45° of the weighted mean electron direction for fast convergence even when that mean is biased by CC contamination.
		 - `"gaussian_around_mean"`: Gaussian prior centered on the weighted mean electron direction. Only appropriate for pure-ES samples; with CC contamination the prior locks the posterior on the wrong direction.
	 - **Likelihood**: uses the energy-dependent `pdf(cos_theta_e | E)` lookup table from `data/cosine_energy_pdf.npz` when `pdf_path` is configured (method label `"emcee+pdf"`); falls back to angle-squared sum otherwise.
	 - Returns posterior samples, reconstructed direction (mean of post-burn-in flat chain), acceptance fraction, and derived angular uncertainty metrics.

2. **Fallback weighted-mean + bootstrap**
	 - Used when emcee is disabled/unavailable/fails.
	 - Point estimate: weighted mean direction.
	 - Uncertainty: bootstrap distribution of angular error; `omega68` from 68% quantile.

Returned burst-level metrics include:

- `single_pass_theta_deg`,
- `theta_samples_deg`,
- `omega68_deg`,
- `method`, `acceptance_fraction`.

## Multi-burst aggregation (`python/app/pipeline_batch.py` + `python/ana/burst_direction_batch_report.py`)

### Batch execution over CAT folders

`pipeline_batch.py`:

- discovers CAT folders,
- distributes requested total CC/ES events across CATs,
- generates per-CAT pipeline configs,
- runs single pipeline per CAT,
- collects per-CAT selected-event counts from `metrics.json`.

It writes batch-level outputs:

- aggregate JSON (`requested_totals`, `selected_totals`, per-cat rows),
- aggregate PNG (per-cat + cumulative selected events).

### Multi-burst direction report

If enabled, `pipeline_batch.py` calls `build_batch_report(...)`.

`burst_direction_batch_report.py` then:

- loads latest run per CAT,
- performs per-burst selection and reconstruction via `burst_direction.py`,
- computes per-burst direction metrics (`angular_error_deg`, `cos_theta`, `omega68_deg`, `theta/phi`, method, CT accuracy),
- aggregates burst-level distribution statistics (`median_error_deg`, `q68_error_deg`),
- writes:
	- PDF with per-burst error plot + summary table,
	- JSON payload with all burst rows and aggregate metrics.

This is the current code path for "aggregate over multiple bursts": it is an aggregation of per-burst reconstructed directions and uncertainties, not a single global direction fit across all bursts.

## Practical notes

- Default user entrypoints are wrappers in `scripts/`.
- Runtime behavior is JSON-driven (`json/*.json`) with workflow-specific sections.
- Model references/paths are maintained externally in `submodules/ml-pointing-tools/docs/BestModels.dat`.
