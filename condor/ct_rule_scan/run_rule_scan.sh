#!/usr/bin/env bash
# condor wrapper: CT selection-rule scan (offline, read-only) on the kept
# per-event outputs of a scenario-7 dev run. One job = one rule group of one root.
#   ROOT  scenario output root (also where partials are written)
#   RULES comma list of rule ids / group ids
#   TAG   partial-file suffix, must be unique per (root, rule group)
set -euo pipefail
export SNOP_SKIP_DEP_CHECKS=1
source /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/scripts/init.sh
cd /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline
REPO=/afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline
ROOT="${ROOT:?ROOT not set}"
python3 python/ana/ct_selection_rule_scan.py \
  --input-root "$ROOT" \
  --pdf "$REPO/data/cosine_energy_pdf.npz" \
  --rules "${RULES:?RULES not set}" \
  --resume \
  --out-json "$ROOT/ct_selection_rule_scan_part_${TAG:?TAG not set}.json" \
  --out-md   "$ROOT/ct_selection_rule_scan_part_${TAG}.md"
