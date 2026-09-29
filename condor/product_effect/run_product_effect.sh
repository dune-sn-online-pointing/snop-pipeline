#!/usr/bin/env bash
# condor wrapper: per-cat original-vs-regenerated product replay (read-only; writes only
# into the product_effect_scratch area)
set -euo pipefail
export SNOP_SKIP_DEP_CHECKS=1
source /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/scripts/init.sh
cd /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline
export TF_CPP_MIN_LOG_LEVEL=3
export OMP_NUM_THREADS=1
SCRATCH=/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/product_effect_scratch
python3 python/ana/product_effect_replay.py --cat "$1" \
    --out-dir "$SCRATCH/percat" --untar-dir "$SCRATCH/untar"
