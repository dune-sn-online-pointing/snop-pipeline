#!bin/bash
# This script is used to run the pipeline
INPUT_JSON=/afs/cern.ch/work/d/dapullia/public/dune/data-selection-pipeline/json/pipeline/new_image_full.json
OUTPUT_FOLDER=/eos/user/d/dapullia/dune/data-selection-pipeline/pipeline/

REPO_HOME=$(git rev-parse --show-toplevel)
echo "REPO_HOME: ${REPO_HOME}"

export PYTHONPATH=$PYTHONPATH:$REPO_HOME/external_libs/lib/python3.9/site-packages

cd ${REPO_HOME}/app

python pipeline.py --input_json $INPUT_JSON --output_folder $OUTPUT_FOLDER

cd ${REPO_HOME}/scripts
