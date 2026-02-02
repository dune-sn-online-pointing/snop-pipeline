#!/bin/bash
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

echo "Job 78: Processing 5 categories"
echo "Start time: $(date)"


echo "Processing cat000391..."
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000391 \
    --cat-dir /eos/user/e/evilla/supernova/dataset_9_7_24_with_positions/cat000391 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average_ct \
    --use-eos-structure 2>&1 | grep -E "(cat000391|Angular error|failed|Saved)"

if [ $? -eq 0 ]; then
    echo "✓ cat000391 completed"
else
    echo "✗ cat000391 failed"
fi


echo "Processing cat000392..."
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000392 \
    --cat-dir /eos/user/e/evilla/supernova/dataset_9_7_24_with_positions/cat000392 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average_ct \
    --use-eos-structure 2>&1 | grep -E "(cat000392|Angular error|failed|Saved)"

if [ $? -eq 0 ]; then
    echo "✓ cat000392 completed"
else
    echo "✗ cat000392 failed"
fi


echo "Processing cat000393..."
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000393 \
    --cat-dir /eos/user/e/evilla/supernova/dataset_9_7_24_with_positions/cat000393 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average_ct \
    --use-eos-structure 2>&1 | grep -E "(cat000393|Angular error|failed|Saved)"

if [ $? -eq 0 ]; then
    echo "✓ cat000393 completed"
else
    echo "✗ cat000393 failed"
fi


echo "Processing cat000394..."
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000394 \
    --cat-dir /eos/user/e/evilla/supernova/dataset_9_7_24_with_positions/cat000394 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average_ct \
    --use-eos-structure 2>&1 | grep -E "(cat000394|Angular error|failed|Saved)"

if [ $? -eq 0 ]; then
    echo "✓ cat000394 completed"
else
    echo "✗ cat000394 failed"
fi


echo "Processing cat000395..."
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000395 \
    --cat-dir /eos/user/e/evilla/supernova/dataset_9_7_24_with_positions/cat000395 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average_ct \
    --use-eos-structure 2>&1 | grep -E "(cat000395|Angular error|failed|Saved)"

if [ $? -eq 0 ]; then
    echo "✓ cat000395 completed"
else
    echo "✗ cat000395 failed"
fi


echo "End time: $(date)"
echo "Job completed"
