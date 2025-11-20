#!/bin/bash

CAT_NAME=$1

echo "=================================================================="
echo "Processing $CAT_NAME with EMCEE - ALL SCENARIOS"
echo "=================================================================="

BASE_PATH="/eos/project-e/ep-nu/evilla/sn-pointing"
CAT_DIR="${BASE_PATH}/${CAT_NAME}"
ED_MODEL="/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras"
PDF_FILE="/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz"

# All scenarios
SCENARIOS="perfect_ct es_main_cc_shower es_main_cc_all es_all_cc_shower es_all_cc_all all_tracks_all_showers"

cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

python3 scripts/run_cat_analysis_emcee_optimized.py \
    --cat-name ${CAT_NAME} \
    --cat-dir ${CAT_DIR} \
    --ed-model ${ED_MODEL} \
    --pdf-file ${PDF_FILE} \
    --scenarios ${SCENARIOS} \
    --nwalkers 64 \
    --nsteps 2000 \
    --discard 400 \
    --use-eos-structure

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ ${CAT_NAME} completed successfully"
else
    echo "✗ ${CAT_NAME} failed with exit code $EXIT_CODE"
fi

exit $EXIT_CODE
