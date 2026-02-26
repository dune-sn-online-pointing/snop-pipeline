#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

"${REPO_DIR}/test/run_full_pipeline_test.sh"
"${REPO_DIR}/test/run_ct_only_test.sh"
"${REPO_DIR}/test/run_ed_only_test.sh"
bash "${REPO_DIR}/test/run_batch_one_burst_test.sh"

echo "All pipeline tests completed successfully."
