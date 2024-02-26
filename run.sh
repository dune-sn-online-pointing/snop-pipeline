#!bin/bash
# This script is used to run the pipeline
INPUT_JSON=/afs/cern.ch/work/d/dapullia/public/dune/pipeline/settings/1_test.json
OUTPUT_FOLDER=/afs/cern.ch/work/d/dapullia/public/dune/pipeline/output/1_test/

python /afs/cern.ch/work/d/dapullia/public/dune/pipeline/pipeline.py --input_json $INPUT_JSON --output_folder $OUTPUT_FOLDER

