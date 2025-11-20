#!/bin/bash
#
# Wrapper script to run all 5 scenarios for a single category
# Usage: ./run_single_cat.sh cat000001
#

set -e

CAT_NAME=$1

if [ -z "$CAT_NAME" ]; then
    echo "Error: Category name required"
    echo "Usage: $0 cat000001"
    exit 1
fi

# Paths
BASE_DIR="/eos/project-e/ep-nu/evilla/sn-pointing"
CAT_DIR="${BASE_DIR}/${CAT_NAME}"
PDF_PATH="/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz"
SCRIPT_DIR="/afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline"

echo "=========================================="
echo "Processing: $CAT_NAME"
echo "=========================================="
echo "Category directory: $CAT_DIR"
echo "PDF path: $PDF_PATH"
echo "Script directory: $SCRIPT_DIR"
echo ""

# Check if category directory exists
if [ ! -d "$CAT_DIR" ]; then
    echo "Error: Category directory not found: $CAT_DIR"
    exit 1
fi

# Check if cluster images directory exists
CLUSTER_DIR="${CAT_DIR}/${CAT_NAME}_cluster_images_tick3_ch2_min2_tot3_e3p0"
if [ ! -d "$CLUSTER_DIR" ]; then
    echo "Error: Cluster images directory not found: $CLUSTER_DIR"
    exit 1
fi

cd $SCRIPT_DIR

# Run all scenarios
echo ""
echo "Running all 5 scenarios..."
echo ""

python3 scripts/run_cat000001_full_analysis.py \
    --cat-dir "$CAT_DIR" \
    --cat-name "$CAT_NAME" \
    --pdf-path "$PDF_PATH" \
    --scenarios best_case perfect_ct full_pipeline weighted_linear weighted_squared \
    --use-eos-structure \
    --save-intermediate

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "SUCCESS: $CAT_NAME completed"
    echo "=========================================="
else
    echo ""
    echo "=========================================="
    echo "FAILED: $CAT_NAME (exit code: $EXIT_CODE)"
    echo "=========================================="
    exit $EXIT_CODE
fi
