#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${REPO_DIR}/scripts/init.sh"

python_entrypoints=(
  "${REPO_DIR}/scripts/run_ct_inference.py"
  "${REPO_DIR}/scripts/run_ed_only.py"
  "${REPO_DIR}/python/app/pipeline.py"
  "${REPO_DIR}/python/app/pipeline_batch.py"
  "${REPO_DIR}/python/ana/plot_neutrino_energy.py"
  "${REPO_DIR}/python/ana/scenario_cos_theta_report.py"
)

for script in "${python_entrypoints[@]}"; do
  if [[ ! -f "${script}" ]]; then
    echo "ERROR: missing entrypoint: ${script}" >&2
    exit 1
  fi
  python3 "${script}" -h >/dev/null
  echo "✓ help smoke test: ${script}"
done

echo "Script smoke tests completed successfully."
