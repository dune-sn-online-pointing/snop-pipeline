#!/bin/bash
# Test script to verify all modules can be imported
# This sources the proper environment first

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source the environment
source "$REPO_DIR/scripts/init.sh"

echo ""
echo "Running Python module tests..."
echo ""

# Run the Python test script
python3 "$SCRIPT_DIR/test_modules.py"
