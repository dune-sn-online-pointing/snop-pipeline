#!/bin/bash
# Wrapper script to run EMCEE with 10 walkers, 10000 steps for perfect_ct_e_gt_5mev
# Args: space-separated list of category names (e.g., cat000001 cat000002 ...)

# Create directory structure for transferred files
mkdir -p scripts json

# Move transferred files to proper locations
if [ -f "run_cat_analysis_emcee_corrected.py" ]; then
    mv run_cat_analysis_emcee_corrected.py scripts/
fi
if [ -f "pipeline.json" ]; then
    mv pipeline.json json/
fi

# Load configuration from JSON
JSON_FILE="json/pipeline.json"
ED_MODEL=$(python3 -c "import json; print(json.load(open('$JSON_FILE'))['models']['ed_model'])")
CT_MODEL=$(python3 -c "import json; print(json.load(open('$JSON_FILE'))['models']['ct_model'])")
PDF_FILE=$(python3 -c "import json; print(json.load(open('$JSON_FILE'))['models']['pdf_file'])")
BASE_PATH=$(python3 -c "import json; print(json.load(open('$JSON_FILE'))['paths']['base_path'])")

# Process each category passed as argument
for CAT_NAME in "$@"; do
    if [ -z "$CAT_NAME" ]; then
        continue
    fi
    
    echo "========================================"
    echo "Processing $CAT_NAME with 10 walkers, 10000 steps"
    echo "========================================"
    
    CAT_DIR="${BASE_PATH}/${CAT_NAME}"
    
    # Run EMCEE analysis with new configuration
    python3 scripts/run_cat_analysis_emcee_corrected.py \
        --cat-name ${CAT_NAME} \
        --cat-dir ${CAT_DIR} \
        --ed-model ${ED_MODEL} \
        --ct-model ${CT_MODEL} \
        --pdf-file ${PDF_FILE} \
        --scenarios perfect_ct_e_gt_5mev \
        --nwalkers 10 \
        --nsteps 10000 \
        --discard 1000 \
        --use-eos-structure
    
    if [ $? -eq 0 ]; then
        echo "✓ Successfully processed $CAT_NAME"
    else
        echo "✗ Failed to process $CAT_NAME (exit code: $?)"
    fi
    echo ""
done

echo "========================================"
echo "All categories processed"
echo "========================================"
