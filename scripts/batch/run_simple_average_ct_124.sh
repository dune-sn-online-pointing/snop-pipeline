#!/bin/bash
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

echo "Job 124: Processing 2 categories"
echo "Start time: $(date)"


echo "Processing cat000621..."
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000621 \
    --cat-dir /eos/user/e/evilla/supernova/dataset_9_7_24_with_positions/cat000621 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average_ct \
    --use-eos-structure 2>&1 | grep -E "(cat000621|Angular error|failed|Saved)"

if [ $? -eq 0 ]; then
    echo "✓ cat000621 completed"
else
    echo "✗ cat000621 failed"
fi


echo "Processing cat000622..."
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000622 \
    --cat-dir /eos/user/e/evilla/supernova/dataset_9_7_24_with_positions/cat000622 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average_ct \
    --use-eos-structure 2>&1 | grep -E "(cat000622|Angular error|failed|Saved)"

if [ $? -eq 0 ]; then
    echo "✓ cat000622 completed"
else
    echo "✗ cat000622 failed"
fi


echo "End time: $(date)"
echo "Job completed"
