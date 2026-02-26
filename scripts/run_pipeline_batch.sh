#!/bin/bash
# Wrapper script to run the full pipeline across many CAT datasets from JSON config
# Usage: ./scripts/run_pipeline_batch.sh -j json/pipeline_100cats_config.json

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

source "$SCRIPT_DIR/init.sh"

echo ""
echo "Running batch whole-pipeline..."
echo ""

python3 "$REPO_DIR/scripts/run_pipeline_batch.py" "$@"
