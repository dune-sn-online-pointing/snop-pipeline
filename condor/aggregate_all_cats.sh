#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

INPUT_ROOT="${INPUT_ROOT:-output/condor_scenarios}"
OUTPUT_PDF="${OUTPUT_PDF:-${INPUT_ROOT}/scenario_aggregate_allcats.pdf}"
OUTPUT_JSON="${OUTPUT_JSON:-${INPUT_ROOT}/scenario_aggregate_allcats.json}"

cd "${REPO_DIR}"

python3 python/ana/aggregate_scenario_reports.py \
  --input-root "${INPUT_ROOT}" \
  --output-pdf "${OUTPUT_PDF}" \
  --output-json "${OUTPUT_JSON}"
