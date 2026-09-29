#!/usr/bin/env bash
# condor wrapper: replay ONE scenario's ANALYSIS stage on the r3 campaign's stored per-event
# predictions (python/ana/replay_scenario_from_slim.py).  Read-only on the campaign; the only
# output is one json per cat under OUT.  The extracted tar members live in the worker's own
# scratch ($_CONDOR_SCRATCH_DIR) and are deleted per cat by the driver.
#   CATS      cat ranges/list, e.g. 2-26
#   OUT       output root (one <cat>/ subfolder per cat, one json inside)
#   CATALOG   scenario catalog (default json/seven_scenarios_v63_acceptance.json)
#   SCENARIO  catalog entry to replay (default scenario_7_full_pipeline_acc)
#   SRCSCEN   scenario folder inside the tar holding the predictions
#   CAMPAIGN  campaign root
set -euo pipefail
export SNOP_SKIP_DEP_CHECKS=1
REPO=/afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline
source "${REPO}/scripts/init.sh"
cd "${REPO}"
SCRATCH="${_CONDOR_SCRATCH_DIR:-${TMPDIR:-/tmp}}"
python3 python/ana/replay_scenario_from_slim.py \
  --catalog "${CATALOG:-${REPO}/json/seven_scenarios_v63_acceptance.json}" \
  --scenario "${SCENARIO:-scenario_7_full_pipeline_acc}" \
  --source-scenario "${SRCSCEN:-scenario_3_full_pipeline}" \
  --cats "${CATS:?CATS not set}" \
  --campaign "${CAMPAIGN:-/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-campaign/v63_matchfix_1000}" \
  --out "${OUT:?OUT not set}" \
  --scratch "${SCRATCH}"
