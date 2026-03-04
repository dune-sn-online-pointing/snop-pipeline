#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

CONFIG="${REPO_DIR}/json/pipeline_batch_one_burst_test_config.json"

python3 "${REPO_DIR}/python/app/pipeline_batch.py" -j "${CONFIG}"

for f in \
  "${REPO_DIR}/output/pipeline_one_burst_test/aggregate_summary.json" \
  "${REPO_DIR}/output/pipeline_one_burst_test/aggregate_summary.png" \
  "${REPO_DIR}/output/pipeline_one_burst_test/burst_direction_report.json" \
  "${REPO_DIR}/output/pipeline_one_burst_test/burst_direction_report.pdf"; do
  if [[ ! -f "${f}" ]]; then
    echo "ERROR: missing one-burst batch artifact: ${f}" >&2
    exit 1
  fi
done

echo "One-burst batch test completed successfully."
