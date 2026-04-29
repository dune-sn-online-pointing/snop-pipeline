#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${REPO_DIR}/scripts/init.sh"

BASE_CONFIG="${BASE_CONFIG:-${REPO_DIR}/json/example_config.json}"
OUTPUT_ROOT="${OUTPUT_ROOT:-${REPO_DIR}/output/test_pipeline_scenarios}"
PRUNE_SCENARIO_OUTPUTS="${PRUNE_SCENARIO_OUTPUTS:-1}"
SCENARIO_CATALOG="${SCENARIO_CATALOG:-${REPO_DIR}/json/six_scenarios.json}"
SCENARIO_NAMES="${SCENARIO_NAMES:-}"

SAMPLES_BASE="${SAMPLES_BASE:-/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples}"
NETWORKS_BASE="${NETWORKS_BASE:-/eos/project-e/ep-nu/evilla/sn-online-pointing/neural-networks}"
CAT="${CAT:-cat000001}"
TEST_N_CC="${TEST_N_CC:-3300}"
TEST_N_ES="${TEST_N_ES:-330}"

CT_MODEL_DEFAULT="${NETWORKS_BASE}/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras"

if [[ ! -f "${BASE_CONFIG}" ]]; then
  echo "ERROR: base config not found: ${BASE_CONFIG}" >&2
  exit 1
fi

if [[ ! -f "${SCENARIO_CATALOG}" ]]; then
  echo "ERROR: scenario catalog not found: ${SCENARIO_CATALOG}" >&2
  exit 1
fi

mkdir -p "${OUTPUT_ROOT}"

