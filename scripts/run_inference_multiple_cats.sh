#!/bin/bash
#
# Run MT inference on multiple cat directories
#

# List of cats to process (subset for testing)
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

MODEL_DIR="/eos/user/e/evilla/dune/sn-tps/neural_networks/mt_identifier/v10_100k_nov13/mt_identifier_simple_cnn_20251113_145400"
DATA_BASE="/eos/project-e/ep-nu/public/sn-pointing"
OUTPUT_BASE="results"

echo "Running MT inference on ${#CATS[@]} cat directories..."

for CAT in "${CATS[@]}"; do
    echo ""
    echo "========================================"
    echo "Processing: $CAT"
    echo "========================================"
    
    CLUSTER_DIR="${DATA_BASE}/${CAT}/${CAT}_cluster_images_20250115/X"
    OUTPUT_DIR="${OUTPUT_BASE}/mt_inference_${CAT}_v10"
    
    # Check if cluster directory exists
    if [ ! -d "$CLUSTER_DIR" ]; then
        echo "WARNING: Directory not found: $CLUSTER_DIR"
        echo "Skipping $CAT"
        continue
    fi
    
    # Count files
    NUM_FILES=$(ls "$CLUSTER_DIR" | wc -l)
    echo "Found $NUM_FILES files in $CLUSTER_DIR"
    
    if [ $NUM_FILES -eq 0 ]; then
        echo "WARNING: No files found, skipping $CAT"
        continue
    fi
    
    mkdir -p "$OUTPUT_DIR"
    
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
        fi
    else
        echo "✗ Inference failed for $CAT"
    fi
done

echo ""
echo "========================================"
echo "All cats processed!"
echo "========================================"
