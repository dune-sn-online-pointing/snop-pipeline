#!/bin/bash
# Submit SN systematic analysis to HTCondor GPU cluster

set -e

cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

echo "=========================================="
echo "SN Systematic Analysis - GPU Submission"
echo "=========================================="
echo ""

# Check if logs directory exists
mkdir -p condor/logs

# Show the submission file
echo "Submit file: condor/submit_sn_analysis_gpu.sub"
echo ""
echo "Job configuration:"
echo "  - GPU: 1x (A100/V100 preferred)"
echo "  - CPUs: 4"
echo "  - Memory: 32GB"
echo "  - Disk: 20GB"
echo "  - Flavour: tomorrow (24h max)"
echo "  - Categories: All 598"
echo "  - Output: results/full_598_cats_gpu/"
echo ""

# Submit the job
read -p "Submit job to HTCondor? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Submitting job..."
    condor_submit condor/submit_sn_analysis_gpu.sub
    echo ""
    echo "Job submitted! Monitor with:"
    echo "  condor_q"
    echo "  tail -f condor/logs/sn_analysis_gpu_*.out"
    echo ""
    echo "After completion, generate report with:"
    echo "  python3 scripts/aggregate_sn_results.py --results-dir results/full_598_cats_gpu --plot"
    echo "  python3 scripts/generate_sn_report.py --results-dir results/full_598_cats_gpu --output full_598_gpu_report.pdf"
else
    echo "Submission cancelled"
fi
