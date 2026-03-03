#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PIPELINE_BATCH_JSON="${PIPELINE_BATCH_JSON:-${REPO_DIR}/json/pipeline_100cats_config.json}"

json_get_or_default() {
  local json_path="$1"
  local query="$2"
  local default_value="$3"

  if [[ ! -f "${json_path}" ]]; then
    printf '%s\n' "${default_value}"
    return 0
  fi

  python3 - <<'PY' "${json_path}" "${query}" "${default_value}"
import json
import sys

json_path, query, default_value = sys.argv[1:]

try:
    with open(json_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
except Exception:
    print(default_value)
    raise SystemExit(0)

node = data
for key in query.split("."):
    if isinstance(node, dict) and key in node:
        node = node[key]
    else:
        print(default_value)
        raise SystemExit(0)

if node is None:
    print(default_value)
elif isinstance(node, bool):
    print("1" if node else "0")
else:
    print(str(node))
PY
}

DEFAULT_SAMPLES_BASE="/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples"
DEFAULT_CAT_GLOB="cat[0-9][0-9][0-9][0-9][0-9][0-9]"
DEFAULT_OUTPUT_BASE="output/condor_scenarios"

JSON_SAMPLES_BASE="$(json_get_or_default "${PIPELINE_BATCH_JSON}" "pipeline_batch.samples.base_dir" "${DEFAULT_SAMPLES_BASE}")"
JSON_CAT_GLOB="$(json_get_or_default "${PIPELINE_BATCH_JSON}" "pipeline_batch.samples.cat_glob" "${DEFAULT_CAT_GLOB}")"
JSON_OUTPUT_BASE="$(json_get_or_default "${PIPELINE_BATCH_JSON}" "pipeline_batch.condor.output_base" "${DEFAULT_OUTPUT_BASE}")"

SAMPLES_BASE="${SAMPLES_BASE:-${JSON_SAMPLES_BASE}}"
CAT_GLOB="${CAT_GLOB:-${JSON_CAT_GLOB}}"
CAT_LIMIT="${CAT_LIMIT:-0}"
TEST_N_CC="${TEST_N_CC:-1000}"
TEST_N_ES="${TEST_N_ES:-100}"
OUTPUT_BASE="${OUTPUT_BASE:-${JSON_OUTPUT_BASE}}"
REQUEST_CPUS="${REQUEST_CPUS:-1}"
REQUEST_MEMORY="${REQUEST_MEMORY:-8 GB}"
REQUEST_DISK="${REQUEST_DISK:-4 GB}"
JOB_FLAVOUR="${JOB_FLAVOUR:-workday}"
DRY_RUN="${DRY_RUN:-0}"
USER_NAME="${USER_NAME:-$(id -un)}"
LOG_DIR_REL="${LOG_DIR_REL:-condor/logs}"
CAT_LIST_REL="${CAT_LIST_REL:-condor/cat_list.txt}"
GENERATED_SUB_REL="${GENERATED_SUB_REL:-condor/submit_all_cats.generated.sub}"

if [[ "${OUTPUT_BASE}" != /* ]]; then
  OUTPUT_BASE_ABS="${REPO_DIR}/${OUTPUT_BASE}"
else
  OUTPUT_BASE_ABS="${OUTPUT_BASE}"
fi

if [[ "${LOG_DIR_REL}" != /* ]]; then
  LOG_DIR_ABS="${REPO_DIR}/${LOG_DIR_REL}"
else
  LOG_DIR_ABS="${LOG_DIR_REL}"
fi

if [[ "${CAT_LIST_REL}" != /* ]]; then
  CAT_LIST_ABS="${REPO_DIR}/${CAT_LIST_REL}"
else
  CAT_LIST_ABS="${CAT_LIST_REL}"
fi

if [[ "${GENERATED_SUB_REL}" != /* ]]; then
  GENERATED_SUB_ABS="${REPO_DIR}/${GENERATED_SUB_REL}"
else
  GENERATED_SUB_ABS="${GENERATED_SUB_REL}"
fi

cd "${REPO_DIR}"
mkdir -p "${LOG_DIR_ABS}"
mkdir -p "${OUTPUT_BASE_ABS}"

python3 condor/build_cat_list.py \
  --samples-base "${SAMPLES_BASE}" \
  --cat-glob "${CAT_GLOB}" \
  --limit "${CAT_LIMIT}" \
  --output "${CAT_LIST_ABS}"

if [[ ! -s "${CAT_LIST_ABS}" ]]; then
  echo "ERROR: ${CAT_LIST_ABS} is empty" >&2
  exit 1
fi

chmod +x condor/run_cat_scenarios.sh
chmod +x condor/aggregate_all_cats.sh

cat > "${GENERATED_SUB_ABS}" <<EOF
universe              = vanilla
executable            = /usr/bin/env
arguments             = bash ${REPO_DIR}/condor/run_cat_scenarios.sh \$(cat)
initialdir            = ${REPO_DIR}
should_transfer_files = NO

output                = ${LOG_DIR_ABS}/\$(cat).out
error                 = ${LOG_DIR_ABS}/\$(cat).err
log                   = ${LOG_DIR_ABS}/\$(cat).log

request_cpus          = \$(REQUEST_CPUS)
request_memory        = \$(REQUEST_MEMORY)
request_disk          = \$(REQUEST_DISK)
+JobFlavour           = "\$(JOB_FLAVOUR)"

batch_name            = "snop-all-cats-${USER_NAME}"
environment           = "TEST_N_CC=\$(TEST_N_CC) TEST_N_ES=\$(TEST_N_ES) OUTPUT_BASE=\$(OUTPUT_BASE)"

queue cat from ${CAT_LIST_ABS}
EOF

submit_cmd=(
  condor_submit
  TEST_N_CC="${TEST_N_CC}"
  TEST_N_ES="${TEST_N_ES}"
  OUTPUT_BASE="${OUTPUT_BASE_ABS}"
  REQUEST_CPUS="${REQUEST_CPUS}"
  REQUEST_MEMORY="${REQUEST_MEMORY}"
  REQUEST_DISK="${REQUEST_DISK}"
  JOB_FLAVOUR="${JOB_FLAVOUR}"
  "${GENERATED_SUB_ABS}"
)

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "Running Condor dry-run (no submission)..."
  "${submit_cmd[@]}" -dry-run "${REPO_DIR}/condor/submit_all_cats.dryrun"
  echo "Dry-run file: ${REPO_DIR}/condor/submit_all_cats.dryrun"
else
  "${submit_cmd[@]}"
fi

echo "Submitted CAT scenario jobs."
