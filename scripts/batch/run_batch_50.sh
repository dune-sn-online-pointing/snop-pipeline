#!/bin/bash
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

echo "===== Processing cat000501 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000501 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000501 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000502 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000502 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000502 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000503 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000503 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000503 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000504 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000504 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000504 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000505 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000505 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000505 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000506 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000506 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000506 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000507 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000507 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000507 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000508 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000508 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000508 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000509 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000509 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000509 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000510 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000510 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000510 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

