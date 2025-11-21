#!/bin/bash

# Condor wrapper for pipeline execution
# Usage: run_pipeline_wrapper.sh <cat_name> <step> [additional_args...]

echo "=== Pipeline Job Started ==="
echo "Cluster ID: ${_CONDOR_JOB_AD}"
echo "Hostname: $(hostname)"
echo "Date: $(date)"
echo "GPU Info:"
nvidia-smi -L 2>/dev/null || echo "No GPU available"
echo ""

# Setup environment
source /cvmfs/sft.cern.ch/lcg/views/LCG_106_cuda/x86_64-el9-gcc11-opt/setup.sh

# Navigate to working directory
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

CAT_NAME=$1
STEP=$2
shift 2

echo "Running pipeline step: $STEP for $CAT_NAME"
echo "Additional arguments: $@"
echo ""

# Run the appropriate step
case $STEP in
    "full")
        python3 scripts/run_pipeline.py \
            --cat "$CAT_NAME" \
            "$@"
        ;;
    "ct")
        python3 scripts/run_ct_inference.py "$@"
        ;;
    "ed")
        python3 python/ed_inference_from_mt.py "$@"
        ;;
    "mcmc")
        python3 python/mcmc_sampler.py "$@"
        ;;
    *)
        echo "ERROR: Unknown step '$STEP'"
        echo "Valid steps: full, ct, ed, mcmc"
        exit 1
        ;;
esac

EXIT_CODE=$?

echo ""
echo "=== Pipeline Job Finished ==="
echo "Exit code: $EXIT_CODE"
echo "Date: $(date)"

exit $EXIT_CODE
