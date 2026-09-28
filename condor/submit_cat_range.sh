#!/usr/bin/env bash
# Submit the six-scenario pipeline for an explicit numeric CAT range.
# Trimmed variant of submit_all_cats.sh for campaigns that must not touch
# training cats (e.g. new cats 623+ only): instead of globbing every cat under
# SAMPLES_BASE, the queue is built from [FIRST,LAST] (cats must exist on EOS).
#
# Usage:
#   FIRST=623 LAST=1223 \
#   OUTPUT_BASE=/eos/user/e/evilla/dune/sn-tps/condor_scenarios_v80t080_ext1000 \
#   CT_MODEL=/eos/project-e/ep-nu/evilla/sn-online-pointing/neural-networks/channel_tagging/ct_volume_v80_20260706_224935/best_model.keras \
#   SCENARIO_CATALOG=json/six_scenarios_v80.json \
#   ./condor/submit_cat_range.sh
#
# Success-marker skipping and 5-cats-per-job grouping match submit_all_cats.sh.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

FIRST="${FIRST:?set FIRST (e.g. 623)}"
LAST="${LAST:?set LAST (e.g. 1223)}"
SAMPLES_BASE="${SAMPLES_BASE:-/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples}"
OUTPUT_BASE="${OUTPUT_BASE:?set OUTPUT_BASE (absolute path)}"
BASE_CONFIG="${BASE_CONFIG:-${REPO_DIR}/json/example_config.json}"
SCENARIO_CATALOG="${SCENARIO_CATALOG:-${REPO_DIR}/json/six_scenarios_v80.json}"
CT_MODEL="${CT_MODEL:-}"
TEST_N_CC="${TEST_N_CC:-3300}"
TEST_N_ES="${TEST_N_ES:-330}"
CATS_PER_JOB="${CATS_PER_JOB:-5}"
REQUEST_MEMORY="${REQUEST_MEMORY:-8 GB}"
REQUEST_DISK="${REQUEST_DISK:-4 GB}"
JOB_FLAVOUR="${JOB_FLAVOUR:-workday}"
USER_NAME="$(id -un)"
SUBMIT_TAG="$(date +%Y%m%d_%H%M%S)"
# CONDOR_LOG_DIR / CONDOR_OUT_DIR: optional overrides to keep condor logs (and job stdout/stderr) on AFS
LOG_DIR="${CONDOR_LOG_DIR:-/tmp/${USER_NAME}/snop_condor_logs/${SUBMIT_TAG}}"
CONDOR_OUT_DIR="${CONDOR_OUT_DIR:-}"
PRUNE_SCENARIO_OUTPUTS="${PRUNE_SCENARIO_OUTPUTS:-1}"
BATCH_TAG="${BATCH_TAG:-snop-range}"
OUT_DIR="${SCRIPT_DIR}/range_submissions"

mkdir -p "${LOG_DIR}" "${OUTPUT_BASE}" "${OUT_DIR}"
JOB_STDOUT="/dev/null"
JOB_STDERR="/dev/null"
if [[ -n "${CONDOR_OUT_DIR}" ]]; then
  mkdir -p "${CONDOR_OUT_DIR}"
  JOB_STDOUT="${CONDOR_OUT_DIR}/job_\$(ClusterId)_\$(ProcId).out"
  JOB_STDERR="${CONDOR_OUT_DIR}/job_\$(ClusterId)_\$(ProcId).err"
fi
cd "${REPO_DIR}"

GROUP_LIST="${OUT_DIR}/cat_group_list_${FIRST}to${LAST}_${SUBMIT_TAG}.txt"
GENERATED_SUB="${OUT_DIR}/submit_${FIRST}to${LAST}_${SUBMIT_TAG}.sub"

python3 - "$SAMPLES_BASE" "$FIRST" "$LAST" "$OUTPUT_BASE" "$CATS_PER_JOB" "$GROUP_LIST" <<'PY'
import sys
from pathlib import Path

samples_base, first, last, output_base, group_size, group_list = sys.argv[1:]
first, last, group_size = int(first), int(last), int(group_size)

import glob
import os

allow_training = os.environ.get("ALLOW_TRAINING_CATS", "0") == "1"
require_products = os.environ.get("REQUIRE_PRODUCTS", "0") == "1"
min_es = int(os.environ.get("MIN_ES_FILES", "10"))
min_cc = int(os.environ.get("MIN_CC_FILES", "83"))
# Documented per-cat exceptions to the global >= 83 CC-file rule.  The rule exists
# because the TEST_N_CC=3300 draw needs 83 files of 40 generated events; a cat that
# cannot supply them is a REDUCED-STATISTICS burst, not a normal one.  cat000001 kept
# only 37 of its CC tpstreams (see refactor-online-utils/condor/evilla/campaign_r2/
# notes.md), i.e. ~1480 generated CC events instead of 3300, so its scenario 3 (full
# pipeline) and scenario 4 (weighted CT) are NOT comparable with the other cats and
# must be reported separately.  It is admitted explicitly here rather than by lowering
# MIN_CC_FILES globally, which would silently let any short cat into a campaign.
MIN_CC_FILES_PER_CAT = {"cat000001": 37}
state_file = os.environ.get("SUBMITTED_STATE", "")
in_flight = set()
if state_file and Path(state_file).is_file():
    in_flight = {l.strip() for l in Path(state_file).read_text().splitlines() if l.strip()}

