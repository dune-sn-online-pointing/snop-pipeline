#!/bin/bash
# Run filtered MCMC analysis on condor node

CAT_NAME=$1

echo "========================================="
echo "Filtered MCMC Analysis"
echo "Category: $CAT_NAME"
echo "========================================="

# Setup environment
source /cvmfs/sft.cern.ch/lcg/views/LCG_106/x86_64-centos7-gcc11-opt/setup.sh

# Navigate to working directory
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

# Run analysis
python3 scripts/visualize_existing_results.py \
    --cat "$CAT_NAME" \
    --output "results/mcmc_investigation_${CAT_NAME}_ES_filtered.pdf" \
    --filter-es \
    --filter-main

EXIT_CODE=$?

echo ""
echo "========================================="
echo "Job finished with exit code: $EXIT_CODE"
echo "========================================="

exit $EXIT_CODE
