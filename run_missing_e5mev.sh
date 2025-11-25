#!/bin/bash

# Script to process missing categories for perfect_ct_e_gt_5mev scenario
# Usage: ./run_missing_e5mev.sh [--max-files N] [--skip-files N]
#
# Options:
#   --max-files N   : Process at most N categories (default: all)
#   --skip-files N  : Skip first N categories (default: 0)
#
# Example parallel usage:
#   Terminal 1: ./run_missing_e5mev.sh --skip-files 0 --max-files 100
#   Terminal 2: ./run_missing_e5mev.sh --skip-files 100 --max-files 100
#   Terminal 3: ./run_missing_e5mev.sh --skip-files 200 --max-files 100

# Default values
MAX_FILES=-1
SKIP_FILES=0
CAT_LIST="missing_cats_e5mev.txt"

# Model and configuration paths (from json/pipeline.json)
ED_MODEL="/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras"
CT_MODEL="/eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras"
PDF_FILE="/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz"
BASE_PATH="/eos/project-e/ep-nu/evilla/sn-pointing"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --max-files)
            MAX_FILES="$2"
            shift 2
            ;;
        --skip-files)
            SKIP_FILES="$2"
            shift 2
            ;;
        --cat-list)
            CAT_LIST="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--max-files N] [--skip-files N] [--cat-list FILE]"
            exit 1
            ;;
    esac
done

# Check if category list exists
if [[ ! -f "$CAT_LIST" ]]; then
    echo "Error: Category list file '$CAT_LIST' not found!"
    exit 1
fi

# Count total categories in list
TOTAL_CATS=$(wc -l < "$CAT_LIST")
echo "Total categories in list: $TOTAL_CATS"
echo "Skip files: $SKIP_FILES"
echo "Max files: $MAX_FILES (negative means all remaining)"
echo ""

# Process categories
PROCESSED=0
SKIPPED=0

while IFS= read -r cat; do
    # Skip if we haven't reached skip count yet
    if [[ $SKIPPED -lt $SKIP_FILES ]]; then
        ((SKIPPED++))
        continue
    fi
    
    # Stop if we've reached max files
    if [[ $MAX_FILES -ge 0 ]] && [[ $PROCESSED -ge $MAX_FILES ]]; then
        echo "Reached max files limit ($MAX_FILES). Stopping."
        break
    fi
    
    # Set up paths for this category
    CAT_DIR="${BASE_PATH}/${cat}"
    
    echo "[$((PROCESSED + 1))] Processing $cat..."
    
    # Run the analysis script for this category with perfect_ct_e_gt_5mev scenario
    python scripts/run_cat_analysis_emcee_corrected.py \
        --cat-name "$cat" \
        --cat-dir "$CAT_DIR" \
        --ed-model "$ED_MODEL" \
        --ct-model "$CT_MODEL" \
        --pdf-file "$PDF_FILE" \
        --scenarios perfect_ct_e_gt_5mev \
        --nwalkers 10 \
        --nsteps 10000 \
        --discard 1000 \
        --use-eos-structure
    
    if [[ $? -eq 0 ]]; then
        echo "✓ Successfully processed $cat"
    else
        echo "✗ Failed to process $cat (exit code: $?)"
    fi
    
    ((PROCESSED++))
    echo ""
    
done < "$CAT_LIST"

echo "========================================"
echo "Processing complete!"
echo "Categories processed: $PROCESSED"
echo "Categories skipped: $SKIPPED"
echo "========================================"
