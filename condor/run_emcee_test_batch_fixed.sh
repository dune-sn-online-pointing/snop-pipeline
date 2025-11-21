#!/bin/bash

# Fixed batch script to run emcee analysis on 5 test cats

CATS=("cat000001" "cat000002" "cat000003" "cat000013" "cat000062")

ED_MODEL="/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras"
PDF_FILE="/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz"

for CAT in "${CATS[@]}"; do
    echo ""
    echo "=================================================================="
    echo "Processing $CAT..."
    echo "=================================================================="
    
    CAT_DIR="/eos/project-e/ep-nu/evilla/sn-pointing/$CAT"
    
    python3 scripts/run_cat_analysis_emcee_fixed.py \
        --cat-name $CAT \
        --cat-dir $CAT_DIR \
        --ed-model $ED_MODEL \
        --pdf-file $PDF_FILE \
        --nwalkers 32 \
        --nsteps 1000 \
        --discard 200 \
        --use-eos-structure
    
    if [ $? -eq 0 ]; then
        echo "✓ $CAT completed successfully"
    else
        echo "✗ $CAT failed"
    fi
done

echo ""
echo "=================================================================="
echo "All cats processed! Now comparing results..."
echo "=================================================================="
