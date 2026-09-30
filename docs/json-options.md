# JSON Configuration Files

This directory contains JSON configuration files for the SNOP pipeline analysis. **All analysis should be driven through JSON configs, not CLI arguments.**

## Default configuration (deployed 2026-09-30)

`json/example_config.json` is the deployed configuration: the **acceptance-normalised per-event
mixture at CT v80 >= 0.30** (= `scenario_8_full_pipeline_acc_t030` of
`json/eight_scenarios_v63_acceptance.json`; model, files and validation in
[pipeline_fixes_2026-09.md](pipeline_fixes_2026-09.md), section "Acceptance term deployed").

| setting | value |
|---|---|
| CT model | `channel_tagging/ct_volume_v80_20260706_224935/best_model.keras`, hard cut 0.30 |
| ED model | `electron_direction/three_plane_v63_matchfix_ft58_20260921_132520/best_model.keras` |
| sample | 330 ES + 3300 CC generated events (`event_budget_mode` `generated`) |
| selection | `mixture-ct`, E >= 5 MeV, `ct_source` `ct`, `ct_hard_cut` 0.3 |
| fit | exact grid mixture posterior, `grid_n` 12000, `pdf_floor` 1e-4, flat CC, `pi_mode` fixed 0.068421 |

Files it needs on EOS, all under
`/eos/project-e/ep-nu/evilla/sn-online-pointing/neural-networks/electron_direction/three_plane_v63_matchfix_ft58_20260921_132520/`
(plus the two model files above):
`cosine_energy_pdf_es_burstaxis_ct030_r3.npz` (ES table of the t = 0.30 selection),
`reco_acceptance_r3_v63_l6_ct030.npz` (acceptance of the same selection),
`ct_v80_calibration_r3slice_e5.npz` (P(ES | CT score), threshold independent).
The ES table, the acceptance and the CT threshold belong to one selection and move together.

The default scenario catalog of `condor/run_cat_scenarios.sh`, `condor/submit_cat_range.sh` and
`test/run_small_sample_pipeline.sh` is `json/eight_scenarios_v63_acceptance.json`; every entry
carries its own `pdf_path`, so the six legacy scenarios are unchanged. The previous cut-based
configuration (CT v80 >= 0.80, `selection_mode` `predicted-es`, emcee) is still available as
`scenario_3_full_pipeline` of that catalog.

How the configuration is consumed:
- `scripts/run_pipeline.py` (= `python/app/pipeline.py`) runs sample selection, CT and ED only;
  it does not read the `analysis` block and has no fit stage.
- The burst fit is `python/ana/scenario_cos_theta_report.py`. It reads the `reporting` block of
  `<scenarios_root>/scenario_<name>/config.json` (selection mode, energy cut, CT threshold,
  `pdf_path`, `acceptance_path`, `mixture`) and only `emcee` / `pdf_path` from its own config.
  `test/run_small_sample_pipeline.sh` writes `reporting` from the catalog entry and copies `emcee`
  from the base config. `example_config.json` carries the same `reporting` block, so a single run
  written to `<root>/scenario_<name>/` with the config copied there as `config.json` can be fitted
  directly (see "Single run with the default fit" below).
- `mixture-ct` is always fitted by the grid, never by emcee. The `emcee` block (uniform prior,
  grid-seeded walkers) applies to the non-mixture scenarios and supplies `random_seed`.
- The CT model is `CT_MODEL` if set, else `neural_networks.channel_tagger.model_path` of the base
  config, else the legacy v52 model.
- Legacy catalogs (`six_scenarios.json`, `six_scenarios_v80.json`, ...) run with the default base
  config now get ED v63 and CT v80. To reproduce an older campaign pass its `BASE_CONFIG` and
  `CT_MODEL` explicitly (the v52/v58 settings are in git history of `example_config.json`).

## Configuration Files

### Scenario / Analysis Configurations
- **`eight_scenarios_v63_acceptance.json`** — default scenario catalog (condor runners and `run_small_sample_pipeline.sh`); scenario 8 is the deployed configuration, scenario 3 the previous cut-based one
- **`six_scenarios.json`** — legacy six-scenario catalog (still the default of `scripts/run_six_scenarios.sh`)
- **`scenario_analysis_config.json`** — input for `scenario_cos_theta_report.py`
- **`burst_direction_analysis_config.json`** — input for `burst_direction_batch_report.py`

### Pipeline Configurations
- **`example_config.json`** — main single-run pipeline template (source of truth for all scenario runs); the deployed configuration, see above
- **`full_pipeline_example_config.json`** — full pipeline with ED enabled
- **`pipeline_100cats_config.json`** — batch run over 100 CATs via `pipeline_batch.py`
- **`pipeline_batch_one_burst_test_config.json`** — single-CAT batch test config

### Component-Specific Configurations
- **`ct_only_example_config.json`** — CT inference only (`run_ct_inference.py`)
- **`ct_example_config.json`** — alternate CT config
- **`ed_only_example_config.json`** — ED inference only

### Test Configuration
- **`unit_test_config.json`** — offline unit test using synthetic data in `test/inputs/`; no EOS or model files required

## Key Configuration Sections

