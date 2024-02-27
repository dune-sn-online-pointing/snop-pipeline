# Data-selection-pipeline

This repo contains some python scripts to run the whole pipeline for the SN pointing. 
It will call some functions to put together the SN pipeline and run the CNN over the data.

Install the repo with 
```bash
git clone https://github.com/dune-sn-online-pointing/data-selection-pipeline.git
cd data-selection-pipeline
```

The first time you install locally, you might need to update the submodules. 
You can do so with:
```bash
./scripts/manage_submodules.sh --up
```

You will probably need a python venv to run the code. ADD MORE INFO.
In `python` you will find some functions that are then called in `scripts/pipeline.py`.
See usage with `python scripts/pipeline.py -h`.

