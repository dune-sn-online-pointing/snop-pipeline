#!/usr/bin/env bash
# Self-contained unit test: runs the full pipeline code path using synthetic
# data committed in test/inputs/. No EOS access, no ML model files required.
# CT and ED inference steps are disabled; burst-direction uses true-ES + true direction.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
source "${REPO_DIR}/scripts/init.sh"

CONFIG="${REPO_DIR}/json/unit_test_config.json"
SCENARIOS_ROOT="${REPO_DIR}/test/output/unit_test"
SCENARIO_DIR="${SCENARIOS_ROOT}/scenario_unit_test"

echo "=== Unit test: pipeline (no models, synthetic inputs) ==="
mkdir -p "${SCENARIO_DIR}"

# Write a per-run config that points output into the scenario subdir
# and includes the reporting section required by scenario_cos_theta_report.py
RUN_CFG="${SCENARIO_DIR}/config.json"
python3 - << PYEOF
import json
with open("${CONFIG}") as f:
    cfg = json.load(f)
cfg["output"]["base_folder"] = "${SCENARIO_DIR}"
cfg["reporting"] = {
    "selection_mode": "true-es",
    "direction_mode": "true",
    "min_energy_mev": 0.0,
    "ct_threshold": 0.5,
    "label": "Unit test (true ES, true dir)"
}
with open("${RUN_CFG}", "w") as f:
    json.dump(cfg, f, indent=2)
PYEOF

python3 "${REPO_DIR}/python/app/pipeline.py" -j "${RUN_CFG}"

LATEST_RUN="$(ls -1dt "${SCENARIO_DIR}"/pipeline_run_* 2>/dev/null | head -n1 || true)"
if [[ -z "${LATEST_RUN}" ]]; then
  echo "ERROR: pipeline produced no pipeline_run_* folder" >&2
  exit 1
fi
for f in "${LATEST_RUN}/metrics.json" "${LATEST_RUN}/pipeline_report.pdf"; do
  if [[ ! -f "${f}" ]]; then
    echo "ERROR: missing artifact: ${f}" >&2
    exit 1
  fi
done
echo "✓ pipeline artifacts present"

echo ""
echo "=== Unit test: burst-direction report ==="
SCENARIO_REPORT_CFG="${SCENARIOS_ROOT}/scenario_report_cfg.json"
cat > "${SCENARIO_REPORT_CFG}" << JSEOF
{
  "analysis": {
    "scenarios_root": "${SCENARIOS_ROOT}",
    "output_pdf": "${SCENARIOS_ROOT}/unit_test_scenario_report.pdf",
    "selection_mode": "true-es",
    "min_energy_mev": 0.0,
    "emcee": {
      "enabled": true,
      "nwalkers": 8,
      "nsteps": 30,
      "discard": 5,
      "prior_type": "uniform",
      "random_seed": 42
    },
    "pdf_path": "${REPO_DIR}/data/cosine_energy_pdf.npz"
  }
}
JSEOF

python3 "${REPO_DIR}/python/ana/scenario_cos_theta_report.py" "${SCENARIO_REPORT_CFG}"

if [[ ! -f "${SCENARIOS_ROOT}/unit_test_scenario_report.pdf" ]]; then
  echo "ERROR: scenario report PDF not produced" >&2
  exit 1
fi
echo "✓ scenario report produced"

echo ""
echo "Unit test passed."
