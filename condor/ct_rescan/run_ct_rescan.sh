#!/usr/bin/env bash
# condor wrapper: CT selection-rule re-scan on the r3 campaign's per-event outputs
# (offline, read-only on the campaign; results go to pipeline-dev/r3_rescan/results).
#   TAGS  comma list of variant tags from variants.json
#   CATS  cat ranges, e.g. 2-61 or 901-960
#   NAME  output basename, must be unique per (tags group, cat chunk)
set -euo pipefail
export SNOP_SKIP_DEP_CHECKS=1
source /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/scripts/init.sh
cd /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline
R3D=/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/r3_rescan
mkdir -p "$R3D/results"
python3 python/ana/ct_rescan_eval.py \
  --variants "${VARIANTS:-$R3D/variants.json}" \
  --tags "${TAGS:?TAGS not set}" \
  --cats "${CATS:?CATS not set}" \
  --out "$R3D/results/${NAME:?NAME not set}.npz"
