#!/usr/bin/env bash
set -euo pipefail
source /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/scripts/init.sh
cd /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline
OUT=/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/v80_allfix_matchfix_dev/ed_diag
python3 python/ana/matchfix_ed_diagnosis.py --cat "$1" --out-dir "$OUT" --extra
