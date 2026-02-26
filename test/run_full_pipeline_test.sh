#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

export TEST_N_CC="${TEST_N_CC:-40}"
export TEST_N_ES="${TEST_N_ES:-8}"

"${REPO_DIR}/test/run_small_sample_pipeline.sh"
