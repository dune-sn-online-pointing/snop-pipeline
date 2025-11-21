#!/bin/bash
# Wrapper for SN analysis batch 115

set -e

echo "=========================================="
echo "SN Analysis Batch 115"
echo "Categories: cat000600,cat000601,cat000602,cat000603,cat000604"
echo "=========================================="
echo "Job start: $(date)"
echo "Hostname: $(hostname)"

# Setup LCG environment
echo "Setting up LCG environment..."
source /cvmfs/sft.cern.ch/lcg/views/LCG_106_cuda/x86_64-el9-gcc13-opt/setup.sh

# Check GPU
echo "GPU check:"
nvidia-smi || echo "No GPU available"

# Check TensorFlow GPU
python3 -c "import tensorflow as tf; print(f'TF GPUs: {len(tf.config.list_physical_devices("GPU"))}')" || echo "TF check failed"

# Navigate to pipeline directory
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

# Run the systematic analysis for this batch
echo "Starting batch analysis..."
python3 scripts/run_systematic_sn_analysis.py \
  --cat-dir-parent /eos/project-e/ep-nu/public/sn-pointing \
  --energy-cosine-pdf /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/_archive_superseded/three_plane_three_plane_v18_200k_aug_20251112_114654/cosine_energy_pdf.npz \
  --output-dir results/parallel_598_cats \
  --n-es 8 \
  --n-cc 80 \
  --run-all \
  --ed-model /eos/user/e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_v14_10k_hyperopt_20251111_175141/checkpoints/model_epoch_62_val_loss_1.1463.keras \
  --mt-model /eos/user/e/evilla/dune/sn-tps/neural_networks/mt_identifier/v26_200k/mt_fixed_20251117_150514/model_best.keras \
  --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
  --cat-range "cat000600,cat000601,cat000602,cat000603,cat000604"

echo "Batch 115 completed: $(date)"
