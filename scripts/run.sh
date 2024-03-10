#!bin/bash
# This script is used to run the pipeline
INPUT_JSON=/afs/cern.ch/work/d/dapullia/public/dune/data-selection-pipeline/json/2_test.json
OUTPUT_FOLDER=/afs/cern.ch/work/d/dapullia/public/dune/data-selection-pipeline/output/2_test/

REPO_HOME=$(git rev-parse --show-toplevel)
echo "REPO_HOME: ${REPO_HOME}"

cd ${REPO_HOME}/app
python pipeline.py --input_json $INPUT_JSON --output_folder $OUTPUT_FOLDER
cd ${REPO_HOME}/scripts
