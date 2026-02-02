#!/bin/bash
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

echo "Job 88: Processing 5 categories"
echo "Start time: $(date)"


echo "Processing cat000441..."
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000441 \
    --cat-dir /eos/user/e/evilla/supernova/dataset_9_7_24_with_positions/cat000441 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average_ct \
    --use-eos-structure 2>&1 | grep -E "(cat000441|Angular error|failed|Saved)"

if [ $? -eq 0 ]; then
    echo "✓ cat000441 completed"
else
    echo "✗ cat000441 failed"
fi


echo "Processing cat000442..."
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000442 \
    --cat-dir /eos/user/e/evilla/supernova/dataset_9_7_24_with_positions/cat000442 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average_ct \
    --use-eos-structure 2>&1 | grep -E "(cat000442|Angular error|failed|Saved)"

if [ $? -eq 0 ]; then
    echo "✓ cat000442 completed"
else
    echo "✗ cat000442 failed"
fi


echo "Processing cat000443..."
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000443 \
    --cat-dir /eos/user/e/evilla/supernova/dataset_9_7_24_with_positions/cat000443 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average_ct \
    --use-eos-structure 2>&1 | grep -E "(cat000443|Angular error|failed|Saved)"

if [ $? -eq 0 ]; then
    echo "✓ cat000443 completed"
else
    echo "✗ cat000443 failed"
fi


echo "Processing cat000444..."
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000444 \
    --cat-dir /eos/user/e/evilla/supernova/dataset_9_7_24_with_positions/cat000444 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average_ct \
    --use-eos-structure 2>&1 | grep -E "(cat000444|Angular error|failed|Saved)"

if [ $? -eq 0 ]; then
    echo "✓ cat000444 completed"
else
    echo "✗ cat000444 failed"
fi


echo "Processing cat000445..."
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000445 \
    --cat-dir /eos/user/e/evilla/supernova/dataset_9_7_24_with_positions/cat000445 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average_ct \
    --use-eos-structure 2>&1 | grep -E "(cat000445|Angular error|failed|Saved)"

if [ $? -eq 0 ]; then
    echo "✓ cat000445 completed"
else
    echo "✗ cat000445 failed"
fi


echo "End time: $(date)"
echo "Job completed"
