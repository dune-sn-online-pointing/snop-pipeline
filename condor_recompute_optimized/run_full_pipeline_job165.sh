#!/bin/bash
source /cvmfs/sft.cern.ch/lcg/views/LCG_105/x86_64-el9-gcc13-opt/setup.sh
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

for cat in cat000410 cat000411 cat000412 cat000413 cat000414 cat000415 cat000416 cat000417 cat000418 cat000419; do
    echo "Processing $cat for full_pipeline..."
    python3 scripts/run_cat_analysis_emcee_corrected.py \
        --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/${cat}/images \
        --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
        --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
        --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
        --scenarios full_pipeline \
        --nwalkers 128 \
        --nsteps 500 \
        --discard 100 \
        --use-eos-structure
done
