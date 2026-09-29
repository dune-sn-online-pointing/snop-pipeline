#!/usr/bin/env bash
# Submit the acceptance-scenario replay over the r3 campaign in chunks of CHUNK cats.
# The cat list is the 1000 campaign cats: 1-399 and 623-1224 except 701.  Cats 400-621
# (training) are never included; the driver refuses them anyway.
#   CHUNK        cats per job (default 25)
#   OUT          output root
#   MAX_JOBS     refuse to submit more than this many jobs (default 60)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CHUNK="${CHUNK:-25}"
OUT="${OUT:?set OUT}"
CAMPAIGN="${CAMPAIGN:-/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-campaign/v63_matchfix_1000}"
CATALOG="${CATALOG:-${REPO}/json/seven_scenarios_v63_acceptance.json}"
SCENARIO="${SCENARIO:-scenario_7_full_pipeline_acc}"
SRCSCEN="${SRCSCEN:-scenario_3_full_pipeline}"
MAX_JOBS="${MAX_JOBS:-60}"
TAG="$(date +%Y%m%d_%H%M%S)"
LOGDIR="${REPO}/condor/logs/combo_acc_replay"
LIST="${SCRIPT_DIR}/chunks_${TAG}.txt"
SUB="${SCRIPT_DIR}/submit_${TAG}.sub"
mkdir -p "${LOGDIR}" "${OUT}"

python3 - "$CHUNK" "$LIST" "$CAMPAIGN" "$OUT" <<'PY'
import sys
from pathlib import Path
chunk, list_path, campaign, out = int(sys.argv[1]), sys.argv[2], Path(sys.argv[3]), Path(sys.argv[4])
cats = [n for n in list(range(1, 400)) + list(range(623, 1225)) if n != 701]
assert len(cats) == 1000, len(cats)
have, missing, done = [], [], []
for n in cats:
    cat = f"cat{n:06d}"
    if not (campaign / cat / f"{cat}_scenarios_slim.tar").is_file():
        missing.append(cat)
        continue
    js = list((out / cat).glob("scenario_cos_theta_report.json")) if (out / cat).is_dir() else []
    if js and js[0].stat().st_size > 0:
        done.append(cat)
        continue
    have.append(n)
groups = [have[i:i + chunk] for i in range(0, len(have), chunk)]
Path(list_path).write_text("".join(f"{g[0]}-{g[-1]}\n" if g[-1] - g[0] + 1 == len(g)
                                   else ",".join(str(x) for x in g) + "\n" for g in groups))
print(f"{len(cats)} campaign cats: {len(have)} to run, {len(done)} already done, "
      f"{len(missing)} without a slim tar")
if missing[:5]:
    print("first missing:", ", ".join(missing[:5]))
print(f"{len(groups)} jobs of <= {chunk} cats")
PY

NJOBS=$(wc -l < "${LIST}")
if [[ "${NJOBS}" -eq 0 ]]; then echo "nothing to submit"; exit 0; fi
if [[ "${NJOBS}" -gt "${MAX_JOBS}" ]]; then
  echo "refusing to submit ${NJOBS} jobs (> MAX_JOBS=${MAX_JOBS}); raise CHUNK" >&2; exit 1
fi

cat > "${SUB}" <<SUBEOF
universe            = vanilla
executable          = ${SCRIPT_DIR}/run_replay.sh
initialdir          = ${REPO}
should_transfer_files = NO
output              = ${LOGDIR}/replay_\$(ClusterId)_\$(ProcId).out
error               = ${LOGDIR}/replay_\$(ClusterId)_\$(ProcId).err
log                 = ${LOGDIR}/replay_\$(ClusterId)_\$(ProcId).log
request_cpus        = 1
request_memory      = 4 GB
request_disk        = 4 GB
+JobFlavour         = "workday"
batch_name          = "combo-acc-replay-\$ENV(USER)"
environment         = "CATS=\$(cats) OUT=${OUT} CATALOG=${CATALOG} SCENARIO=${SCENARIO} SRCSCEN=${SRCSCEN} CAMPAIGN=${CAMPAIGN}"
queue cats from ${LIST}
SUBEOF

if [[ "${DRY_RUN:-0}" == "1" ]]; then echo "DRY_RUN: ${SUB}"; cat "${SUB}"; echo "--- chunks:"; head -3 "${LIST}"; else
  condor_submit "${SUB}"; echo "logs: ${LOGDIR}"; fi
