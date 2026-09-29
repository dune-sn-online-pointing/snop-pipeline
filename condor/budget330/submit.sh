#!/usr/bin/env bash
# Submit the budget/gate re-evaluation.  Example:
#   MODE=gate  CAT_FILE=.../cats_gate.txt CATS_PER_JOB=10 ./submit.sh
#   MODE=budget CAT_FILE=.../cats_all.txt CATS_PER_JOB=20 \
#     OUT_ROOT=/eos/.../v80_fixed_1000_budget330 ./submit.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
MODE="${MODE:-budget}"
CAT_FILE="${CAT_FILE:?set CAT_FILE}"
CATS_PER_JOB="${CATS_PER_JOB:-20}"
TAG="$(date +%Y%m%d_%H%M%S)"
LIST="${SCRIPT_DIR}/lists/${MODE}_groups_${TAG}.txt"
LOGS="${SCRIPT_DIR}/logs/${MODE}_${TAG}"
mkdir -p "${LOGS}" "$(dirname "${LIST}")"

OUT_ROOT="${OUT_ROOT:-}"
OUT_JSON_DIR="${OUT_JSON_DIR:-${SCRIPT_DIR}/logs/${MODE}_${TAG}_json}"
mkdir -p "${OUT_JSON_DIR}"

python3 - "${CAT_FILE}" "${CATS_PER_JOB}" "${LIST}" "${OUT_ROOT}" <<'PY'
import sys
from pathlib import Path
cat_file, n, out, out_root = sys.argv[1:]
cats = [l.strip() for l in Path(cat_file).read_text().splitlines() if l.strip()]
if out_root:
    cats = [c for c in cats
            if not (Path(out_root) / c / "scenario_cos_theta_report.json").is_file()]
n = int(n)
groups = [cats[i:i+n] for i in range(0, len(cats), n)]
Path(out).write_text("\n".join(",".join(g) for g in groups) + ("\n" if groups else ""))
print(f"{len(cats)} cats pending -> {len(groups)} jobs")
PY

if [[ ! -s "${LIST}" ]]; then echo "nothing to do"; exit 0; fi

SUB="${SCRIPT_DIR}/lists/${MODE}_${TAG}.sub"
cat > "${SUB}" <<EOF
universe              = vanilla
executable            = /usr/bin/env
arguments             = bash ${SCRIPT_DIR}/run_budget_replay.sh \$(cat_group)
initialdir            = ${REPO_DIR}
should_transfer_files = NO
output                = ${LOGS}/job_\$(ClusterId)_\$(ProcId).out
error                 = ${LOGS}/job_\$(ClusterId)_\$(ProcId).err
log                   = ${LOGS}/job_\$(ClusterId)_\$(ProcId).log
request_cpus          = 1
request_memory        = ${REQUEST_MEMORY:-4 GB}
request_disk          = ${REQUEST_DISK:-2 GB}
+JobFlavour           = "${JOB_FLAVOUR:-workday}"
batch_name            = "snop-${MODE}330-${TAG}"
environment           = "MODE=${MODE} OUT_ROOT=${OUT_ROOT} OUT_JSON_DIR=${OUT_JSON_DIR} SNOP_SKIP_DEP_CHECKS=1"
queue cat_group from ${LIST}
EOF
if [[ "${DRY_RUN:-0}" == "1" ]]; then cat "${SUB}"; else condor_submit "${SUB}"; fi
echo "logs: ${LOGS}"
echo "json: ${OUT_JSON_DIR}"
