#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

CT_CONFIG="${REPO_DIR}/json/ct_only_example_config.json"
ED_CONFIG="${REPO_DIR}/json/ed_only_example_config.json"
CT_MAX_VOLUMES="${CT_MAX_VOLUMES:-4}"

if [[ ! -f "${REPO_DIR}/output/ct_only_example/volumes_for_ed.npz" || ! -f "${REPO_DIR}/output/ct_only_example/selected_mask.npz" ]]; then
  "${REPO_DIR}/scripts/run_ct.sh" -j "${CT_CONFIG}" --skip-ct --max-volumes "${CT_MAX_VOLUMES}"
fi

"${REPO_DIR}/scripts/run_ed.sh" -j "${ED_CONFIG}"

for f in \
  "${REPO_DIR}/output/ed_only_example/ed_inference.npz" \
  "${REPO_DIR}/output/ed_only_example/ed_mcmc_results.npz"; do
  if [[ ! -f "${f}" ]]; then
    echo "ERROR: missing ED-only artifact: ${f}" >&2
    exit 1
  fi
done

echo "ED-only test completed successfully."
