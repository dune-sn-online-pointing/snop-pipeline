#!bin/bash
INPUT_JSON=/afs/cern.ch/work/d/dapullia/public/dune/data-selection-pipeline/json/res_studies/test_single_dir.json
OUTPUT_FOLDER=/eos/user/d/dapullia/dune/data-selection-pipeline/res_studies/test_single_dir/
# This script is used to run the pipeline
REPO_HOME=$(git rev-parse --show-toplevel)

export PYTHONPATH=$PYTHONPATH:$REPO_HOME/external_libs/lib/python3.9/site-packages

echo "REPO_HOME: ${REPO_HOME}"

cd ${REPO_HOME}/app
python res_studies.py --input_json $INPUT_JSON --output_folder $OUTPUT_FOLDER

cd ${REPO_HOME}/scripts
