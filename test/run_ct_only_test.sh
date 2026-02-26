#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

CONFIG="${REPO_DIR}/json/ct_only_example_config.json"
CT_MAX_VOLUMES="${CT_MAX_VOLUMES:-4}"

"${REPO_DIR}/scripts/run_ct.sh" -j "${CONFIG}" --max-volumes "${CT_MAX_VOLUMES}"

for f in \
  "${REPO_DIR}/output/ct_only_example/ct_predictions.csv" \
  "${REPO_DIR}/output/ct_only_example/ct_metrics.json" \
  "${REPO_DIR}/output/ct_only_example/volumes_for_ed.npz" \
  "${REPO_DIR}/output/ct_only_example/selected_mask.npz"; do
  if [[ ! -f "${f}" ]]; then
    echo "ERROR: missing CT-only artifact: ${f}" >&2
    exit 1
  fi
done

echo "CT-only test completed successfully."
