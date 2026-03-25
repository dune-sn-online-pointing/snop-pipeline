#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

INPUT_ROOT="${INPUT_ROOT:-output/condor_scenarios_3mev}"
OUTPUT_PDF="${OUTPUT_PDF:-${INPUT_ROOT}/scenario_aggregate_allcats_filtered.pdf}"
OUTPUT_JSON="${OUTPUT_JSON:-${INPUT_ROOT}/scenario_aggregate_allcats_filtered.json}"

cd "${REPO_DIR}"

echo "Aggregating scenarios with ES event filtering from: ${INPUT_ROOT}"
echo "Output PDF: ${OUTPUT_PDF}"
echo "Output JSON: ${OUTPUT_JSON}"
echo "Filtering: Excluding cats with <30 ES events (insufficient raw data)"

python3 python/ana/aggregate_scenario_reports.py \
  --input-root "${INPUT_ROOT}" \
  --output-pdf "${OUTPUT_PDF}" \
  --output-json "${OUTPUT_JSON}"

echo "✓ Filtered aggregation complete!"