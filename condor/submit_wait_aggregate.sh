#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: ./condor/submit_wait_aggregate.sh [options]

Submit CAT jobs to Condor, optionally wait for completion, then aggregate.

Options:
  --samples-base PATH     CAT source folder (default: /eos/user/e/evilla/dune/sn-tps/sn-burst-samples)
  --output-base PATH      Output folder for per-CAT results (default: output/condor_scenarios_corrected)
  --poll-sec N            Poll interval in seconds while waiting (default: 120)
  --no-wait               Submit and return immediately (no aggregation step)
  --force                 Force re-submit CATs even if success marker exists
  --dry-run               Prepare queue only, do not submit
  -h, --help              Show this help

Environment passthrough to submit script is supported (for example TEST_N_CC, TEST_N_ES,
BASE_CONFIG, REQUEST_CPUS, REQUEST_MEMORY, REQUEST_DISK, JOB_FLAVOUR, CATS_PER_JOB,
SCENARIO_NAMES, SCENARIO_CATALOG).
USAGE
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

SAMPLES_BASE="${SAMPLES_BASE:-/eos/user/e/evilla/dune/sn-tps/sn-burst-samples}"
OUTPUT_BASE="${OUTPUT_BASE:-output/condor_scenarios_corrected}"
POLL_SEC="${POLL_SEC:-120}"
WAIT_FOR_DONE=1
FORCE_FLAG=""
DRY_RUN="${DRY_RUN:-0}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --samples-base)
      SAMPLES_BASE="$2"
      shift 2
      ;;
    --output-base)
      OUTPUT_BASE="$2"
      shift 2
      ;;
    --poll-sec)
      POLL_SEC="$2"
      shift 2
      ;;
    --no-wait)
      WAIT_FOR_DONE=0
      shift
      ;;
    --force)
      FORCE_FLAG="--force"
      shift
      ;;
    --dry-run)
      DRY_RUN=1
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

if [[ ! -d "${SAMPLES_BASE}" ]]; then
  echo "ERROR: samples base not found: ${SAMPLES_BASE}" >&2
  exit 1
fi

if ! [[ "${POLL_SEC}" =~ ^[0-9]+$ ]] || [[ "${POLL_SEC}" -le 0 ]]; then
  echo "ERROR: --poll-sec must be a positive integer" >&2
  exit 1
fi

cd "${REPO_DIR}"

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "Running in dry-run mode (no Condor submission)."
fi

echo "Submitting CAT jobs"
echo "  SAMPLES_BASE: ${SAMPLES_BASE}"
echo "  OUTPUT_BASE:  ${OUTPUT_BASE}"

submit_output="$({
  SAMPLES_BASE="${SAMPLES_BASE}" \
  OUTPUT_BASE="${OUTPUT_BASE}" \
  DRY_RUN="${DRY_RUN}" \
  ./condor/submit_all_cats.sh ${FORCE_FLAG}
} 2>&1)"

echo "${submit_output}"

if [[ "${DRY_RUN}" == "1" ]]; then
  echo "Dry-run finished."
  exit 0
fi

cluster_id="$(printf '%s\n' "${submit_output}" | grep -oE 'cluster[[:space:]]+[0-9]+' | awk '{print $2}' | tail -n1 || true)"

if [[ -z "${cluster_id}" ]]; then
  if printf '%s' "${submit_output}" | grep -qi 'nothing to submit\|already completed'; then
    echo "No new jobs submitted (already completed). Running aggregation now..."
  else
    echo "ERROR: Could not parse cluster id from condor_submit output." >&2
    exit 1
  fi
fi

if [[ -n "${cluster_id}" && "${WAIT_FOR_DONE}" == "1" ]]; then
  echo "Waiting for Condor cluster ${cluster_id} to finish..."
  while true; do
    qout="$(condor_q "${cluster_id}" -nobatch 2>&1 || true)"

    if printf '%s' "${qout}" | grep -q "0 jobs"; then
      echo "Cluster ${cluster_id} no longer in queue (assumed finished)."
      break
    fi

    summary_line="$(printf '%s\n' "${qout}" | grep -i 'Total for query:' | tail -n1 || true)"
    if [[ -z "${summary_line}" ]]; then
      echo "Could not read queue summary, retrying in ${POLL_SEC}s..."
      continue
    fi

    # Example: Total for query: 125 jobs; 0 completed, 0 removed, 0 idle, 125 running, 0 held, 0 suspended
    if printf '%s' "${summary_line}" | grep -qE '[[:space:]]+[1-9][0-9]*[[:space:]]+running'; then
      echo "${summary_line}"
      sleep "${POLL_SEC}"
      continue
    fi
    if printf '%s' "${summary_line}" | grep -qE '[[:space:]]+[1-9][0-9]*[[:space:]]+idle'; then
      echo "${summary_line}"
      sleep "${POLL_SEC}"
      continue
    fi

    echo "${summary_line}"
    echo "No running/idle jobs remain for cluster ${cluster_id}."
    break
  done
elif [[ -n "${cluster_id}" ]]; then
  echo "Submission completed for cluster ${cluster_id}. Skipping wait/aggregation (--no-wait)."
  exit 0
fi

if [[ "${OUTPUT_BASE}" != /* ]]; then
  INPUT_ROOT="${REPO_DIR}/${OUTPUT_BASE}"
else
  INPUT_ROOT="${OUTPUT_BASE}"
fi

OUTPUT_PDF="${INPUT_ROOT}/scenario_aggregate_allcats_filtered.pdf"
OUTPUT_JSON="${INPUT_ROOT}/scenario_aggregate_allcats_filtered.json"

echo "Running aggregation"
echo "  INPUT_ROOT: ${INPUT_ROOT}"
echo "  OUTPUT_PDF: ${OUTPUT_PDF}"
echo "  OUTPUT_JSON: ${OUTPUT_JSON}"

INPUT_ROOT="${INPUT_ROOT}" \
OUTPUT_PDF="${OUTPUT_PDF}" \
OUTPUT_JSON="${OUTPUT_JSON}" \
./condor/aggregate_all_cats.sh

echo "All done."
