#!/usr/bin/env bash

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <cat_name>" >&2
  exit 1
fi

CAT_NAME="$1"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

export CAT="${CAT_NAME}"
export TEST_N_CC="${TEST_N_CC:-1000}"
export TEST_N_ES="${TEST_N_ES:-100}"
export OUTPUT_BASE="${OUTPUT_BASE:-output/condor_scenarios}"
export OUTPUT_ROOT="${OUTPUT_BASE}/${CAT_NAME}"

cd "${REPO_DIR}"

./test/run_small_sample_pipeline.sh

echo "CAT ${CAT_NAME} completed. Output: ${OUTPUT_ROOT}"
