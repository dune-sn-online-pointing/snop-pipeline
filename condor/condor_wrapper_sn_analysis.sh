#!/bin/bash
# HTCondor wrapper script for GPU-accelerated SN systematic analysis

set -e

echo "=========================================="
echo "SN Systematic Analysis - GPU Job"
echo "=========================================="
echo "Job start: $(date)"
echo "Hostname: $(hostname)"
echo "Working directory: $(pwd)"
echo ""

HOME_DIR="/afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline"
cd $HOME_DIR

# Setup LCG environment
source $HOME_DIR/scripts/init.sh

# Run the systematic analysis
echo "Starting systematic analysis..."
python3 $HOME_DIR/scripts/run_systematic_sn_analysis.py \
  --cat-dir-parent /eos/project-e/ep-nu/public/sn-pointing \
  --energy-cosine-pdf /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/_archive_superseded/three_plane_three_plane_v18_200k_aug_20251112_114654/cosine_energy_pdf.npz \
  --output-dir results/full_598_cats_gpu \
  --n-es 8 \
  --n-cc 80 \
  --run-all \
  --ed-model /eos/user/e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_v14_10k_hyperopt_20251111_175141/checkpoints/model_epoch_62_val_loss_1.1463.keras \
  --mt-model /eos/user/e/evilla/dune/sn-tps/neural_networks/mt_identifier/v26_200k/mt_fixed_20251117_150514/model_best.keras \
  --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras

echo ""
echo "Job completed: $(date)"
