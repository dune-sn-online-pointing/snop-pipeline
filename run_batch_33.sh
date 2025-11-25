#!/bin/bash
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

echo "===== Processing cat000331 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000331 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000331 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000332 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000332 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000332 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000333 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000333 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000333 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000334 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000334 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000334 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000335 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000335 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000335 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000336 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000336 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000336 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000337 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000337 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000337 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000338 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000338 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000338 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000339 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000339 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000339 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000340 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000340 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000340 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

