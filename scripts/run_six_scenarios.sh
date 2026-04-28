#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

source "${REPO_DIR}/scripts/init.sh"

# Production defaults: keep full scenario folders unless caller explicitly prunes.
export OUTPUT_ROOT="${OUTPUT_ROOT:-${REPO_DIR}/output/pipeline_scenarios}"
export PRUNE_SCENARIO_OUTPUTS="${PRUNE_SCENARIO_OUTPUTS:-0}"
export SCENARIO_CATALOG="${SCENARIO_CATALOG:-${REPO_DIR}/json/six_scenarios.json}"

"${REPO_DIR}/test/run_small_sample_pipeline.sh"
