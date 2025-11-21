#!/bin/bash
#
# Submit scenarios 6, 7, 8 for cats 1-150 (and eventually 151-600)
# This script submits in batches to avoid overloading the scheduler
#

SCRIPT_DIR="/afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline"
LOG_FILE="${SCRIPT_DIR}/scenarios_678_submission.log"

# Configuration
START_CAT=1
END_CAT=150
BATCH_SIZE=50
DELAY_MINUTES=2

echo "========================================" | tee -a "$LOG_FILE"
echo "Submitting scenarios 6,7,8 at $(date)" | tee -a "$LOG_FILE"
echo "Range: cat${START_CAT} to cat${END_CAT}" | tee -a "$LOG_FILE"
echo "Scenarios: no_pdf, perfect_ct_e_gt_10mev, perfect_ct_e_gt_20mev" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

cd "$SCRIPT_DIR" || exit 1

# Create submission script for scenarios 6,7,8
cat > run_scenarios_678.sub << 'EOF'
executable = /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline/scripts/run_cat000001_full_analysis.py
arguments = --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat$(cat_num) --cat-name cat$(cat_num) --pdf-path /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras --scenarios no_pdf perfect_ct_e_gt_10mev perfect_ct_e_gt_20mev --use-eos-structure

output = logs/cat$(cat_num)_s678.out
error = logs/cat$(cat_num)_s678.err
log = logs/cat$(cat_num)_s678.log

+JobFlavour = "tomorrow"
request_GPUs = 1
request_CPUs = 1

queue cat_num from (
EOF

# Add all cat numbers
for ((cat = START_CAT; cat <= END_CAT; cat++)); do
    printf "%06d\n" $cat >> run_scenarios_678.sub
done

echo ")" >> run_scenarios_678.sub

# Submit
echo "Submitting all ${END_CAT} cats for scenarios 6,7,8..." | tee -a "$LOG_FILE"
CLUSTER_ID=$(condor_submit run_scenarios_678.sub 2>&1 | grep -oP 'submitted to cluster \K\d+')

if [ -n "$CLUSTER_ID" ]; then
    echo "✓ Submitted to cluster ${CLUSTER_ID}" | tee -a "$LOG_FILE"
else
    echo "✗ Submission failed!" | tee -a "$LOG_FILE"
fi

echo "========================================" | tee -a "$LOG_FILE"
echo "Submission completed at $(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
