#!/bin/bash
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

echo "Job 20: Processing 5 categories"
echo "Start time: $(date)"


echo "Processing cat000101..."
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000101 \
    --cat-dir /eos/user/e/evilla/supernova/dataset_9_7_24_with_positions/cat000101 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average_ct \
    --use-eos-structure 2>&1 | grep -E "(cat000101|Angular error|failed|Saved)"

if [ $? -eq 0 ]; then
    echo "✓ cat000101 completed"
else
    echo "✗ cat000101 failed"
fi


echo "Processing cat000102..."
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000102 \
    --cat-dir /eos/user/e/evilla/supernova/dataset_9_7_24_with_positions/cat000102 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average_ct \
    --use-eos-structure 2>&1 | grep -E "(cat000102|Angular error|failed|Saved)"

if [ $? -eq 0 ]; then
    echo "✓ cat000102 completed"
else
    echo "✗ cat000102 failed"
fi


echo "Processing cat000103..."
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000103 \
    --cat-dir /eos/user/e/evilla/supernova/dataset_9_7_24_with_positions/cat000103 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average_ct \
    --use-eos-structure 2>&1 | grep -E "(cat000103|Angular error|failed|Saved)"

if [ $? -eq 0 ]; then
    echo "✓ cat000103 completed"
else
    echo "✗ cat000103 failed"
fi


echo "Processing cat000104..."
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000104 \
    --cat-dir /eos/user/e/evilla/supernova/dataset_9_7_24_with_positions/cat000104 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average_ct \
    --use-eos-structure 2>&1 | grep -E "(cat000104|Angular error|failed|Saved)"

if [ $? -eq 0 ]; then
    echo "✓ cat000104 completed"
else
    echo "✗ cat000104 failed"
fi


echo "Processing cat000105..."
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000105 \
    --cat-dir /eos/user/e/evilla/supernova/dataset_9_7_24_with_positions/cat000105 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average_ct \
    --use-eos-structure 2>&1 | grep -E "(cat000105|Angular error|failed|Saved)"

if [ $? -eq 0 ]; then
    echo "✓ cat000105 completed"
else
    echo "✗ cat000105 failed"
fi


echo "End time: $(date)"
echo "Job completed"
