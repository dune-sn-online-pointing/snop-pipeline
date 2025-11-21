#!/bin/bash

# Condor wrapper script for MT inference on cat000001

echo "Starting MT inference job"
echo "Cluster ID: $1"
echo "Process ID: $2"
echo "Hostname: $(hostname)"
echo "Date: $(date)"

# Setup environment (use same as training to avoid Keras version issues)
source /cvmfs/sft.cern.ch/lcg/views/LCG_106_cuda/x86_64-el9-gcc11-opt/setup.sh

# Navigate to working directory
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

# Run MT inference
python3 scripts/run_mt_inference.py \
    --model-path /eos/user/e/evilla/dune/sn-tps/neural_networks/mt_identifier/v10_100k_nov13/mt_identifier_simple_cnn_20251113_145400 \
    --data-dir /eos/project-e/ep-nu/public/sn-pointing/cat000001 \
    --output-dir results/mt_inference_cat000001_v10 \
    --plane X \
    --threshold 0.5 \
    --batch-size 256

echo "Job finished"
echo "Exit code: $?"
