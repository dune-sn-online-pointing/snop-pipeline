#!/bin/bash
# Run emcee analysis on 5 test cats

CATS=("cat000001" "cat000002" "cat000003" "cat000013" "cat000062")

PDF_PATH="/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz"
ED_MODEL="/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras"

echo "=================================================================="
echo "Running emcee analysis on 5 test cats"
echo "=================================================================="
echo ""

for cat in "${CATS[@]}"; do
    echo "Processing $cat..."
    python3 scripts/run_cat_analysis_emcee.py \
        --cat-name "$cat" \
        --pdf-path "$PDF_PATH" \
        --ed-model "$ED_MODEL" \
        --scenarios perfect_ct \
        --use-eos-structure \
        --nwalkers 32 \
        --nsteps 1000 \
        --discard 200
    
    if [ $? -eq 0 ]; then
        echo "✓ $cat completed successfully"
    else
        echo "✗ $cat failed"
    fi
    echo ""
done

echo "=================================================================="
echo "All cats processed! Now comparing results..."
echo "=================================================================="
