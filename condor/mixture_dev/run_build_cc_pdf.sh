#!/usr/bin/env bash
# condor wrapper: ED v58 inference on the prod_cc matched clusters and CC pdf table (writes to user EOS)
set -euo pipefail
source /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/scripts/init.sh
cd /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline
python3 python/ana/build_cc_cosine_pdf.py \
  --cluster-folder /eos/user/e/evilla/dune/sn-tps/mixture_dev_prodcc/neighbourAPA_cc_bg_cluster_images_tick3_ch2_min2_tot3_e3p0 \
  --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
  --reference-pdf /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/data/cosine_energy_pdf.npz \
  --work-dir /eos/user/e/evilla/dune/sn-tps/mixture_dev_prodcc/work \
  --out /eos/user/e/evilla/dune/sn-tps/mixture_dev_prodcc/cosine_energy_pdf_cc.npz --png /eos/user/e/evilla/dune/sn-tps/mixture_dev_prodcc/cosine_energy_pdf_cc.png --events-out /eos/user/e/evilla/dune/sn-tps/mixture_dev_prodcc/cc_ed_events.npz
