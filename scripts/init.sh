#!/bin/bash
# Initialization script for Data Selection Pipeline
# Sets up environment, paths, and helper functions
# Source this script from other scripts: source $SCRIPTS_DIR/init.sh

# Do not force shell options here (especially `set -e`) because this file is
# sourced by other scripts and interactive shells. Keep initialization robust
# and self-contained instead.

if [[ "${INIT_DONE:-}" == "true" ]]; then
    return 0 2>/dev/null || exit 0
fi

# Get absolute path to the repository root
export SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export REPO_DIR="$(cd "$SCRIPTS_DIR/.." && pwd)"

# Python modules directory
export PYTHON_DIR="$REPO_DIR/python"

# JSON configurations directory
export JSON_DIR="$REPO_DIR/json"

# Default output base directory (can be overridden by environment)
export SNOP_OUTPUT_BASE="${SNOP_OUTPUT_BASE:-$REPO_DIR/output}"

# Submodules directory
export SUBMODULES_DIR="$REPO_DIR/submodules"

# Source LCG environment with CUDA support (same as ml_for_pointing)
LCG_RELEASE="LCG_106_cuda/x86_64-el9-gcc11-opt"
LCG_VIEW="/cvmfs/sft.cern.ch/lcg/views/$LCG_RELEASE"

if [ -f "$LCG_VIEW/setup.sh" ]; then
    _snop_had_u=0
    case $- in
        *u*) _snop_had_u=1; set +u ;;
    esac
    if ! source "$LCG_VIEW/setup.sh"; then
        echo "⚠ Warning: failed to source LCG environment at $LCG_VIEW/setup.sh"
        echo "  Continuing with current Python environment"
    else
        echo "✓ Sourced LCG environment: $LCG_RELEASE"
    fi
    if [ "$_snop_had_u" -eq 1 ]; then
        set -u
    fi
else
    echo "⚠ Warning: LCG environment not found at $LCG_VIEW"
    echo "  Using system Python instead"
fi

# Add Python modules to PYTHONPATH
export PYTHONPATH="$PYTHON_DIR:$PYTHONPATH"

# Add Python app modules to PYTHONPATH
if [ -d "$PYTHON_DIR/app" ]; then
    export PYTHONPATH="$PYTHON_DIR/app:$PYTHONPATH"
fi

# Add local packages to PYTHONPATH if it exists
if [ -d "$REPO_DIR/local_packages" ]; then
    export PYTHONPATH="$REPO_DIR/local_packages:$PYTHONPATH"
    echo "✓ Added local_packages to PYTHONPATH"
fi

# Add online-pointing-utils to PYTHONPATH if it exists
if [ -d "$SUBMODULES_DIR/online-pointing-utils/python" ]; then
    export PYTHONPATH="$SUBMODULES_DIR/online-pointing-utils/python:$PYTHONPATH"
    echo "✓ Added online-pointing-utils to PYTHONPATH"
fi

# Helper function to print colored messages
print_info() {
    echo -e "\033[0;34m[INFO]\033[0m $1"
}

print_success() {
    echo -e "\033[0;32m[SUCCESS]\033[0m $1"
}

print_warning() {
    echo -e "\033[0;33m[WARNING]\033[0m $1"
}

print_error() {
    echo -e "\033[0;31m[ERROR]\033[0m $1"
}

# Helper function to check if a file exists
check_file() {
    if [ ! -f "$1" ]; then
        print_error "File not found: $1"
        exit 1
    fi
}

# Helper function to check if a directory exists
check_dir() {
    if [ ! -d "$1" ]; then
        print_error "Directory not found: $1"
        exit 1
    fi
}

# Helper function to create output directory if it doesn't exist
ensure_dir() {
    if [ ! -d "$1" ]; then
        mkdir -p "$1"
        print_info "Created directory: $1"
    fi
}

# Print environment information
print_info "Data Selection Pipeline Environment"
print_info "Repository: $REPO_DIR"
print_info "Python modules: $PYTHON_DIR"
print_info "JSON configs: $JSON_DIR"
print_info "Output base (SNOP_OUTPUT_BASE): $SNOP_OUTPUT_BASE"

# Check Python version
if command -v python3 >/dev/null 2>&1; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    print_info "Python version: $PYTHON_VERSION"
else
    print_warning "python3 not found in PATH"
fi

# Optionally skip dependency probes in non-interactive runs to avoid slow imports.
if [[ "${SNOP_SKIP_DEP_CHECKS:-0}" == "1" ]]; then
    print_info "Skipping TensorFlow/scikit-learn dependency probes (SNOP_SKIP_DEP_CHECKS=1)"
else
    # Check if TensorFlow is available
    if command -v python3 >/dev/null 2>&1 && python3 -c "import tensorflow" 2>/dev/null; then
        TF_VERSION=$(python3 -c "import tensorflow as tf; print(tf.__version__)" 2>/dev/null)
        print_success "TensorFlow $TF_VERSION is available"
    else
        print_warning "TensorFlow is not available"
    fi

    # Check if scikit-learn is available
    if command -v python3 >/dev/null 2>&1 && python3 -c "import sklearn" 2>/dev/null; then
        SKLEARN_VERSION=$(python3 -c "import sklearn; print(sklearn.__version__)" 2>/dev/null)
        print_success "scikit-learn $SKLEARN_VERSION is available"
    else
        print_warning "scikit-learn is not available"
    fi
fi

export INIT_DONE=true
