#!/bin/bash
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

echo "Job 87: Processing 5 categories"
echo "Start time: $(date)"


echo "Processing cat000436..."
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000436 \
    --cat-dir /eos/user/e/evilla/supernova/dataset_9_7_24_with_positions/cat000436 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average_ct \
    --use-eos-structure 2>&1 | grep -E "(cat000436|Angular error|failed|Saved)"

if [ $? -eq 0 ]; then
    echo "✓ cat000436 completed"
else
    echo "✗ cat000436 failed"
fi


echo "Processing cat000437..."
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000437 \
    --cat-dir /eos/user/e/evilla/supernova/dataset_9_7_24_with_positions/cat000437 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average_ct \
    --use-eos-structure 2>&1 | grep -E "(cat000437|Angular error|failed|Saved)"

if [ $? -eq 0 ]; then
    echo "✓ cat000437 completed"
else
    echo "✗ cat000437 failed"
fi


echo "Processing cat000438..."
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000438 \
    --cat-dir /eos/user/e/evilla/supernova/dataset_9_7_24_with_positions/cat000438 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average_ct \
    --use-eos-structure 2>&1 | grep -E "(cat000438|Angular error|failed|Saved)"

if [ $? -eq 0 ]; then
    echo "✓ cat000438 completed"
else
    echo "✗ cat000438 failed"
fi


echo "Processing cat000439..."
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000439 \
    --cat-dir /eos/user/e/evilla/supernova/dataset_9_7_24_with_positions/cat000439 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average_ct \
    --use-eos-structure 2>&1 | grep -E "(cat000439|Angular error|failed|Saved)"

if [ $? -eq 0 ]; then
    echo "✓ cat000439 completed"
else
    echo "✗ cat000439 failed"
fi


echo "Processing cat000440..."
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000440 \
    --cat-dir /eos/user/e/evilla/supernova/dataset_9_7_24_with_positions/cat000440 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average_ct \
    --use-eos-structure 2>&1 | grep -E "(cat000440|Angular error|failed|Saved)"

if [ $? -eq 0 ]; then
    echo "✓ cat000440 completed"
else
    echo "✗ cat000440 failed"
fi


echo "End time: $(date)"
echo "Job completed"
