#!/bin/bash
# Condor wrapper script for ED+MCMC per-category processing

CAT_DIR=$1
CAT_NAME=$2
ED_MODEL=$3
PDF_FILE=$4
OUTPUT_DIR=$5

echo "========================================="
echo "ED+MCMC Per-Category Processing"
echo "========================================="
echo "Category: $CAT_NAME"
echo "Category directory: $CAT_DIR"
echo "ED model: $ED_MODEL"
echo "PDF file: $PDF_FILE"
echo "Output directory: $OUTPUT_DIR"
echo "========================================="
echo ""

# Setup CERN environment
source /cvmfs/sft.cern.ch/lcg/views/LCG_106_cuda/x86_64-el9-gcc13-opt/setup.sh

# Navigate to working directory
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

# Run the script
python3 scripts/run_ed_mcmc_single_cat.py \
    --cat-dir "$CAT_DIR" \
    --cat-name "$CAT_NAME" \
    --ed-model "$ED_MODEL" \
    --energy-cosine-pdf "$PDF_FILE" \
    --output-dir "$OUTPUT_DIR"

EXIT_CODE=$?

echo ""
echo "========================================="
echo "Job finished with exit code: $EXIT_CODE"
echo "========================================="

exit $EXIT_CODE
