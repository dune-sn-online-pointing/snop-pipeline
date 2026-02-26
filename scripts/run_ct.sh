#!/bin/bash
# Wrapper script to run standalone CT inference with JSON config
# Usage: ./scripts/run_ct.sh -j json/ct_only_example_config.json

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

source "$SCRIPT_DIR/init.sh"

echo ""
echo "Running CT inference..."
echo ""

python3 "$REPO_DIR/scripts/run_ct_inference.py" "$@"
