#!/usr/bin/env bash
# Offline re-evaluation of one group of cats under the generated-event budget.
#   $1 = comma-separated cat list
#   env MODE=budget|gate|index, OUT_ROOT (budget), OUT_JSON_DIR (gate/index)
set -euo pipefail

CAT_GROUP="${1:?cat group}"
MODE="${MODE:-budget}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

export SNOP_SKIP_DEP_CHECKS=1
source "${REPO_DIR}/scripts/init.sh"
cd "${REPO_DIR}"

SCRATCH="${TMPDIR:-/tmp}/budget_replay_$$"
mkdir -p "${SCRATCH}"
trap 'rm -rf "${SCRATCH}"' EXIT

case "${MODE}" in
  budget)
    python3 python/ana/budget_replay.py budget --cats "${CAT_GROUP}" \
      --out-root "${OUT_ROOT:?set OUT_ROOT}" --scratch "${SCRATCH}"
    ;;
  gate|index)
    TAG="$(echo "${CAT_GROUP}" | cut -d, -f1)"
    mkdir -p "${OUT_JSON_DIR:?set OUT_JSON_DIR}"
    python3 python/ana/budget_replay.py "${MODE}" --cats "${CAT_GROUP}" \
      --out "${OUT_JSON_DIR}/${MODE}_${TAG}.json" --scratch "${SCRATCH}"
    ;;
  *) echo "unknown MODE=${MODE}" >&2; exit 2 ;;
esac
