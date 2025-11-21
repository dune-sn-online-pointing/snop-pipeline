#!/bin/bash
# Run pure ED analysis

CAT_DIR=$1
CAT_NAME=$2
ED_MODEL=$3
PDF_FILE=$4
OUTPUT_DIR=$5
WITH_MCMC=$6

echo "========================================="
echo "Pure ED Analysis (ES Main Track Only)"
echo "========================================="
echo "Category: $CAT_NAME"
echo "With MCMC: $WITH_MCMC"
echo "========================================="

source /cvmfs/sft.cern.ch/lcg/views/LCG_106/x86_64-centos7-gcc11-opt/setup.sh

cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

if [ "$WITH_MCMC" = "true" ]; then
    python3 scripts/run_pure_ed_analysis.py \
        --cat-dir "$CAT_DIR" \
        --cat-name "$CAT_NAME" \
        --ed-model "$ED_MODEL" \
        --energy-cosine-pdf "$PDF_FILE" \
        --output-dir "$OUTPUT_DIR" \
        --with-mcmc
else
    python3 scripts/run_pure_ed_analysis.py \
        --cat-dir "$CAT_DIR" \
        --cat-name "$CAT_NAME" \
        --ed-model "$ED_MODEL" \
        --energy-cosine-pdf "$PDF_FILE" \
        --output-dir "$OUTPUT_DIR"
fi

EXIT_CODE=$?

echo ""
echo "========================================="
echo "Job finished with exit code: $EXIT_CODE"
echo "========================================="

exit $EXIT_CODE
