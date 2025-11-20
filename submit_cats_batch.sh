#!/bin/bash
#
# Batch submission script: Submits 20 cats every 5 minutes
# Processes cats 151-600 in batches of 20
#
# Usage: ./submit_cats_batch.sh
# Run in a screen/tmux session for persistence

SCRIPT_DIR="/afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline"
LOG_FILE="${SCRIPT_DIR}/batch_submission.log"

# Range configuration
START_CAT=151
END_CAT=600
BATCH_SIZE=20
DELAY_MINUTES=5

echo "========================================" | tee -a "$LOG_FILE"
echo "Starting batch submission at $(date)" | tee -a "$LOG_FILE"
echo "Range: cat${START_CAT} to cat${END_CAT}" | tee -a "$LOG_FILE"
echo "Batch size: ${BATCH_SIZE} cats" | tee -a "$LOG_FILE"
echo "Delay: ${DELAY_MINUTES} minutes" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

cd "$SCRIPT_DIR" || exit 1

# Calculate total batches
TOTAL_CATS=$((END_CAT - START_CAT + 1))
TOTAL_BATCHES=$(((TOTAL_CATS + BATCH_SIZE - 1) / BATCH_SIZE))

echo "Total cats: ${TOTAL_CATS}" | tee -a "$LOG_FILE"
echo "Total batches: ${TOTAL_BATCHES}" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

batch_num=1
for ((start = START_CAT; start <= END_CAT; start += BATCH_SIZE)); do
    end=$((start + BATCH_SIZE - 1))
    if [ $end -gt $END_CAT ]; then
        end=$END_CAT
    fi
    
    echo "[Batch ${batch_num}/${TOTAL_BATCHES}] $(date)" | tee -a "$LOG_FILE"
    echo "  Submitting cats ${start}-${end}..." | tee -a "$LOG_FILE"
    
    # Create temporary submission file
    SUB_FILE="${SCRIPT_DIR}/submit_batch_${start}_${end}.sub"
    cat > "$SUB_FILE" << 'SUBEOF'
executable = scripts/run_cat000001_full_analysis.py
arguments = --cat-dir /eos/project-e/ep-nu/evilla/sn-pointing/cat$(cat_num) --cat-name cat$(cat_num) --pdf-path /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz --ed-model /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras --scenarios best_case perfect_ct full_pipeline weighted_linear weighted_squared no_pdf perfect_ct_e_gt_10mev perfect_ct_e_gt_20mev --use-eos-structure

output = logs/cat$(cat_num).out
error = logs/cat$(cat_num).err
log = logs/cat$(cat_num).log

+JobFlavour = "tomorrow"
request_GPUs = 1
request_CPUs = 1

queue cat_num from (
SUBEOF
    
    # Add cat numbers to submission file
    for ((cat = start; cat <= end; cat++)); do
        printf "%06d\n" $cat >> "$SUB_FILE"
    done
    
    echo ")" >> "$SUB_FILE"
    
    # Submit the batch
    CLUSTER_ID=$(condor_submit "$SUB_FILE" 2>&1 | grep -oP 'submitted to cluster \K\d+')
    
    if [ -n "$CLUSTER_ID" ]; then
        echo "  ✓ Submitted to cluster ${CLUSTER_ID}" | tee -a "$LOG_FILE"
    else
        echo "  ✗ Submission failed!" | tee -a "$LOG_FILE"
    fi
    
    # Clean up temporary file
    rm -f "$SUB_FILE"
    
    batch_num=$((batch_num + 1))
    
    # Wait before next batch (except for last batch)
    if [ $end -lt $END_CAT ]; then
        echo "  Waiting ${DELAY_MINUTES} minutes before next batch..." | tee -a "$LOG_FILE"
        echo "" | tee -a "$LOG_FILE"
        sleep $((DELAY_MINUTES * 60))
    fi
done

echo "" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "Batch submission completed at $(date)" | tee -a "$LOG_FILE"
echo "All batches submitted successfully!" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
