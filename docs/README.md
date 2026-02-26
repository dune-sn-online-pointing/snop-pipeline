# snop-pipeline

SN online-pointing pipeline with JSON-config-driven workflows.

## Model reference (authoritative)

Reference models are listed in:

- `submodules/ml-pointing-tools/docs/BestModels.dat`

Use this file as the source of truth for recommended CT/ED model versions and EOS paths.

## 1) Run the whole pipeline (single run)

```bash
./scripts/run_pipeline.sh -j json/full_pipeline_example_config.json
```

Core config toggles:

- `neural_networks.channel_tagger.enabled`
- `volume_creation.use_simple_mode`
- `sample_selection.n_cc_events`, `sample_selection.n_es_events`
- `input_data.cc_file_pattern`, `input_data.es_file_pattern`

## 2) Run CT only (JSON + wrapper script)

```bash
./scripts/run_ct.sh -j json/ct_only_example_config.json
```

`json/ct_only_example_config.json` contains model path, data directory, selected mapping,
output directory, optional ED export paths, and `skip_ct` mode.

## 2b) Run ED only (JSON + wrapper script)

```bash
./scripts/run_ed.sh -j json/ed_only_example_config.json
```

## 3) Run full pipeline over 100 CATs (3300 CC, 330 ES total)

```bash
./scripts/run_pipeline_batch.sh -j json/pipeline_100cats_config.json
```

This batch config distributes totals across the first 100 CAT folders and writes:

- per-CAT generated configs in `output/pipeline_100cats/generated_configs/`
- per-CAT runs in `output/pipeline_100cats/runs/`
- aggregate summary JSON + plot in `output/pipeline_100cats/`

## 4) Aggregate on the legacy neutrino-energy plot

```bash
./scripts/run_energy_plot.sh -j json/neutrino_energy_100cats_config.json
```

This uses `python/ana/plot_neutrino_energy.py` and produces the combined 100-CAT energy plot.

## 5) Run ED only

```bash
python3 python/app/ed_inference.py /path/to/ed_model volumes_for_ed.npz selected_mask.npz --out output/ed_inference.npz
python3 python/app/ed_mcmc.py output/ed_inference.npz --out output/ed_mcmc_results.npz
```

## 6) Run built-in scenario test (whole pipeline)

```bash
./test/run_small_sample_pipeline.sh
```

Run the aggregate test entrypoint (full + CT-only + ED-only):

```bash
./test/run_all_pipeline_tests.sh
```

Default outputs are written under `output/` via `SNOP_OUTPUT_BASE`.
JSON `output` fields still take precedence when explicitly set.

This now also runs six legacy-style scenarios (best-case, perfect-CT, full-pipeline, weighted-CT, and energy-threshold variants) and generates:

- `output/test_pipeline_scenarios/scenario_cos_theta_report.pdf`

The report compares scenarios using `cos(theta)` distributions and annotates the
68% quantile containment for each scenario.

Standalone report generation is also available:

```bash
./scripts/run_scenario_report.sh \
	--scenarios-root output/test_pipeline_scenarios \
	--output-pdf output/test_pipeline_scenarios/scenario_cos_theta_report.pdf
```

## More technical details

- `docs/code-description.md`
