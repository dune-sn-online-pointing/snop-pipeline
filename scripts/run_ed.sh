#!/bin/bash
# Wrapper script to run ED-only workflow with JSON config
# Usage: ./scripts/run_ed.sh -j json/ed_only_example_config.json

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

source "$SCRIPT_DIR/init.sh"

echo ""
echo "Running ED-only workflow..."
echo ""

python3 "$REPO_DIR/scripts/run_ed_only.py" "$@"
