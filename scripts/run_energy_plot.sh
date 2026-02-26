#!/bin/bash
# Wrapper script to aggregate neutrino energies with JSON config
# Usage: ./scripts/run_energy_plot.sh -j json/neutrino_energy_100cats_config.json

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

source "$SCRIPT_DIR/init.sh"

echo ""
echo "Running neutrino energy aggregation plot..."
echo ""

python3 "$REPO_DIR/python/ana/plot_neutrino_energy.py" "$@"
