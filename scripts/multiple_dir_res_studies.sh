#!bin/bash

INPUT_JSON=/afs/cern.ch/work/d/dapullia/public/dune/data-selection-pipeline/json/multiple_dir_res_studies/supernova_spectrum.json
OUTPUT_FOLDER=/eos/user/d/dapullia/dune/data-selection-pipeline/multiple_dir_res_studies/test_single_3d_dir/prodmarley_nue_spectrum_clean_dune10kt_1x2x6_ES_customDirection-TPdump_standardHF_noiseless_MCtruth-tpstream-200events_thr30

# This script is used to run the pipeline
REPO_HOME=$(git rev-parse --show-toplevel)

export PYTHONPATH=$PYTHONPATH:$REPO_HOME/external_libs/lib/python3.9/site-packages

echo "REPO_HOME: ${REPO_HOME}"

cd ${REPO_HOME}/app
# python multiple_dir_res_studies.py --input_json $INPUT_JSON --output_folder $OUTPUT_FOLDER
python multiple_dir_res_studies.py --input_json $INPUT_JSON --output_folder /eos/user/d/dapullia/dune/data-selection-pipeline/multiple_dir_res_studies/supernova_spectrum/

# python multiple_dir_res_studies.py --input_json $INPUT_JSON --output_folder /eos/user/d/dapullia/dune/data-selection-pipeline/multiple_dir_res_studies/test_single_3d_dir/tpstream_2445/noU/ --delete_view U
# python multiple_dir_res_studies.py --input_json $INPUT_JSON --output_folder /eos/user/d/dapullia/dune/data-selection-pipeline/multiple_dir_res_studies/test_single_3d_dir/tpstream_2445/noV/ --delete_view V
# python multiple_dir_res_studies.py --input_json $INPUT_JSON --output_folder /eos/user/d/dapullia/dune/data-selection-pipeline/multiple_dir_res_studies/test_single_3d_dir/tpstream_2445/noX/ --delete_view X

cd ${REPO_HOME}/scripts
