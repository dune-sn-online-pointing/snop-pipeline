#!/bin/bash
#
# Check status of batch processing jobs
#

CLUSTER_ID="13791158"
BASE_DIR="/eos/project-e/ep-nu/evilla/sn-pointing"

echo "======================================"
echo "Condor Job Status"
echo "======================================"
condor_q $CLUSTER_ID -nobatch | tail -5

echo ""
echo "======================================"
echo "Completed Categories (with pipeline results)"
echo "======================================"

completed=0
failed=0

for i in $(seq 1 50); do
    cat_name=$(printf "cat%06d" $i)
    pipeline_dir="${BASE_DIR}/${cat_name}/pipeline"
    
    if [ -d "$pipeline_dir" ]; then
        # Count .npz files
        n_files=$(ls -1 "$pipeline_dir"/*.npz 2>/dev/null | wc -l)
        if [ $n_files -ge 5 ]; then
            echo "✓ $cat_name ($n_files scenarios)"
            ((completed++))
        elif [ $n_files -gt 0 ]; then
            echo "⚠ $cat_name (partial: $n_files scenarios)"
            ((failed++))
        fi
    fi
done

echo ""
echo "======================================"
echo "Summary"
echo "======================================"
echo "Completed: $completed / 50"
echo "Partial/Failed: $failed / 50"
echo "Pending: $((50 - completed - failed)) / 50"

# Check for recent errors in logs
echo ""
echo "======================================"
echo "Recent Errors (if any)"
echo "======================================"
grep -i "error\|failed\|exception" /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline/condor_logs/cat*.err 2>/dev/null | head -10 || echo "No errors found in logs"
