#!/bin/bash

echo "*****************************************************************************"
echo "Running"
source /cvmfs/dunedaq.opensciencegrid.org/setup_dunedaq.sh 
setup_dbt latest dbt-setup-release fddaq-v4.2.0
export PYTHONPATH=/afs/cern.ch/user/h/hakins/private/matplotlib/lib/python3.10/site-packages/:$PYTHONPATH
source /cvmfs/sft.cern.ch/lcg/views/LCG_105/x86_64-el9-gcc13-opt/setup.sh
cd /afs/cern.ch/work/h/hakins/private/data-selection-pipeline/app/
cuts=(50000  60000  70000 80000  100000  120000  140000  150000  160000  180000  225000  250000  275000  300000  325000  350000  400000  500000)
for cut_model in "${cuts[@]}"; do
    for cut_data in "${cuts[@]}"; do
        python pipeline.py --input_json "/afs/cern.ch/work/h/hakins/private/data-selection-pipeline/json/pipeline_model_${cut_model}_on_cut_${cut_data}.json" --output_folder "/eos/user/h/hakins/dune/ML/mt_identifier/benchmark/model_${cut_model}_on_cut_${cut_data}"
    done
done
