#!/usr/bin/env bash
# condor wrapper: third pass (pdf-lookup x init-mode scan on the ORIGINAL products)
set -euo pipefail
export SNOP_SKIP_DEP_CHECKS=1
source /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/scripts/init.sh
cd /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline
export OMP_NUM_THREADS=1
SCRATCH=/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/product_effect_scratch
python3 python/ana/product_effect_replay.py --codescan --cat "$1" --out-dir "$SCRATCH/percat"
