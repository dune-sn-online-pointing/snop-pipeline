#!/bin/bash
#SBATCH --job-name=mt_inference_multicats
#SBATCH --output=logs/mt_inference_multicats_%A_%a.out
#SBATCH --error=logs/mt_inference_multicats_%A_%a.err
#SBATCH --time=4:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=8GB
#SBATCH --partition=longlunch
#SBATCH --array=0-9

# List of cats to process (same as run_inference_multiple_cats.sh)
CATS=(
    cat000001
    cat000002
    cat000003
    cat000005
    cat000010
    cat000020
    cat000050
    cat000100
    cat000200
    cat000300
)

# Get the cat for this array task
CAT=${CATS[$SLURM_ARRAY_TASK_ID]}

echo "========================================"
echo "Processing: $CAT"
echo "Task ID: $SLURM_ARRAY_TASK_ID"
echo "========================================"

# Setup environment
source /cvmfs/sft.cern.ch/lcg/views/LCG_106_cuda/x86_64-el9-gcc11-opt/setup.sh

cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

MODEL_DIR="/eos/user/e/evilla/dune/sn-tps/neural_networks/mt_identifier/v10_100k_nov13/mt_identifier_simple_cnn_20251113_145400"
DATA_BASE="/eos/project-e/ep-nu/public/sn-pointing"
OUTPUT_BASE="results"

CLUSTER_DIR="${DATA_BASE}/${CAT}/${CAT}_cluster_images_20250115/X"
OUTPUT_DIR="${OUTPUT_BASE}/mt_inference_${CAT}_v10"

# Check if cluster directory exists
if [ ! -d "$CLUSTER_DIR" ]; then
    echo "ERROR: Directory not found: $CLUSTER_DIR"
    exit 1
fi

# Count files
NUM_FILES=$(ls "$CLUSTER_DIR" | wc -l)
echo "Found $NUM_FILES files in $CLUSTER_DIR"

if [ $NUM_FILES -eq 0 ]; then
    echo "ERROR: No files found in $CLUSTER_DIR"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"
mkdir -p logs

# Run inference
python scripts/run_mt_inference.py \
    --model-dir "$MODEL_DIR" \
    --data-dir "$CLUSTER_DIR" \
    --output-dir "$OUTPUT_DIR" \
    --batch-size 256

if [ $? -eq 0 ]; then
    echo "✓ Inference completed for $CAT"
    
    # Generate analysis report
    python python/ana/analyze_mt_predictions.py --cat "$CAT"
    
    if [ $? -eq 0 ]; then
        echo "✓ Analysis report generated for $CAT"
    else
        echo "✗ Analysis failed for $CAT"
        exit 1
    fi
else
    echo "✗ Inference failed for $CAT"
    exit 1
fi

echo "========================================"
echo "Completed: $CAT"
echo "========================================"
