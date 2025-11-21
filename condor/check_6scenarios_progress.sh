#!/bin/bash

echo "=================================================================="
echo "EMCEE 6-SCENARIO PROCESSING STATUS"
echo "=================================================================="
echo ""

# Condor status
echo "Condor Job Status (Cluster 13791725):"
condor_q 13791725 -nobatch | tail -3

echo ""
echo "Completed output files by scenario:"
BASE_PATH="/eos/project-e/ep-nu/evilla/sn-pointing"

for scenario in best_case perfect_ct full_pipeline weighted_ct perfect_ct_e_gt_10mev perfect_ct_e_gt_5mev; do
    COUNT=$(find "$BASE_PATH"/cat*/pipeline -name "*_scenario_${scenario}_emcee.npz" -type f 2>&- | wc -l)
    echo "  ${scenario}: $COUNT / 618"
done

TOTAL=$(find "$BASE_PATH"/cat*/pipeline -name "*_scenario_*_emcee.npz" -type f 2>&- | wc -l)
EXPECTED=$((618 * 6))
echo ""
echo "Total files: $TOTAL / $EXPECTED"
echo "Progress: $((TOTAL * 100 / EXPECTED))%"

echo ""
echo "Recent log entries:"
ls -lt logs/emcee_cat*out 2>&- | head -5

echo ""
echo "=================================================================="
