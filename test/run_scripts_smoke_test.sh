#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

scripts=(
  "${REPO_DIR}/scripts/run_pipeline.sh"
  "${REPO_DIR}/scripts/run_ct.sh"
  "${REPO_DIR}/scripts/run_ed.sh"
  "${REPO_DIR}/scripts/run_energy_plot.sh"
  "${REPO_DIR}/scripts/run_scenario_report.sh"
)

for script in "${scripts[@]}"; do
  if [[ ! -x "${script}" ]]; then
    echo "ERROR: script is not executable: ${script}" >&2
    exit 1
  fi
  "${script}" -h >/dev/null
  echo "✓ help smoke test: ${script}"
done

python3 "${REPO_DIR}/python/app/pipeline_batch.py" -h >/dev/null
echo "✓ help smoke test: ${REPO_DIR}/python/app/pipeline_batch.py"

echo "Script smoke tests completed successfully."
