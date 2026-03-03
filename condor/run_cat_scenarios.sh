#!/usr/bin/env bash

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <cat_name[,cat_name,...]>" >&2
  exit 1
fi

CAT_GROUP="$1"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

export TEST_N_CC="${TEST_N_CC:-1000}"
export TEST_N_ES="${TEST_N_ES:-100}"
export OUTPUT_BASE="${OUTPUT_BASE:-output/condor_scenarios}"

cd "${REPO_DIR}"

IFS=',' read -r -a CAT_NAMES <<< "${CAT_GROUP}"

for CAT_NAME in "${CAT_NAMES[@]}"; do
  CAT_NAME="$(echo "${CAT_NAME}" | xargs)"
  if [[ -z "${CAT_NAME}" ]]; then
    continue
  fi

  export CAT="${CAT_NAME}"
  export OUTPUT_ROOT="${OUTPUT_BASE}/${CAT_NAME}"

  echo "Running CAT ${CAT_NAME}"
  ./test/run_small_sample_pipeline.sh
  echo "CAT ${CAT_NAME} completed. Output: ${OUTPUT_ROOT}"
done
