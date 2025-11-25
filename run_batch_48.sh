#!/bin/bash
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

echo "===== Processing cat000481 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000481 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000481 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000482 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000482 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000482 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000483 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000483 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000483 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000484 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000484 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000484 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000485 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000485 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000485 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000486 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000486 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000486 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000487 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000487 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000487 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000488 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000488 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000488 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000489 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000489 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000489 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000490 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000490 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000490 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

