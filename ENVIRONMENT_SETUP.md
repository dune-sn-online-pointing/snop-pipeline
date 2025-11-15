# Environment Setup for Data Selection Pipeline

## Overview

The data-selection-pipeline uses the same LCG environment as ml_for_pointing to ensure compatibility and access to all required packages.

## LCG Environment

**Version**: `LCG_106_cuda/x86_64-el9-gcc11-opt`

This provides:
- Python 3.11.9
- TensorFlow 2.16.1
- scikit-learn 1.2.2
- NumPy, Matplotlib, and other scientific packages
- CUDA support for GPU acceleration

## Setup Methods

### Method 1: Use the Wrapper Scripts (Recommended)

The easiest way to run the pipeline with the correct environment:

```bash
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

# Run the pipeline
./scripts/run_pipeline.sh --config json/example_config.json --verbose

# Run tests
./tests/run_tests.sh
```

These scripts automatically source the LCG environment.

### Method 2: Manual Environment Setup

If you need to run Python commands directly:

```bash
# Source the init script
source /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline/scripts/init.sh

# Now you can run Python scripts
python3 python/app/pipeline_v2.py --config json/example_config.json
```

### Method 3: Direct LCG Sourcing

For minimal setup:

```bash
source /cvmfs/sft.cern.ch/lcg/views/LCG_106_cuda/x86_64-el9-gcc11-opt/setup.sh
export PYTHONPATH="/afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline/python:$PYTHONPATH"
```

## Environment Variables Set by init.sh

When you source `scripts/init.sh`, the following variables are set:

- `REPO_DIR`: Repository root directory
- `PYTHON_DIR`: Python modules directory
- `JSON_DIR`: JSON configurations directory
- `SUBMODULES_DIR`: Submodules directory
- `PYTHONPATH`: Updated to include all necessary Python paths

## Available Packages

After sourcing the environment, you have access to:

### Core ML Libraries
- TensorFlow 2.16.1 (with Keras)
- NumPy
- scikit-learn 1.2.2

### Visualization
- Matplotlib
- (PDF generation via matplotlib backends)

### Data Processing
- NumPy arrays
- JSON handling (built-in)
- Subprocess management (built-in)

## Verification

To verify your environment is set up correctly:

```bash
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline
./tests/run_tests.sh
```

Expected output:
```
✓ Sourced LCG environment: LCG_106_cuda/x86_64-el9-gcc11-opt
✓ Added online-pointing-utils to PYTHONPATH
[SUCCESS] TensorFlow 2.16.1 is available
[SUCCESS] scikit-learn 1.2.2 is available
...
✓ All tests passed!
```

## Compatibility with ml_for_pointing

Both repositories use the **same LCG environment** (`LCG_106_cuda`), ensuring:

1. **Model Compatibility**: Models trained in ml_for_pointing can be loaded in data-selection-pipeline
2. **Same TensorFlow Version**: No serialization/deserialization issues
3. **Consistent Results**: Same numerical libraries ensure reproducible results
4. **Shared Dependencies**: Both can use the same trained models and data formats

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError`:
```bash
# Make sure you sourced the environment
source scripts/init.sh

# Check PYTHONPATH
echo $PYTHONPATH
```

### TensorFlow Not Found

If TensorFlow is not available:
```bash
# Verify LCG path
ls /cvmfs/sft.cern.ch/lcg/views/LCG_106_cuda/x86_64-el9-gcc11-opt/

# Try sourcing directly
source /cvmfs/sft.cern.ch/lcg/views/LCG_106_cuda/x86_64-el9-gcc11-opt/setup.sh
```

### CUDA Warnings

You may see warnings about CUDA not being available. This is normal on login nodes:
```
Could not find cuda drivers on your machine, GPU will not be used.
```

For GPU acceleration, run on nodes with GPU access (e.g., via HTCondor jobs).

## Running on HTCondor

When submitting jobs to HTCondor, make sure to source the environment in your job script:

```bash
#!/bin/bash
source /cvmfs/sft.cern.ch/lcg/views/LCG_106_cuda/x86_64-el9-gcc11-opt/setup.sh
export PYTHONPATH="/afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline/python:$PYTHONPATH"

python3 /path/to/pipeline_v2.py --config /path/to/config.json
```

## Notes

- The LCG environment is available on **LXPLUS** and other CERN computing resources via CVMFS
- No local installation or conda environment is needed
- The environment is centrally maintained by CERN IT
- Updates to the LCG release may require updating the `LCG_RELEASE` variable in `scripts/init.sh`
