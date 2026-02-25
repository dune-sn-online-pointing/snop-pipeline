#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

BASE_CONFIG="${BASE_CONFIG:-${REPO_DIR}/json/example_config.json}"
OUTPUT_ROOT="${OUTPUT_ROOT:-${REPO_DIR}/output/test_pipeline_scenarios}"

SAMPLES_BASE="${SAMPLES_BASE:-/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples}"
NETWORKS_BASE="${NETWORKS_BASE:-/eos/project-e/ep-nu/evilla/sn-online-pointing/neural-networks}"
CAT="${CAT:-cat000001}"

CT_MODEL_DEFAULT="${NETWORKS_BASE}/channel_tagging/ct_volume_v78_dario_10k_20251123_153908/best_model.keras"

if [[ ! -f "${BASE_CONFIG}" ]]; then
  echo "ERROR: base config not found: ${BASE_CONFIG}" >&2
  exit 1
fi

mkdir -p "${OUTPUT_ROOT}"

run_scenario() {
  local scenario_name="$1"
  local n_cc="$2"
  local n_es="$3"
  local ct_enabled="$4"

  local scenario_dir="${OUTPUT_ROOT}/${scenario_name}"
  local scenario_config="${scenario_dir}/config.json"
  mkdir -p "${scenario_dir}"

  python3 - <<'PY' "${BASE_CONFIG}" "${scenario_config}" "${SAMPLES_BASE}" "${CAT}" "${CT_MODEL_DEFAULT}" "${scenario_dir}" "${n_cc}" "${n_es}" "${ct_enabled}"
import json
import sys

base_config, out_config, samples_base, cat, ct_model, scenario_dir, n_cc, n_es, ct_enabled = sys.argv[1:]

with open(base_config, "r") as f:
    cfg = json.load(f)

cfg["input_data"]["cc_folder"] = f"{samples_base}/{cat}/cc_clusters_X"
cfg["input_data"]["es_folder"] = f"{samples_base}/{cat}/es_clusters_X"
cfg["sample_selection"]["n_cc_events"] = int(n_cc)
cfg["sample_selection"]["n_es_events"] = int(n_es)
cfg.setdefault("volume_creation", {})["use_simple_mode"] = True
cfg.setdefault("neural_networks", {}).setdefault("channel_tagger", {})["enabled"] = (ct_enabled == "1")
cfg["neural_networks"]["channel_tagger"]["model_path"] = ct_model
cfg.setdefault("output", {})["base_folder"] = scenario_dir
cfg["output"]["report_file"] = "pipeline_report.pdf"

with open(out_config, "w") as f:
    json.dump(cfg, f, indent=2)

print(f"Wrote scenario config: {out_config}")
PY

  echo
  echo "============================================================"
  echo "Running scenario: ${scenario_name}"
  echo "  n_cc_events: ${n_cc}"
  echo "  n_es_events: ${n_es}"
  echo "  channel_tagger.enabled: ${ct_enabled}"
  echo "============================================================"

  python3 "${REPO_DIR}/python/app/pipeline.py" -j "${scenario_config}"

  local latest_run
  latest_run="$(ls -1dt "${scenario_dir}"/pipeline_run_* 2>/dev/null | head -n1 || true)"
  if [[ -z "${latest_run}" ]]; then
    echo "ERROR: scenario ${scenario_name} produced no pipeline_run_* folder" >&2
    exit 1
  fi

  local report_file="${latest_run}/pipeline_report.pdf"
  if [[ ! -f "${report_file}" ]]; then
    echo "ERROR: scenario ${scenario_name} did not produce report: ${report_file}" >&2
    exit 1
  fi

  echo "✓ Scenario ${scenario_name} report: ${report_file}"
}

run_scenario "scenario_a_baseline" "40" "8" "1"
run_scenario "scenario_b_ct_disabled" "40" "8" "0"
run_scenario "scenario_c_higher_stats" "80" "16" "1"

echo
echo "All scenarios completed successfully."
echo "Results root: ${OUTPUT_ROOT}"
