#!/bin/bash
# Wrapper script to generate scenario cos(theta) PDF report
# Usage: ./scripts/run_scenario_report.sh [--scenarios-root output/test_pipeline_scenarios] [--output-pdf output/test_pipeline_scenarios/scenario_cos_theta_report.pdf]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

source "$SCRIPT_DIR/init.sh"

echo ""
echo "Running scenario cos(theta) report..."
echo ""

python3 "$REPO_DIR/python/ana/scenario_cos_theta_report.py" "$@"