run_scenario() {
  local scenario_name="$1"
  local n_cc="$2"
  local n_es="$3"
  local ct_enabled="$4"
  local ct_threshold="$5"
  local report_selection_mode="$6"
  local report_direction_mode="$7"
  local report_min_energy_mev="$8"
  local report_label="$9"

  local scenario_dir="${OUTPUT_ROOT}/${scenario_name}"
  local scenario_config="${scenario_dir}/config.json"
  mkdir -p "${scenario_dir}"

  python3 - <<'PY' "${BASE_CONFIG}" "${scenario_config}" "${SAMPLES_BASE}" "${CAT}" "${CT_MODEL_DEFAULT}" "${scenario_dir}" "${n_cc}" "${n_es}" "${ct_enabled}" "${ct_threshold}" "${report_selection_mode}" "${report_direction_mode}" "${report_min_energy_mev}" "${report_label}"
import json
import sys
from pathlib import Path

base_config, out_config, samples_base, cat, ct_model, scenario_dir, n_cc, n_es, ct_enabled, ct_threshold, report_selection_mode, report_direction_mode, report_min_energy_mev, report_label = sys.argv[1:]

with open(base_config, "r") as f:
    cfg = json.load(f)

cat_dir = Path(samples_base) / cat
cluster_candidates = sorted(cat_dir.glob(f"{cat}_cluster_images*/X"))
if not cluster_candidates:
  raise RuntimeError(f"Could not find cluster image X-folder under {cat_dir}")

# Use base folder (parent of X/) for 3-plane matching via match_id (column 13)
cluster_base_dir = str(cluster_candidates[0].parent)

# Volume images (large format for CT model)
vol_candidates = sorted(cat_dir.glob(f"{cat}_volume_images*/X"))
vol_base_dir = str(vol_candidates[0].parent) if vol_candidates else None

cfg["input_data"]["cc_folder"] = cluster_base_dir
cfg["input_data"]["es_folder"] = cluster_base_dir
if vol_base_dir:
  cfg["input_data"]["cc_vol_folder"] = vol_base_dir
  cfg["input_data"]["es_vol_folder"] = vol_base_dir
cfg["input_data"]["file_pattern"] = "*_bg_matched_planeX.npz"
cfg["input_data"]["cc_file_pattern"] = "cc_*_bg_matched_planeX.npz"
cfg["input_data"]["es_file_pattern"] = "es_*_bg_matched_planeX.npz"
cfg["input_data"]["load_all_planes"] = True  # Enable proper 3-plane matching
cfg["sample_selection"]["n_cc_events"] = int(n_cc)
cfg["sample_selection"]["n_es_events"] = int(n_es)
cfg.setdefault("volume_creation", {})["use_simple_mode"] = True
cfg.setdefault("neural_networks", {}).setdefault("channel_tagger", {})["enabled"] = (ct_enabled == "1")
cfg["neural_networks"]["channel_tagger"]["model_path"] = ct_model
cfg["neural_networks"]["channel_tagger"]["threshold"] = float(ct_threshold)
# Disable ED reconstruction for scenarios that use true directions
cfg.setdefault("neural_networks", {}).setdefault("electron_direction", {})["enabled"] = (report_direction_mode != "true")
cfg.setdefault("output", {})["base_folder"] = scenario_dir
cfg["output"]["report_file"] = "pipeline_report.pdf"
cfg["reporting"] = {
  "selection_mode": report_selection_mode,
  "direction_mode": report_direction_mode,
  "min_energy_mev": float(report_min_energy_mev),
  "ct_threshold": float(ct_threshold),
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
  echo "  channel_tagger.threshold: ${ct_threshold}"
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

echo "Reading scenario catalog: ${SCENARIO_CATALOG}"
if [[ -n "${SCENARIO_NAMES}" ]]; then
  echo "Applying scenario filter: ${SCENARIO_NAMES}"
fi

mapfile -t SCENARIO_ROWS < <(python3 - <<'PY' "${SCENARIO_CATALOG}" "${SCENARIO_NAMES}"
import json
import sys

catalog_path = sys.argv[1]
scenario_filter = sys.argv[2]

with open(catalog_path, "r") as f:
    catalog = json.load(f)

requested = None
if scenario_filter.strip():
    requested = [name.strip() for name in scenario_filter.split(",") if name.strip()]
    if not requested:
        raise RuntimeError("SCENARIO_NAMES was provided but no valid names were parsed")

scenarios = catalog.get("scenarios", [])
if not scenarios:
    raise RuntimeError(f"No scenarios found in catalog: {catalog_path}")

index = {item.get("name"): item for item in scenarios if item.get("name")}

selected = scenarios
if requested is not None:
    missing = [name for name in requested if name not in index]
    if missing:
        raise RuntimeError(
            f"Requested scenarios not found in catalog: {', '.join(missing)}"
        )
    selected = [index[name] for name in requested]

for item in selected:
    name = item["name"]
    ct_enabled = "1" if bool(item.get("channel_tagger_enabled", False)) else "0"
    ct_threshold = str(float(item.get("channel_tagger_threshold", 0.5)))
    selection_mode = str(item.get("report_selection_mode", "predicted-es"))
    direction_mode = str(item.get("report_direction_mode", "reco"))
    min_energy = str(float(item.get("report_min_energy_mev", 3.0)))
    label = str(item.get("report_label", name))
    print("\t".join([
        name,
        ct_enabled,
        ct_threshold,
        selection_mode,
        direction_mode,
        min_energy,
        label,
    ]))
PY
)

if [[ "${#SCENARIO_ROWS[@]}" -eq 0 ]]; then
  echo "ERROR: scenario catalog produced zero runnable scenarios" >&2
  exit 1
fi

echo "Running ${#SCENARIO_ROWS[@]} scenario(s)"
for row in "${SCENARIO_ROWS[@]}"; do
  IFS=$'\t' read -r scenario_name ct_enabled ct_threshold report_selection_mode report_direction_mode report_min_energy_mev report_label <<< "${row}"
  run_scenario "${scenario_name}" "${TEST_N_CC}" "${TEST_N_ES}" "${ct_enabled}" "${ct_threshold}" "${report_selection_mode}" "${report_direction_mode}" "${report_min_energy_mev}" "${report_label}"
done

echo
echo "Generating scenario cos(theta) PDF report..."

# Extract MCMC parameters from BASE_CONFIG to avoid hardcoding
SCENARIO_CONFIG="${OUTPUT_ROOT}/scenario_analysis_config.json"

# Read MCMC config from BASE_CONFIG JSON
BASE_CONFIG_PATH="${BASE_CONFIG:-${REPO_DIR}/json/example_config.json}"
echo "Reading MCMC config from: ${BASE_CONFIG_PATH}"

EMCEE_CONFIG=$(python3 -c "
import json
import sys
try:
    with open('${BASE_CONFIG_PATH}', 'r') as f:
        config = json.load(f)
    emcee = config.get('analysis', {}).get('emcee', {})
    # Ensure enabled is set
    emcee['enabled'] = emcee.get('enabled', True)
    print(json.dumps(emcee, indent=6))
except Exception as e:
    print(f'Error reading {BASE_CONFIG_PATH}: {e}', file=sys.stderr)
    # Fallback to corrected defaults if config read fails
    fallback = {
        'enabled': True,
        'nwalkers': 128,
        'nsteps': 500,
        'discard': 100,
        'prior_kappa': 25.0,
        'likelihood_kappa': 25.0,
        'random_seed': 42
    }
    print(json.dumps(fallback, indent=6))
")

# Generate scenario config with MCMC params from BASE_CONFIG
cat > "${SCENARIO_CONFIG}" << EOF
{
  "analysis": {
    "scenarios_root": "${OUTPUT_ROOT}",
    "output_pdf": "${OUTPUT_ROOT}/scenario_cos_theta_report.pdf",
    "selection_mode": "predicted-es",
    "min_energy_mev": 3.0,
    "emcee": ${EMCEE_CONFIG},
    "pdf_path": "${REPO_DIR}/data/cosine_energy_pdf.npz",
    "description": "Scenario analysis reading MCMC config from ${BASE_CONFIG_PATH}"
  }
}
EOF

echo "Generated scenario config with MCMC parameters from ${BASE_CONFIG_PATH}"

python3 "${REPO_DIR}/python/ana/scenario_cos_theta_report.py" "${SCENARIO_CONFIG}"

# Save scenario reports JSON before pruning
if [[ "${PRUNE_SCENARIO_OUTPUTS}" == "1" ]]; then
  echo
  echo "Saving scenario JSON reports and pruning intermediate files..."
  # Copy the JSON reports to root
  for scenario_dir in "${OUTPUT_ROOT}"/scenario_*/; do
    if [[ -f "${scenario_dir}/pipeline_run_"*/metrics.json ]]; then
      scenario_name=$(basename "$scenario_dir")
      # Keep metrics for reference
      find "${scenario_dir}" -name "metrics.json" -exec cp {} "${OUTPUT_ROOT}/${scenario_name}_metrics.json" \;
    fi
  done
  # Delete large intermediate files but keep the aggregated report
  find "${OUTPUT_ROOT}" -path "*/volume_images/*" -type f -delete
  find "${OUTPUT_ROOT}" -path "*/selected_clusters/*" -type f -delete
  find "${OUTPUT_ROOT}" -path "*/plots/*" -type f -delete
  find "${OUTPUT_ROOT}" -path "*/predictions/*" -type f -delete
  # Finally remove scenario directories
  find "${OUTPUT_ROOT}" -mindepth 1 -maxdepth 1 -type d -name 'scenario_*' -exec rm -rf {} +
fi

echo
echo "All scenarios completed successfully."
echo "Results root: ${OUTPUT_ROOT}"
echo "Scenario report: ${OUTPUT_ROOT}/scenario_cos_theta_report.pdf"
