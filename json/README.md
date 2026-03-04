# JSON Options

This folder contains example configurations.

Main examples:

- `json/full_pipeline_example_config.json` for full pipeline runs
- `json/ct_only_example_config.json` for CT-only runs
- `json/ed_only_example_config.json` for ED-only single-file runs
- `json/ed_only_folder_example_config.json` for ED-only folder runs
- `json/pipeline_100cats_config.json` for multi-CAT batch runs
- `json/neutrino_energy_100cats_config.json` for legacy neutrino-energy aggregation plot

Recommended usage is to copy one of these files and edit paths and counts for your run.

## Available settings

Configs can be either top-level keys or nested under workflow sections (for example `ed_only.*`, `ct_inference.*`, `pipeline_batch.*`).

### Full pipeline (`full_pipeline_example_config.json` / `example_config.json`)

- `input_data.cc_folder`, `input_data.es_folder`: input dataset folders
- `input_data.cc_file_pattern`, `input_data.es_file_pattern`: NPZ matching patterns
- `sample_selection.n_cc_events`, `sample_selection.n_es_events`: event targets
- `volume_creation.use_simple_mode`: simple volume creation toggle
- `neural_networks.channel_tagger.enabled`: enable/disable CT step
- `neural_networks.channel_tagger.model_path`: CT model path
- `output.base_folder`: output root for pipeline runs

### CT-only (`ct_only_example_config.json`)

- `ct_inference.model_path`: CT model path
- `ct_inference.data_dir`: CAT folder or volume-images folder
- `ct_inference.selected_mapping`: optional selected-cluster mapping JSON
- `ct_inference.plane`: `U`, `V`, or `X`
- `ct_inference.batch_size`: CT inference batch size
- `ct_inference.max_volumes`: optional cap for quick runs/tests
- `ct_inference.skip_ct`: bypass CT model and export selected volumes directly
- `ct_inference.ed_volumes_npz`: optional ED-ready volumes output path
- `ct_inference.ed_selected_mask_npz`: optional ED-ready selection output path
- `ct_inference.output_dir`: CT-only output directory

### ED-only (`ed_only_example_config.json`, `ed_only_single_file_config.json`, `ed_only_folder_example_config.json`)

- `ed_only.ed_model`: ED model path
- `ed_only.volumes_npz`: single-file ED input (takes priority)
- `ed_only.input_folder`, `ed_only.input_glob`: folder mode inputs
- `ed_only.selection_npz`: optional explicit selection mask (auto-generated if `null`)
- `ed_only.batch_size`: ED inference batch size
- `ed_only.run_mcmc`: enable/disable MCMC refinement
- `ed_only.mcmc_steps`, `ed_only.mcmc_proposal_scale`: MCMC controls
- `ed_only.generate_report`: enable/disable ED PDF report
- `ed_only.report_pdf`: report output path (single-file mode)
- `ed_only.output_dir`: output directory

### Batch pipeline (`pipeline_100cats_config.json`, `pipeline_batch_one_burst_test_config.json`)

- `pipeline_batch.base_pipeline_config`: base full-pipeline config template
- `pipeline_batch.samples.base_dir`: CAT parent folder
- `pipeline_batch.samples.cat_glob`: CAT discovery pattern
- `pipeline_batch.samples.n_bursts` (or `n_cats`): number of CATs to process
- `pipeline_batch.samples.plane`: detector plane
- `pipeline_batch.selection.total_cc_events`, `pipeline_batch.selection.total_es_events`: totals to distribute
- `pipeline_batch.channel_tagger.enabled`, `pipeline_batch.channel_tagger.model_path`: CT options
- `pipeline_batch.volume_creation.use_simple_mode`: volume mode
- `pipeline_batch.execution.continue_on_error`: continue on CAT failures
- `pipeline_batch.output.base_dir`: output base folder
- `pipeline_batch.output.aggregate_json`, `pipeline_batch.output.aggregate_plot`: aggregate outputs
- `pipeline_batch.burst_direction_report.*`: per-burst direction report options (`enabled`, `use_emcee`, `output_pdf`, `output_json`, `selection_mode`, `direction_mode`, `min_energy_mev`, and emcee parameters)

### Legacy neutrino-energy aggregation (`neutrino_energy_100cats_config.json`)

- Input/output paths and plot controls used by `run_energy_plot.sh`
