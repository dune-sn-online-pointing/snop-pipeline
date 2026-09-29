#!/usr/bin/env bash
# condor wrapper: combined-likelihood grid fits (r3 CC map + brems ES acceptance).
# Offline, read-only on the campaign; results go to pipeline-dev/combo_study/results.
#   TAGS       comma list of arm tags from the arms json, or ALL
#   CATS       cat ranges, e.g. 2-31 or 901-930
#   NAME       output basename (unique per job)
#   ARMS       arms json (default combo_arms.json)
#   EVALCOL    per-event table of the cats to fit
#   SLICECATS  slice range used to measure R (default 673-900)
set -euo pipefail
export SNOP_SKIP_DEP_CHECKS=1
source /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/scripts/init.sh
cd /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline
CD=/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/combo_study
BD=/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/brems_study
mkdir -p "$CD/results"
python3 python/ana/combo_gridfit.py \
  --arms "${ARMS:-$CD/combo_arms.json}" \
  --tags "${TAGS:-ALL}" \
  --cats "${CATS:?CATS not set}" \
  --eval-collect "${EVALCOL:-$BD/collect_eval_slimonly.npz}" \
  --slice-collect "$BD/collect_673_900.npz" \
  --slice-cats "${SLICECATS:-673-900}" \
  --tables-dir "$CD/tables" \
  --out "$CD/results/${NAME:?NAME not set}.npz"
