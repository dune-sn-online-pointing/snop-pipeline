#!/usr/bin/env bash
# condor wrapper: offline re-evaluation of mixture-ct variants on the kept per-event outputs of the dev run
set -euo pipefail
source /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/scripts/init.sh
cd /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline
OUT=/eos/user/e/evilla/dune/sn-tps/condor_scenarios_v80_mixture_dev
python3 python/ana/mixture_offline_variants.py --input-root $OUT \
  --pdf-es /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/data/cosine_energy_pdf.npz --pdf-cc /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/data/cosine_energy_pdf_cc.npz \
  --pdf-es-alt /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/data/cosine_energy_pdf_es_nu.npz --cc-map /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/data/cc_reco_direction_map.npz --calibration /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/data/ct_v80_calibration.npz --grid-n ${GRID_N:-41253} \
  --out-json $OUT/mixture_offline_variants${TAG:-}.json --out-md $OUT/mixture_offline_variants${TAG:-}.md ${ONLY:+--only $ONLY}