### Input Data Section
```json
{
  "input_data": {
    "cc_folder": "/path/to/cc/cluster/images/X",
    "es_folder": "/path/to/es/cluster/images/X",
    "cc_vol_folder": "/path/to/cat_volume_images_xxx",
    "es_vol_folder": "/path/to/cat_volume_images_xxx"
  }
}
```

`cc_vol_folder` / `es_vol_folder` (optional): paths to the large-format CT volume image directories (`cat_volume_images_*`). When set, the sample loader records `(file_path, match_id)` references for each selected cluster instead of loading the full volume array into RAM. The CT tagger then reads each source file exactly once during inference. **The CT model requires these large-format images (208×1242 pixels); the small cluster images used by the ED model are not valid CT inputs.**

In test/Condor runs, `test/run_small_sample_pipeline.sh` auto-detects `cat_volume_images_*/X` under the CAT directory and injects the path automatically.

### Analysis Section
```json
{
  "analysis": {
    "min_energy_mev": 5.0,            // Energy threshold for cluster selection
    "selection_mode": "mixture-ct",   // ES selection method (see below)
    "direction_mode": "reco",         // "reco" or "true"
    "pdf_path": ".../cosine_energy_pdf_es_burstaxis_ct030_r3.npz",
    "acceptance_path": ".../reco_acceptance_r3_v63_l6_ct030.npz",
    "mixture": { "calibration_path": ".../ct_v80_calibration_r3slice_e5.npz",
                 "pdf_es_path": ".../cosine_energy_pdf_es_burstaxis_ct030_r3.npz",
                 "cc_pdf_mode": "flat", "pi_mode": "fixed", "pi_fixed": 0.068421,
                 "ct_source": "ct", "ct_hard_cut": 0.3,
                 "acceptance_path": ".../reco_acceptance_r3_v63_l6_ct030.npz",
                 "grid_n": 12000, "pdf_floor": 0.0001 },
    "emcee": {
      "enabled": true,
      "nwalkers": 128,
      "nsteps": 500,
      "discard": 100,
      "prior_type": "uniform",        // "uniform" (default) or "gaussian_around_mean"
      "init_mode": "grid",            // grid-seeded walkers (code default)
      "random_seed": 42
    }
  }
}
```

**`selection_mode` values**:
- `"predicted-es"`: keep clusters where CT model predicted ES (binary, uses `channel_tagger_threshold`).
- `"true-es"`: keep only ground-truth ES clusters (benchmark only).
- `"weighted-ct"`: keep **all** clusters; weight each by `P(ES)` from CT model output. No threshold. With a typical CC:ES ratio of ~10:1, CT model discrimination quality determines whether this mode outperforms `predicted-es`.
- `"all"`: keep all clusters with uniform weight.
- `"mixture-ct"` (default): keep clusters with CT score >= `mixture.ct_hard_cut`; each gets a calibrated `P(ES)` and the burst direction is the exact grid posterior of the per-event ES/CC mixture, normalised by the detector acceptance (`acceptance_path`). Settings in `mixture`.

**`prior_type` values**:
- `"uniform"` (recommended): flat prior on sphere; walkers initialized ±45° around the weighted mean electron direction. Robust to CC contamination.
- `"gaussian_around_mean"`: Gaussian prior on the weighted mean direction. Biases the fit toward the mean electron direction, which is ~27° away from the true neutrino direction even for pure ES — use only for specific studies.

### Neural Networks Section
```json
{
  "neural_networks": {
    "channel_tagger": {
      "enabled": true,
      "model_path": "path/to/ct_model.keras",
      "threshold": 0.3
    },
    "electron_direction": {
      "enabled": true,
      "model_path": "path/to/ed_model.keras",
      "pdf_file": "path/to/cosine_energy_pdf.npz"
    }
  }
}
```

## Usage Examples

### Full single-run pipeline
```bash
python3 scripts/run_pipeline.py -j json/example_config.json
```

### Single run with the default fit
`run_pipeline.py` has no fit stage; run the report on the run directory. With `output.base_folder`
set to `<root>/scenario_default` and the config copied to `<root>/scenario_default/config.json`:
```bash
python3 scripts/run_pipeline.py -j my_config.json
python3 python/ana/scenario_cos_theta_report.py my_report.json   # analysis.scenarios_root = <root>, emcee from example_config.json
```

### Default catalog on one CAT (scenario runner)
```bash
CAT=cat000623 PRODUCT_SUFFIX=_matchfix SCENARIO_NAMES=scenario_8_full_pipeline_acc_t030 \
OUTPUT_ROOT=/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/<dir>/cat000623 \
./test/run_small_sample_pipeline.sh
```

### Six-scenario production run
```bash
./scripts/run_six_scenarios.sh
# or for a single CAT test:
./test/run_small_sample_pipeline.sh
```

### Scenario cos(theta) report from existing outputs
```bash
python3 python/ana/scenario_cos_theta_report.py json/scenario_analysis_config.json
```

### Per-burst direction report from batch runs
```bash
python3 python/ana/burst_direction_batch_report.py \
  --runs-root output/runs \
  --output-pdf output/burst_report.pdf \
  --output-json output/burst_report.json \
  --selection-mode predicted-es
```

### Batch run over many CATs (single machine)
```bash
python3 python/app/pipeline_batch.py -j json/pipeline_100cats_config.json
```
