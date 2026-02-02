#!/bin/bash
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

echo "===== Processing cat000301 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000301 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000301 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000302 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000302 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000302 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000303 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000303 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000303 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000304 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000304 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000304 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000305 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000305 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000305 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000306 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000306 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000306 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000307 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000307 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000307 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000308 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000308 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000308 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000309 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000309 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000309 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000310 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000310 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000310 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

