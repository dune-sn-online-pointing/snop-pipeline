#!/bin/bash
#
# Recompute all 6 scenarios with optimized MCMC parameters:
# - 128 walkers × 500 steps (converges by ~100 steps, 500 for safety)
# - Smart initialization (mean cluster direction)
# - Stretch parameter a=3.0
# - Discard first 100 steps (20%)
#
# This gives ~6.7× speedup over old config (64k evals vs 128k)
# with dramatically better angular resolution.
#

# Check if max-files argument provided
MAX_FILES=""
if [ "$1" == "--max-files" ]; then
    MAX_FILES="--max-files $2"
    echo "Will process maximum $2 categories"
fi

# Define scenarios
scenarios=("best_case" "perfect_ct" "full_pipeline" "weighted_ct" "perfect_ct_e_gt_10mev" "perfect_ct_e_gt_5mev")

# Model paths
ED_MODEL="/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras"
CT_MODEL="/eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras"
PDF_FILE="/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz"
BASE_PATH="/eos/project-e/ep-nu/evilla/sn-pointing"

# Optimized MCMC parameters
NWALKERS=128
NSTEPS=500
DISCARD=100

# Categories to process (all 618)
cat_list=$(seq -f "cat%06g" 0 617)

# Prepare condor directory
mkdir -p condor_recompute_optimized
cd condor_recompute_optimized

# Split categories into groups of 10 per job
job_id=0
for scenario in "${scenarios[@]}"; do
    echo "==> Preparing jobs for scenario: $scenario"
    
    cats_array=($cat_list)
    total_cats=${#cats_array[@]}
    cats_per_job=10
    
    for ((i=0; i<total_cats; i+=cats_per_job)); do
        # Get batch of categories
        batch_cats="${cats_array[@]:i:cats_per_job}"
        
        # Create submission script
        submit_file="submit_${scenario}_job${job_id}.sub"
        cat > $submit_file << EOF
executable = run_${scenario}_job${job_id}.sh
output = logs/${scenario}_job${job_id}.out
error = logs/${scenario}_job${job_id}.err
log = logs/${scenario}_job${job_id}.log
request_cpus = 1
request_memory = 4GB
+MaxRuntime = 14400
queue
EOF

        # Create run script
        run_file="run_${scenario}_job${job_id}.sh"
        cat > $run_file << RUNEOF
#!/bin/bash
source /cvmfs/sft.cern.ch/lcg/views/LCG_105/x86_64-el9-gcc13-opt/setup.sh
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

for cat in $batch_cats; do
    echo "Processing \$cat for $scenario..."
    python3 scripts/run_cat_analysis_emcee_corrected.py \\
        --cat-dir ${BASE_PATH}/\${cat}/images \\
        --ed-model $ED_MODEL \\
        --ct-model $CT_MODEL \\
        --pdf-file $PDF_FILE \\
        --scenarios $scenario \\
        --nwalkers $NWALKERS \\
        --nsteps $NSTEPS \\
        --discard $DISCARD \\
        --use-eos-structure
done
RUNEOF

        chmod +x $run_file
        
        job_id=$((job_id + 1))
    done
done

# Create logs directory
mkdir -p logs

echo ""
echo "========================================="
echo "Prepared $job_id Condor jobs"
echo "Scenarios: ${scenarios[@]}"
echo "Categories per job: 10"
echo "MCMC config: $NWALKERS walkers × $NSTEPS steps"
echo "========================================="
echo ""
echo "To submit all jobs:"
echo "  cd condor_recompute_optimized"
echo "  for f in submit_*.sub; do condor_submit \$f; done"
echo ""
echo "To check progress:"
echo "  condor_q"
echo ""
echo "Estimated time: ~2-3 minutes per category"
echo "Total wall time: ~12-18 hours (parallelized)"
echo ""

