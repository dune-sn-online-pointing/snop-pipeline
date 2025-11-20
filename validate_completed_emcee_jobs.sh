#!/bin/bash

# Validation script for completed emcee jobs
# Uses proper command flags instead of /dev/null redirects

CLUSTER_ID="13791414"
LOG_DIR="logs"
OUTPUT_BASE="/eos/project-e/ep-nu/evilla/sn-pointing"
SCENARIOS=("perfect_ct" "es_main_cc_shower" "es_main_cc_all" "es_all_cc_shower" "es_all_cc_all" "all_tracks_all_showers")

echo "=================================================================="
echo "EMCEE JOB VALIDATION REPORT"
echo "=================================================================="
echo ""

# Count total output files
TOTAL_FILES=$(find "$OUTPUT_BASE"/cat*/pipeline -name "*_emcee.npz" -type f 2>&- | wc -l)
echo "Total output files: $TOTAL_FILES"
echo ""

# Get list of cats with any emcee output
echo "Analyzing completed cats..."
COMPLETED_CATS=$(find "$OUTPUT_BASE"/cat*/pipeline -name "*_emcee.npz" -type f 2>&- | \
                 awk -F'/' '{print $(NF-2)}' | \
                 sort -u)
NUM_CATS=$(echo "$COMPLETED_CATS" | wc -l)
echo "Cats with outputs: $NUM_CATS"
echo ""

# Check each cat for complete scenario set
echo "Checking for incomplete cats (missing scenarios)..."
INCOMPLETE_COUNT=0
COMPLETE_COUNT=0
INCOMPLETE_CATS=""

for cat in $COMPLETED_CATS; do
    CAT_DIR="$OUTPUT_BASE/$cat/pipeline"
    FOUND_SCENARIOS=0
    
    for scenario in "${SCENARIOS[@]}"; do
        if [ -f "$CAT_DIR/${cat}_scenario_${scenario}_emcee.npz" ]; then
            ((FOUND_SCENARIOS++))
        fi
    done
    
    if [ $FOUND_SCENARIOS -eq 6 ]; then
        ((COMPLETE_COUNT++))
    else
        ((INCOMPLETE_COUNT++))
        INCOMPLETE_CATS="$INCOMPLETE_CATS $cat($FOUND_SCENARIOS/6)"
    fi
done

echo "  Complete cats (6/6 scenarios): $COMPLETE_COUNT"
echo "  Incomplete cats: $INCOMPLETE_COUNT"
if [ $INCOMPLETE_COUNT -gt 0 ]; then
    echo "  Incomplete list: $INCOMPLETE_CATS"
fi
echo ""

# Check for errors in log files
echo "Checking error logs for failures..."
ERROR_COUNT=0
CATS_WITH_ERRORS=""

for cat in $COMPLETED_CATS; do
    LOG_FILE="$LOG_DIR/emcee_${cat}_${CLUSTER_ID}.err"
    
    if [ -f "$LOG_FILE" ]; then
        # Check for actual errors (not just warnings)
        # Exclude TensorFlow warnings, info messages, and CUDA initialization errors
        ERRORS=$(grep -i "error\|exception\|traceback\|failed" "$LOG_FILE" 2>&- | \
                 grep -v "tensorflow" | \
                 grep -v "WARNING" | \
                 grep -v "INFO" | \
                 grep -v "CUDA error" | \
                 grep -v "cuInit" | \
                 wc -l)
        
        if [ "$ERRORS" -gt 0 ]; then
            ((ERROR_COUNT++))
            CATS_WITH_ERRORS="$CATS_WITH_ERRORS $cat"
        fi
    fi
done

echo "  Cats with errors: $ERROR_COUNT"
if [ $ERROR_COUNT -gt 0 ]; then
    echo "  Error list: $CATS_WITH_ERRORS"
fi
echo ""

# Check output logs for failed completions
echo "Checking output logs for job failures..."
FAILED_JOBS=0
FAILED_CATS=""

for cat in $COMPLETED_CATS; do
    LOG_FILE="$LOG_DIR/emcee_${cat}_${CLUSTER_ID}.out"
    
    if [ -f "$LOG_FILE" ]; then
        # Check if log contains success message
        if ! grep -q "completed successfully" "$LOG_FILE" 2>&-; then
            ((FAILED_JOBS++))
            FAILED_CATS="$FAILED_CATS $cat"
        fi
    fi
done

echo "  Failed completions: $FAILED_JOBS"
if [ $FAILED_JOBS -gt 0 ]; then
    echo "  Failed list: $FAILED_CATS"
fi
echo ""

# Summary
echo "=================================================================="
echo "SUMMARY"
echo "=================================================================="
echo "Total output files: $TOTAL_FILES (expected: $((618 * 6)) = 3708)"
echo "Cats processed: $NUM_CATS / 618"
echo "Complete cats: $COMPLETE_COUNT"
echo "Incomplete cats: $INCOMPLETE_COUNT"
echo "Cats with errors: $ERROR_COUNT"
echo "Failed jobs: $FAILED_JOBS"
echo ""

if [ $COMPLETE_COUNT -eq $NUM_CATS ] && [ $ERROR_COUNT -eq 0 ] && [ $FAILED_JOBS -eq 0 ]; then
    echo "✓ All completed jobs are SUCCESSFUL!"
else
    echo "⚠ Some jobs have issues - review above for details"
fi
echo "=================================================================="
