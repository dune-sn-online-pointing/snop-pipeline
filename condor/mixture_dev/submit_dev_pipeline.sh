#!/usr/bin/env bash
# Submit the seven-scenario pipeline (incl. scenario 7 mixture-ct) for the mixture dev subset,
# cats 623-672, on the regenerated products in the user-EOS fake-cat area.
# Per-event outputs are kept (PRUNE_SCENARIO_OUTPUTS=2), condor logs + job stdout go to AFS.
set -euo pipefail
SP=/afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline
cd "$SP"
FIRST="${FIRST:-623}" LAST="${LAST:-672}" \
OUTPUT_BASE="${OUTPUT_BASE:-/eos/user/e/evilla/dune/sn-tps/condor_scenarios_v80_mixture_dev}" \
SAMPLES_BASE="${SAMPLES_BASE:-/eos/user/e/evilla/dune/sn-tps/mixture_dev_samples}" \
SCENARIO_CATALOG="${SCENARIO_CATALOG:-$SP/json/seven_scenarios_v80_mixture.json}" \
CT_MODEL="${CT_MODEL:-/eos/project-e/ep-nu/evilla/sn-online-pointing/neural-networks/channel_tagging/ct_volume_v80_20260706_224935/best_model.keras}" \
REQUIRE_PRODUCTS=1 PRUNE_SCENARIO_OUTPUTS=2 CATS_PER_JOB="${CATS_PER_JOB:-2}" REQUEST_MEMORY="${REQUEST_MEMORY:-10 GB}" \
CONDOR_LOG_DIR="$SP/condor/logs/mixture_dev/pipeline" CONDOR_OUT_DIR="$SP/condor/logs/mixture_dev/pipeline" \
BATCH_TAG=mixdev-pipe \
./condor/submit_cat_range.sh
