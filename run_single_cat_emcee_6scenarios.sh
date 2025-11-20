#!/bin/bash
# Wrapper script to run emcee analysis for a single cat with corrected 6 scenarios

CAT_NAME=$1

# Load configuration from JSON
JSON_FILE="json/pipeline.json"
ED_MODEL=$(python3 -c "import json; print(json.load(open('$JSON_FILE'))['models']['ed_model'])")
CT_MODEL=$(python3 -c "import json; print(json.load(open('$JSON_FILE'))['models']['ct_model'])")
PDF_FILE=$(python3 -c "import json; print(json.load(open('$JSON_FILE'))['models']['pdf_file'])")
BASE_PATH=$(python3 -c "import json; print(json.load(open('$JSON_FILE'))['paths']['base_path'])")
SCENARIOS=$(python3 -c "import json; print(' '.join(json.load(open('$JSON_FILE'))['scenarios']))")

# Cat directory
CAT_DIR="${BASE_PATH}/${CAT_NAME}"

echo "Processing ${CAT_NAME} with 6 scenarios..."
echo "Cat directory: ${CAT_DIR}"

python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name ${CAT_NAME} \
    --cat-dir ${CAT_DIR} \
    --ed-model ${ED_MODEL} \
    --ct-model ${CT_MODEL} \
    --pdf-file ${PDF_FILE} \
    --scenarios ${SCENARIOS} \
    --nwalkers 64 \
    --nsteps 2000 \
    --discard 400 \
    --use-eos-structure

echo "✓ ${CAT_NAME} completed successfully"
