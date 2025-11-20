#!/bin/bash

# Set up environment
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

SCENARIO=$1

echo "Starting scenario ${SCENARIO} with improved MCMC and 3 MeV energy cut..."

# Run scenario
python3 scripts/run_cat000001_full_analysis.py \
    --pdf-path /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --scenarios ${SCENARIO} \
    --output results/cat000001_scenario_${SCENARIO}.npz

echo "Scenario ${SCENARIO} completed with exit code: $?"
