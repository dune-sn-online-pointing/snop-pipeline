#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: ./condor/submit_all_cats.sh [-f|--force] [-h|--help]

Options:
  -f, --force   Submit all CATs even if success marker already exists.
                Existing cat folders/files are not deleted.
  -h, --help    Show this help and exit.
USAGE
}

FORCE_OVERWRITE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -f|--force)
      FORCE_OVERWRITE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

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
CATS_PER_JOB="${CATS_PER_JOB:-5}"
MAX_MATERIALIZE="${MAX_MATERIALIZE:-5}"
MAX_IDLE="${MAX_IDLE:-5}"
DRY_RUN="${DRY_RUN:-0}"
USER_NAME="${USER_NAME:-$(id -un)}"
SUBMIT_TAG="${SUBMIT_TAG:-$(date +%Y%m%d_%H%M%S)}"
LOG_DIR_REL="${LOG_DIR_REL:-condor/logs/${SUBMIT_TAG}}"
CAT_LIST_REL="${CAT_LIST_REL:-condor/cat_list.txt}"
PENDING_CAT_LIST_REL="${PENDING_CAT_LIST_REL:-condor/cat_list_pending.txt}"
CAT_GROUP_LIST_REL="${CAT_GROUP_LIST_REL:-condor/cat_group_list.txt}"
SUCCESS_MARKER_REL="${SUCCESS_MARKER_REL:-scenario_cos_theta_report.json}"
GENERATED_SUB_REL="${GENERATED_SUB_REL:-condor/submit_all_cats.generated.sub}"
PROC_CAT_MAP_REL="${PROC_CAT_MAP_REL:-condor/proc_cat_map.txt}"

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

