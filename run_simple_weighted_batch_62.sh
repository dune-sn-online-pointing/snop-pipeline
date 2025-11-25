#!/bin/bash

/usr/bin/python3 /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline/scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000621 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000621 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average weighted_average \
    --use-eos-structure

/usr/bin/python3 /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline/scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000622 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000622 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios simple_average weighted_average \
    --use-eos-structure

