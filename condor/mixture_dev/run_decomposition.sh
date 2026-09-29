#!/usr/bin/env bash
# condor wrapper: (selection x sampler x lookup) decomposition of the scenario-3
# pointing resolution on the kept per-event outputs of the dev run.
set -euo pipefail
source /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/scripts/init.sh
cd /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline
OUT=/eos/user/e/evilla/dune/sn-tps/condor_scenarios_v80_mixture_dev
REPO=/afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline
python3 python/ana/mixture_offline_variants.py --input-root $OUT \
  --pdf-es $REPO/data/cosine_energy_pdf.npz \
  --pdf-cc $REPO/data/cosine_energy_pdf_cc.npz \
  --calibration $REPO/data/ct_v80_calibration.npz \
  --decompose \
  --decompose-selections "${SEL:-sc3,sc2}" \
  --decompose-samplers "${SAMPLERS:-emcee}" \
  --decompose-lookups "${LOOKUPS:-clipped,hole}" \
  --repeats "${REPEATS:-3}" --seed0 "${SEED0:-20260904}" --resume \
  --grid-n "${GRID_N:-41253}" \
  --out-json $OUT/lookup_sampler_decomposition${TAG:-}.json \
  --out-md   $OUT/lookup_sampler_decomposition${TAG:-}.md
