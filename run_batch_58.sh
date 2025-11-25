#!/bin/bash
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

echo "===== Processing cat000581 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000581 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000581 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000582 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000582 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000582 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000583 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000583 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000583 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000584 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000584 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000584 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000585 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000585 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000585 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000586 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000586 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000586 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000587 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000587 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000587 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000588 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000588 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000588 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000589 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000589 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000589 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

echo "===== Processing cat000590 ====="
/usr/bin/python3 scripts/run_cat_analysis_emcee_corrected.py \
    --cat-name cat000590 \
    --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat000590 \
    --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
    --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
    --pdf-file /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz \
    --scenarios best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev \
    --nwalkers 128 \
    --nsteps 500 \
    --discard 100 \
    --use-eos-structure

