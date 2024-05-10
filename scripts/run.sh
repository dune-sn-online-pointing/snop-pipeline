#!bin/bash
# This script is used to run the pipeline
INPUT_JSON=/afs/cern.ch/work/d/dapullia/public/dune/data-selection-pipeline/json/pipeline/4_test.json
OUTPUT_FOLDER=/afs/cern.ch/work/d/dapullia/public/dune/data-selection-pipeline/output/4_test/

REPO_HOME=$(git rev-parse --show-toplevel)
echo "REPO_HOME: ${REPO_HOME}"

cd ${REPO_HOME}/app
# INPUT_JSON=/afs/cern.ch/work/d/dapullia/public/dune/data-selection-pipeline/json/mt-2files.json
# OUTPUT_FOLDER=/afs/cern.ch/work/d/dapullia/public/dune/data-selection-pipeline/output/mt-2files/
# python pipeline.py --input_json $INPUT_JSON --output_folder $OUTPUT_FOLDER

# INPUT_JSON=/afs/cern.ch/work/d/dapullia/public/dune/data-selection-pipeline/json/mt-random.json
# OUTPUT_FOLDER=/afs/cern.ch/work/d/dapullia/public/dune/data-selection-pipeline/output/mt-random/
# python pipeline.py --input_json $INPUT_JSON --output_folder $OUTPUT_FOLDER

# INPUT_JSON=/afs/cern.ch/work/d/dapullia/public/dune/data-selection-pipeline/json/mt-3files-cut80000.json
# OUTPUT_FOLDER=/afs/cern.ch/work/d/dapullia/public/dune/data-selection-pipeline/output/mt-3files-cut80000/
python pipeline.py --input_json $INPUT_JSON --output_folder $OUTPUT_FOLDER

cd ${REPO_HOME}/scripts
