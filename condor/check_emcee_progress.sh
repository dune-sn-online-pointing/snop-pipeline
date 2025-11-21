#!/bin/bash

echo "=================================================================="
echo "EMCEE ALL-SCENARIOS PROCESSING STATUS"
echo "=================================================================="
echo ""

# Condor status
echo "Condor Job Status:"
condor_q 13791414 -nobatch | tail -3

echo ""
echo "Completed output files:"
COMPLETED=$(find /eos/project-e/ep-nu/evilla/sn-pointing/cat*/pipeline -name "*_emcee.npz" -type f 2>&- | wc -l)
EXPECTED=$((618 * 6))  # 618 cats × 6 scenarios
echo "  Files found: $COMPLETED / $EXPECTED"
echo "  Progress: $((COMPLETED * 100 / EXPECTED))%"

echo ""
echo "Recent log entries:"
ls -lt logs/emcee_cat*out 2>&- | head -5

echo ""
echo "=================================================================="
