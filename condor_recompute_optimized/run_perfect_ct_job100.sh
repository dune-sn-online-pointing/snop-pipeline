#!/bin/bash
source /cvmfs/sft.cern.ch/lcg/views/LCG_105/x86_64-el9-gcc13-opt/setup.sh
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

for cat in cat000380 cat000381 cat000382 cat000383 cat000384 cat000385 cat000386 cat000387 cat000388 cat000389; do
    echo "Processing $cat for perfect_ct..."
    python3 scripts/run_cat_analysis_emcee_corrected.py \
        --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/${cat}/images \
        --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
        --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
        --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
        --scenarios perfect_ct \
        --nwalkers 128 \
        --nsteps 500 \
        --discard 100 \
        --use-eos-structure
done
