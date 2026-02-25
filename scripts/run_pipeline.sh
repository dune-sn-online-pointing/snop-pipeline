#!/bin/bash
# Wrapper script to run the pipeline with proper environment
# Usage: ./scripts/run_pipeline.sh --config json/my_config.json [other options]

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source the environment
source "$SCRIPT_DIR/init.sh"

echo ""
echo "Running Data Selection Pipeline..."
echo ""

# Run the pipeline with all arguments passed through
python3 "$REPO_DIR/python/app/pipeline.py" "$@"