if [[ "${PENDING_CAT_LIST_REL}" != /* ]]; then
  PENDING_CAT_LIST_ABS="${REPO_DIR}/${PENDING_CAT_LIST_REL}"
else
  PENDING_CAT_LIST_ABS="${PENDING_CAT_LIST_REL}"
fi

if [[ "${CAT_GROUP_LIST_REL}" != /* ]]; then
  CAT_GROUP_LIST_ABS="${REPO_DIR}/${CAT_GROUP_LIST_REL}"
else
  CAT_GROUP_LIST_ABS="${CAT_GROUP_LIST_REL}"
fi

if [[ "${PROC_CAT_MAP_REL}" != /* ]]; then
  PROC_CAT_MAP_ABS="${REPO_DIR}/${PROC_CAT_MAP_REL}"
else
  PROC_CAT_MAP_ABS="${PROC_CAT_MAP_REL}"
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

python3 - <<'PY' "${CAT_LIST_ABS}" "${PENDING_CAT_LIST_ABS}" "${OUTPUT_BASE_ABS}" "${SUCCESS_MARKER_REL}" "${FORCE_OVERWRITE}"
from pathlib import Path
import sys

all_cats_path = Path(sys.argv[1])
pending_path = Path(sys.argv[2])
output_base = Path(sys.argv[3])
success_marker_rel = sys.argv[4]
force_overwrite = bool(int(sys.argv[5]))

all_cats = [line.strip() for line in all_cats_path.read_text().splitlines() if line.strip()]
pending = []
completed = []

if force_overwrite:
  pending = list(all_cats)
else:
  for cat in all_cats:
    marker = output_base / cat / success_marker_rel
    if marker.is_file() and marker.stat().st_size > 0:
      completed.append(cat)
    else:
      pending.append(cat)

pending_path.parent.mkdir(parents=True, exist_ok=True)
pending_path.write_text("\n".join(pending) + ("\n" if pending else ""))

if force_overwrite:
  print("Force mode enabled: ignoring success markers")
  print(f"CATs to submit:             {len(pending)}")
else:
  print(f"Already successful (skipped): {len(completed)}")
  print(f"Pending CATs to submit:      {len(pending)}")
PY

if [[ ! -s "${PENDING_CAT_LIST_ABS}" ]]; then
  echo "All CATs already completed successfully; nothing to submit."
  exit 0
fi

python3 - <<'PY' "${PENDING_CAT_LIST_ABS}" "${CAT_GROUP_LIST_ABS}" "${CATS_PER_JOB}"
from pathlib import Path
import sys

pending_path = Path(sys.argv[1])
groups_path = Path(sys.argv[2])
group_size = max(1, int(sys.argv[3]))

cats = [line.strip() for line in pending_path.read_text().splitlines() if line.strip()]
groups = [cats[i:i + group_size] for i in range(0, len(cats), group_size)]

groups_path.parent.mkdir(parents=True, exist_ok=True)
groups_path.write_text("\n".join(",".join(group) for group in groups) + ("\n" if groups else ""))

print(f"Grouped pending CATs into {len(groups)} job(s), {group_size} CATs/job")
PY

if [[ ! -s "${CAT_GROUP_LIST_ABS}" ]]; then
  echo "ERROR: ${CAT_GROUP_LIST_ABS} is empty" >&2
  exit 1
fi

python3 - <<'PY' "${CAT_GROUP_LIST_ABS}" "${PROC_CAT_MAP_ABS}"
from pathlib import Path
import sys

groups_path = Path(sys.argv[1])
mapping_path = Path(sys.argv[2])

groups = [line.strip() for line in groups_path.read_text().splitlines() if line.strip()]
mapping_path.parent.mkdir(parents=True, exist_ok=True)

with mapping_path.open("w", encoding="utf-8") as handle:
    handle.write("proc_id\tcat_group\n")
    for proc_id, group in enumerate(groups):
        handle.write(f"{proc_id}\t{group}\n")

print(f"Wrote proc→CAT-group map: {mapping_path}")
PY

chmod +x condor/run_cat_scenarios.sh
chmod +x condor/aggregate_all_cats.sh

cat > "${GENERATED_SUB_ABS}" <<EOF
universe              = vanilla
executable            = /usr/bin/env
arguments             = bash ${REPO_DIR}/condor/run_cat_scenarios.sh \$(cat_group)
initialdir            = ${REPO_DIR}
should_transfer_files = NO

output                = ${LOG_DIR_ABS}/job_\$(ClusterId)_\$(ProcId).out
error                 = ${LOG_DIR_ABS}/job_\$(ClusterId)_\$(ProcId).err
log                   = ${LOG_DIR_ABS}/job_\$(ClusterId)_\$(ProcId).log

request_cpus          = \$(REQUEST_CPUS)
request_memory        = \$(REQUEST_MEMORY)
request_disk          = \$(REQUEST_DISK)
+JobFlavour           = "\$(JOB_FLAVOUR)"
max_materialize       = \$(MAX_MATERIALIZE)
max_idle              = \$(MAX_IDLE)

batch_name            = "snop-all-cats-${USER_NAME}"
environment           = "TEST_N_CC=\$(TEST_N_CC) TEST_N_ES=\$(TEST_N_ES) OUTPUT_BASE=\$(OUTPUT_BASE)"

queue cat_group from ${CAT_GROUP_LIST_ABS}
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
  MAX_MATERIALIZE="${MAX_MATERIALIZE}"
  MAX_IDLE="${MAX_IDLE}"
  "${GENERATED_SUB_ABS}"
)

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "Running Condor dry-run (no submission)..."
  "${submit_cmd[@]}" -dry-run "${REPO_DIR}/condor/submit_all_cats.dryrun"
  echo "Dry-run file: ${REPO_DIR}/condor/submit_all_cats.dryrun"
else
  submit_output="$("${submit_cmd[@]}")"
  echo "${submit_output}"

  cluster_id="$(printf '%s\n' "${submit_output}" | grep -oE 'cluster[[:space:]]+[0-9]+' | awk '{print $2}' | tail -n1 || true)"
  if [[ -n "${cluster_id}" ]]; then
    cluster_artifacts_dir="${REPO_DIR}/condor/submissions/${cluster_id}"
    mkdir -p "${cluster_artifacts_dir}"
    cp "${PROC_CAT_MAP_ABS}" "${cluster_artifacts_dir}/proc_cat_map.txt"
    cp "${CAT_GROUP_LIST_ABS}" "${cluster_artifacts_dir}/cat_group_list.txt"
    cp "${GENERATED_SUB_ABS}" "${cluster_artifacts_dir}/submit_all_cats.generated.sub"

    echo "Cluster ID: ${cluster_id}"
    echo "Proc→CAT map: ${cluster_artifacts_dir}/proc_cat_map.txt"
    echo "Log directory: ${LOG_DIR_ABS}"
    echo "Submit artifacts: ${cluster_artifacts_dir}"
    echo "Note: With late materialization, condor_q shows only materialized ProcIds."
    echo "Check factory summary: condor_q -factory ${cluster_id}"
    echo "Check visible jobs:    condor_q ${cluster_id} -nobatch"
  fi
fi

echo "Submitted CAT scenario jobs."
