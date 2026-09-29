#!/usr/bin/env bash
# condor wrapper: ES pdf vs the NEUTRINO axis, P(cos(reco, nu) | E_reco), from the ES cluster images of
# cats 1-100 (read-only; out-of-sample for the dev cats 623-672), ED v58 via ed_inference.py.
set -euo pipefail
source /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/scripts/init.sh
cd /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline
python3 python/ana/build_cc_cosine_pdf.py \
  --cluster-folders-glob '/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples/cat0000[0-9][0-9]/cat0000[0-9][0-9]_cluster_images_tick3_ch2_min2_tot3_e3p0' \
  --file-pattern 'es_*_matched_planeX.npz' --sample-type ES \
  --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras \
  --reference-pdf /afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/data/cosine_energy_pdf.npz \
  --work-dir /eos/user/e/evilla/dune/sn-tps/mixture_dev_prodcc/es_nu/work \
  --out /eos/user/e/evilla/dune/sn-tps/mixture_dev_prodcc/es_nu/cosine_energy_pdf_es_nu.npz --png /eos/user/e/evilla/dune/sn-tps/mixture_dev_prodcc/es_nu/cosine_energy_pdf_es_nu.png --events-out /eos/user/e/evilla/dune/sn-tps/mixture_dev_prodcc/es_nu/es_ed_events.npz