pending, done, absent, training, unprocessed, skipped_in_flight = [], [], [], [], [], []
for n in range(first, last + 1):
    cat = f"cat{n:06d}"
    if not (Path(samples_base) / cat).is_dir():
        absent.append(cat)
        continue
    if not allow_training and (Path(samples_base) / cat / "TRAINING_CAT.txt").is_file():
        training.append(cat)
        continue
    marker = Path(output_base) / cat / "scenario_cos_theta_report.json"
    if marker.is_file() and marker.stat().st_size > 0:
        done.append(cat)
        continue
    if cat in in_flight:
        skipped_in_flight.append(cat)
        continue
    if require_products:
        # a cat is usable once it holds enough events for the test draw:
        # TEST_N_ES=330 needs 9 ES files, TEST_N_CC=3300 needs 83 CC files (40 ev/file)
        # PRODUCT_SUFFIX (same env var the pipeline uses to pick its inputs) must also
        # gate this readiness check: without it the ORIGINAL "..._e3p0" folders would be
        # counted and a cat would look ready before its suffixed products exist.
        suffix = os.environ.get("PRODUCT_SUFFIX", "").strip()
        def _pick(paths):
            if not suffix:
                return paths
            return [p for p in paths if Path(p).parent.parent.name.endswith(suffix)]
        vols = [Path(p).name for p in _pick(
                glob.glob(str(Path(samples_base) / cat / f"{cat}_volume_images_*/X/*.npz")))]
        clus = [Path(p).name for p in _pick(
                glob.glob(str(Path(samples_base) / cat / f"{cat}_cluster_images_*/X/*.npz")))]
        n_es = sum(1 for f in vols if f.startswith("es_"))
        n_cc = sum(1 for f in vols if f.startswith("cc_"))
        min_cc_cat = MIN_CC_FILES_PER_CAT.get(cat, min_cc)
        if n_es < min_es or n_cc < min_cc_cat or len(clus) < min_es + min_cc_cat:
            unprocessed.append(cat)
            continue
        if min_cc_cat != min_cc:
            print(f"NOTE {cat}: admitted with a per-cat CC-file floor of {min_cc_cat} "
                  f"(global {min_cc}) - REDUCED STATISTICS, scenarios 3/4 not comparable")
    pending.append(cat)
if training:
    print(f"EXCLUDED {len(training)} training cats (TRAINING_CAT.txt; set ALLOW_TRAINING_CATS=1 to override)")
if unprocessed:
    print(f"skipped {len(unprocessed)} cats with incomplete processing products")
if skipped_in_flight:
    print(f"skipped {len(skipped_in_flight)} cats already submitted (in {state_file})")
if state_file and pending and os.environ.get("DRY_RUN", "0") != "1":
    with open(state_file, "a") as fh:
        fh.write("\n".join(pending) + "\n")

groups = [pending[i:i + group_size] for i in range(0, len(pending), group_size)]
Path(group_list).write_text("\n".join(",".join(g) for g in groups) + ("\n" if groups else ""))
print(f"range {first}-{last}: {len(pending)} pending, {len(done)} done, {len(absent)} absent on EOS")
print(f"{len(groups)} condor jobs ({group_size} cats/job)")
if absent[:5]:
    print("first absent:", ", ".join(absent[:5]))
PY

if [[ ! -s "${GROUP_LIST}" ]]; then
  echo "Nothing pending to submit."
  exit 0
fi

chmod +x condor/run_cat_scenarios.sh

cat > "${GENERATED_SUB}" <<EOF
universe              = vanilla
executable            = /usr/bin/env
arguments             = bash ${REPO_DIR}/condor/run_cat_scenarios.sh \$(cat_group)
initialdir            = ${REPO_DIR}
should_transfer_files = NO

output                = ${JOB_STDOUT}
error                 = ${JOB_STDERR}
log                   = ${LOG_DIR}/job_\$(ClusterId)_\$(ProcId).log

request_cpus          = 1
request_memory        = ${REQUEST_MEMORY}
request_disk          = ${REQUEST_DISK}
+JobFlavour           = "${JOB_FLAVOUR}"

batch_name            = "${BATCH_TAG}-${FIRST}-${LAST}-${USER_NAME}"
environment           = "TEST_N_CC=${TEST_N_CC} TEST_N_ES=${TEST_N_ES} OUTPUT_BASE=${OUTPUT_BASE} BASE_CONFIG=${BASE_CONFIG} CT_MODEL=${CT_MODEL} SCENARIO_CATALOG=${SCENARIO_CATALOG} SAMPLES_BASE=${SAMPLES_BASE} PRUNE_SCENARIO_OUTPUTS=${PRUNE_SCENARIO_OUTPUTS} SCENARIO_NAMES=${SCENARIO_NAMES:-} PRODUCT_SUFFIX=${PRODUCT_SUFFIX:-} PDF_PATH=${PDF_PATH:-}"

queue cat_group from ${GROUP_LIST}
EOF

if [[ "${DRY_RUN:-0}" == "1" ]]; then
  echo "DRY_RUN: submit file at ${GENERATED_SUB}"
  cat "${GENERATED_SUB}"
else
  condor_submit "${GENERATED_SUB}"
  echo "Log dir: ${LOG_DIR}"
fi
