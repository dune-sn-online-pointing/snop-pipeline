# Python Code Description

The core code is split into two areas:

- `python/app/`: executable application entrypoints (pipeline, batch pipeline, ED inference, ED MCMC)
- `python/ana/`: reporting and analysis modules

Primary app entrypoints:

- `python/app/pipeline.py`: full single-run pipeline
- `python/app/pipeline_batch.py`: batch pipeline over many CAT folders
- `python/app/ed_inference.py`: ED inference on selected clusters
- `python/app/ed_mcmc.py`: MCMC refinement for ED outputs

Most users should run wrappers under `scripts/` and configure behavior through JSON files under `json/`.
