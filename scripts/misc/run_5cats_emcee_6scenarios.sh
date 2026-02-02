#!/bin/bash
# Wrapper script to run emcee analysis for 5 cats with corrected 6 scenarios (0.8 CT threshold)

CAT1=$1
CAT2=$2
CAT3=$3
CAT4=$4
CAT5=$5

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
SCENARIOS=$(python3 -c "import json; print(' '.join(json.load(open('$JSON_FILE'))['scenarios']))")

# Process each cat
for CAT_NAME in "$CAT1" "$CAT2" "$CAT3" "$CAT4" "$CAT5"; do
    # Skip if empty (less than 5 cats in batch)
    [ -z "$CAT_NAME" ] && continue
    
    CAT_DIR="${BASE_PATH}/${CAT_NAME}"
    
    echo "========================================"
    echo "Processing ${CAT_NAME} - ONLY scenario 3 (full_pipeline) with CT threshold=0.8..."
    echo "Cat directory: ${CAT_DIR}"
    echo "========================================"
    
    python3 scripts/run_cat_analysis_emcee_corrected.py \
        --cat-name ${CAT_NAME} \
        --cat-dir ${CAT_DIR} \
        --ed-model ${ED_MODEL} \
        --ct-model ${CT_MODEL} \
        --pdf-file ${PDF_FILE} \
        --scenarios full_pipeline \
        --nwalkers 64 \
        --nsteps 2000 \
        --discard 400 \
        --use-eos-structure
    
    if [ $? -eq 0 ]; then
        echo "✓ ${CAT_NAME} completed successfully"
    else
        echo "✗ ${CAT_NAME} FAILED"
    fi
done

echo "========================================"
echo "Batch of 5 cats completed"
echo "========================================"
