#!/bin/bash
# Quick test job
source /cvmfs/sft.cern.ch/lcg/views/LCG_106/x86_64-centos7-gcc11-opt/setup.sh
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline
python3 scripts/check_data_structure.py
