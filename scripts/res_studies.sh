#!bin/bash
# This script is used to run the pipeline
REPO_HOME=$(git rev-parse --show-toplevel)
echo "REPO_HOME: ${REPO_HOME}"

cd ${REPO_HOME}/app

INPUT_JSON=/afs/cern.ch/work/d/dapullia/public/dune/data-selection-pipeline/json/res_studies/flat_test.json
OUTPUT_FOLDER=/afs/cern.ch/work/d/dapullia/public/dune/data-selection-pipeline/output/res_studies/3d/
python res_studies.py --input_json $INPUT_JSON --output_folder $OUTPUT_FOLDER

cd ${REPO_HOME}/scripts
