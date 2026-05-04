#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${REPO_DIR}/scripts/init.sh"

echo "Running unit test (offline, synthetic inputs, no models)..."
"${REPO_DIR}/test/run_unit_test.sh"

echo "Running scripts smoke test..."
"${REPO_DIR}/test/run_scripts_smoke_test.sh"

echo ""
echo "--- EOS-dependent tests (require CERN EOS access + model files) ---"
echo "Running full pipeline test..."
"${REPO_DIR}/test/run_full_pipeline_test.sh"

echo "Running CT-only test..."
"${REPO_DIR}/test/run_ct_only_test.sh"

echo "Running one-burst batch test..."
"${REPO_DIR}/test/run_batch_one_burst_test.sh"

echo "All tests completed successfully."
