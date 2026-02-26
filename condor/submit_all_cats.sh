#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

SAMPLES_BASE="${SAMPLES_BASE:-/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples}"
CAT_GLOB="${CAT_GLOB:-cat[0-9][0-9][0-9][0-9][0-9][0-9]}"
CAT_LIMIT="${CAT_LIMIT:-0}"
TEST_N_CC="${TEST_N_CC:-1000}"
TEST_N_ES="${TEST_N_ES:-100}"
OUTPUT_BASE="${OUTPUT_BASE:-output/condor_scenarios}"
REQUEST_CPUS="${REQUEST_CPUS:-1}"
REQUEST_MEMORY="${REQUEST_MEMORY:-8 GB}"
REQUEST_DISK="${REQUEST_DISK:-4 GB}"
JOB_FLAVOUR="${JOB_FLAVOUR:-workday}"
DRY_RUN="${DRY_RUN:-0}"

cd "${REPO_DIR}"
mkdir -p condor/logs
mkdir -p "${OUTPUT_BASE}"

python3 condor/build_cat_list.py \
  --samples-base "${SAMPLES_BASE}" \
  --cat-glob "${CAT_GLOB}" \
  --limit "${CAT_LIMIT}" \
  --output condor/cat_list.txt

if [[ ! -s condor/cat_list.txt ]]; then
  echo "ERROR: condor/cat_list.txt is empty" >&2
  exit 1
fi

chmod +x condor/run_cat_scenarios.sh
chmod +x condor/aggregate_all_cats.sh

submit_cmd=(
  condor_submit
  TEST_N_CC="${TEST_N_CC}"
  TEST_N_ES="${TEST_N_ES}"
  OUTPUT_BASE="${OUTPUT_BASE}"
  REQUEST_CPUS="${REQUEST_CPUS}"
  REQUEST_MEMORY="${REQUEST_MEMORY}"
  REQUEST_DISK="${REQUEST_DISK}"
  JOB_FLAVOUR="${JOB_FLAVOUR}"
  condor/submit_all_cats.sub
)

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "Running Condor dry-run (no submission)..."
  "${submit_cmd[@]}" -dry-run condor/submit_all_cats.dryrun
  echo "Dry-run file: condor/submit_all_cats.dryrun"
else
  "${submit_cmd[@]}"
fi

echo "Submitted CAT scenario jobs."
