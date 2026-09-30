#!/usr/bin/env bash
# condor wrapper: supernova-distance study.  Replays scenario 8 (deployed) on the r3 campaign's
# stored per-event predictions after keeping a random fraction F = (10/d)^2 of the generated ES
# and CC events of each burst (replay_scenario_from_slim.py --keep-fraction).  All (F, seed)
# pairs of a chunk of cats go into ONE json (CHUNKOUT).  Read-only on the campaign.
#   CATS  FRACS  SEEDS  CHUNKOUT
set -euo pipefail
export SNOP_SKIP_DEP_CHECKS=1
REPO=/afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline
source "${REPO}/scripts/init.sh"
cd "${REPO}"
SCRATCH="${_CONDOR_SCRATCH_DIR:-${TMPDIR:-/tmp}}"
python3 python/ana/replay_scenario_from_slim.py \
  --catalog "${REPO}/json/eight_scenarios_v63_acceptance.json" \
  --scenario scenario_8_full_pipeline_acc_t030 \
  --source-scenario scenario_3_full_pipeline \
  --cats "${CATS:?}" \
  --campaign /eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-campaign/v63_matchfix_1000 \
  --out "$(dirname "${CHUNKOUT:?}")" \
  --scratch "${SCRATCH}" \
  --keep-fraction "${FRACS:?}" --trim-seed "${SEEDS:?}" \
  --chunk-out "${CHUNKOUT}"
