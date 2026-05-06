#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: ./condor/wait_cluster_and_aggregate.sh --cluster-id ID [options]

Options:
  --cluster-id ID       Condor cluster id to monitor (required)
  --input-root PATH     Root containing per-cat results (default: output/condor_scenarios_corrected)
  --poll-sec N          Poll interval in seconds (default: 120)
  -h, --help            Show this help
USAGE
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

CLUSTER_ID=""
INPUT_ROOT="${INPUT_ROOT:-output/condor_scenarios_corrected}"
POLL_SEC="${POLL_SEC:-120}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cluster-id)
      CLUSTER_ID="$2"
      shift 2
      ;;
    --input-root)
      INPUT_ROOT="$2"
      shift 2
      ;;
    --poll-sec)
      POLL_SEC="$2"
      shift 2
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

if [[ -z "${CLUSTER_ID}" ]]; then
  echo "ERROR: --cluster-id is required" >&2
  usage
  exit 1
fi

if ! [[ "${POLL_SEC}" =~ ^[0-9]+$ ]] || [[ "${POLL_SEC}" -le 0 ]]; then
  echo "ERROR: --poll-sec must be a positive integer" >&2
  exit 1
fi

cd "${REPO_DIR}"

echo "Monitoring Condor cluster ${CLUSTER_ID}"
while true; do
  qout="$(condor_q "${CLUSTER_ID}" -nobatch 2>&1 || true)"

  if printf '%s' "${qout}" | grep -q "0 jobs"; then
    echo "Cluster ${CLUSTER_ID} no longer in queue (assumed finished)."
    break
  fi

  summary_line="$(printf '%s\n' "${qout}" | grep -i 'Total for query:' | tail -n1 || true)"
  if [[ -z "${summary_line}" ]]; then
    echo "Could not read queue summary, retrying in ${POLL_SEC}s..."
    sleep "${POLL_SEC}"
    continue
  fi

  echo "${summary_line}"

  if printf '%s' "${summary_line}" | grep -qE '[[:space:]]+[1-9][0-9]*[[:space:]]+running'; then
    sleep "${POLL_SEC}"
    continue
  fi
  if printf '%s' "${summary_line}" | grep -qE '[[:space:]]+[1-9][0-9]*[[:space:]]+idle'; then
    sleep "${POLL_SEC}"
    continue
  fi

  echo "No running/idle jobs remain for cluster ${CLUSTER_ID}."
  break
done

if [[ "${INPUT_ROOT}" != /* ]]; then
  INPUT_ROOT_ABS="${REPO_DIR}/${INPUT_ROOT}"
else
  INPUT_ROOT_ABS="${INPUT_ROOT}"
fi

OUTPUT_PDF="${INPUT_ROOT_ABS}/scenario_aggregate_allcats_filtered.pdf"
OUTPUT_JSON="${INPUT_ROOT_ABS}/scenario_aggregate_allcats_filtered.json"

echo "Aggregating results"
echo "  INPUT_ROOT: ${INPUT_ROOT_ABS}"
echo "  OUTPUT_PDF: ${OUTPUT_PDF}"
echo "  OUTPUT_JSON: ${OUTPUT_JSON}"

INPUT_ROOT="${INPUT_ROOT_ABS}" \
OUTPUT_PDF="${OUTPUT_PDF}" \
OUTPUT_JSON="${OUTPUT_JSON}" \
./condor/aggregate_all_cats.sh

echo "Aggregation done."
