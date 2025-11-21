#!/bin/bash
# Analyze ES/CC distribution

CAT_NAME=$1

source /cvmfs/sft.cern.ch/lcg/views/LCG_106/x86_64-centos7-gcc11-opt/setup.sh
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline
python3 scripts/analyze_es_cc_distribution.py --cat "$CAT_NAME"
