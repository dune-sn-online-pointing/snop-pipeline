#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

BASE_CONFIG="${BASE_CONFIG:-${REPO_DIR}/json/example_config.json}"
OUTPUT_ROOT="${OUTPUT_ROOT:-${REPO_DIR}/output/test_pipeline_scenarios}"

SAMPLES_BASE="${SAMPLES_BASE:-/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples}"
NETWORKS_BASE="${NETWORKS_BASE:-/eos/project-e/ep-nu/evilla/sn-online-pointing/neural-networks}"
CAT="${CAT:-cat000001}"
TEST_N_CC="${TEST_N_CC:-40}"
TEST_N_ES="${TEST_N_ES:-8}"

CT_MODEL_DEFAULT="${NETWORKS_BASE}/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras"

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
  local report_selection_mode="$5"
  local report_direction_mode="$6"
  local report_min_energy_mev="$7"
  local report_label="$8"

  local scenario_dir="${OUTPUT_ROOT}/${scenario_name}"
  local scenario_config="${scenario_dir}/config.json"
  mkdir -p "${scenario_dir}"

  python3 - <<'PY' "${BASE_CONFIG}" "${scenario_config}" "${SAMPLES_BASE}" "${CAT}" "${CT_MODEL_DEFAULT}" "${scenario_dir}" "${n_cc}" "${n_es}" "${ct_enabled}" "${report_selection_mode}" "${report_direction_mode}" "${report_min_energy_mev}" "${report_label}"
import json
import sys
from pathlib import Path

base_config, out_config, samples_base, cat, ct_model, scenario_dir, n_cc, n_es, ct_enabled, report_selection_mode, report_direction_mode, report_min_energy_mev, report_label = sys.argv[1:]

with open(base_config, "r") as f:
    cfg = json.load(f)

cat_dir = Path(samples_base) / cat
cluster_candidates = sorted(cat_dir.glob(f"{cat}_cluster_images*/X"))
if not cluster_candidates:
  raise RuntimeError(f"Could not find cluster image X-folder under {cat_dir}")

cluster_x_dir = str(cluster_candidates[0])

cfg["input_data"]["cc_folder"] = cluster_x_dir
cfg["input_data"]["es_folder"] = cluster_x_dir
cfg["input_data"]["file_pattern"] = "*_planeX.npz"
cfg["input_data"]["cc_file_pattern"] = "cc_*_planeX.npz"
cfg["input_data"]["es_file_pattern"] = "es_*_planeX.npz"
cfg["sample_selection"]["n_cc_events"] = int(n_cc)
cfg["sample_selection"]["n_es_events"] = int(n_es)
cfg.setdefault("volume_creation", {})["use_simple_mode"] = True
cfg.setdefault("neural_networks", {}).setdefault("channel_tagger", {})["enabled"] = (ct_enabled == "1")
cfg["neural_networks"]["channel_tagger"]["model_path"] = ct_model
cfg.setdefault("output", {})["base_folder"] = scenario_dir
cfg["output"]["report_file"] = "pipeline_report.pdf"
cfg["reporting"] = {
  "selection_mode": report_selection_mode,
  "direction_mode": report_direction_mode,
  "min_energy_mev": float(report_min_energy_mev),
  "label": report_label,
}

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
  echo "  reporting.selection_mode: ${report_selection_mode}"
  echo "  reporting.direction_mode: ${report_direction_mode}"
  echo "  reporting.min_energy_mev: ${report_min_energy_mev}"
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

run_scenario "scenario_1_best_case" "${TEST_N_CC}" "${TEST_N_ES}" "0" "true-es" "true" "0" "Best Case (true e- dir, true ES)"
run_scenario "scenario_2_perfect_ct" "${TEST_N_CC}" "${TEST_N_ES}" "0" "true-es" "reco" "0" "Perfect CT (true ES, reco dir)"
run_scenario "scenario_3_full_pipeline" "${TEST_N_CC}" "${TEST_N_ES}" "1" "predicted-es" "reco" "0" "Full pipeline (predicted ES)"
run_scenario "scenario_4_weighted_ct" "${TEST_N_CC}" "${TEST_N_ES}" "1" "weighted-ct" "reco" "0" "Weighted CT"
run_scenario "scenario_5_perfect_ct_e_gt_10mev" "${TEST_N_CC}" "${TEST_N_ES}" "0" "true-es" "reco" "10" "Perfect CT (E > 10 MeV)"
run_scenario "scenario_6_perfect_ct_e_gt_5mev" "${TEST_N_CC}" "${TEST_N_ES}" "0" "true-es" "reco" "5" "Perfect CT (E > 5 MeV)"

echo
echo "Generating scenario cos(theta) PDF report..."
python3 "${REPO_DIR}/python/ana/scenario_cos_theta_report.py" \
  --scenarios-root "${OUTPUT_ROOT}" \
  --output-pdf "${OUTPUT_ROOT}/scenario_cos_theta_report.pdf" \
  --selection-mode predicted-es

echo
echo "All scenarios completed successfully."
echo "Results root: ${OUTPUT_ROOT}"
echo "Scenario report: ${OUTPUT_ROOT}/scenario_cos_theta_report.pdf"
