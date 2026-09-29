#!/usr/bin/env bash
# condor wrapper: threshold scan of the recommended combined-likelihood model
# (CMB2_..._accCC_ccl6) at t = 0.30..0.90 and 'all'. Offline, read-only on the
# campaign; results go to pipeline-dev/combo_study/threshold_scan/results.
# Uses a FROZEN copy of python/ (see FROZEN below) so it is immune to any
# concurrent edit of python/ana/burst_direction.py in the live checkout.
#   TAGS       comma list of arm tags from the arms json, or ALL
#   CATS       cat ranges, e.g. 2-31 or 901-930
#   NAME       output basename (unique per job)
#   ARMS       arms json (threshold-scan arms)
#   EVALCOL    per-event table of the cats to fit
#   SLICECATS  slice range used to measure R (default 673-900)
set -euo pipefail
export SNOP_SKIP_DEP_CHECKS=1
source /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/scripts/init.sh
cd /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline
CD=/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/combo_study
TD=/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/combo_study/threshold_scan
BD=/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/brems_study
FROZEN=/afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/condor/combo_tscan/frozen_python_20260929T011255
mkdir -p "$TD/results"
python3 /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/condor/combo_tscan/run_combo_gridfit_tscan_wrapper.py \
  --frozen "$FROZEN" \
  --arms "${ARMS:?ARMS not set}" \
  --tags "${TAGS:-ALL}" \
  --cats "${CATS:?CATS not set}" \
  --eval-collect "${EVALCOL:-$BD/collect_eval_slimonly.npz}" \
  --slice-collect "$BD/collect_673_900.npz" \
  --slice-cats "${SLICECATS:-673-900}" \
  --tables-dir "$CD/tables" \
  --out "$TD/results/${NAME:?NAME not set}.npz"
