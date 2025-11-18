#!/bin/bash
#
# Complete SN pointing systematic analysis pipeline
# Runs analysis, aggregates results, and generates PDF report
#

set -e  # Exit on error

# Default values
CAT_DIR_PARENT="/eos/project-e/ep-nu/public/sn-pointing"
OUTPUT_DIR="results/systematic_sn"
ENERGY_PDF="/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/_archive_superseded/three_plane_three_plane_v18_200k_aug_20251112_114654/cosine_energy_pdf.npz"
ED_MODEL="/eos/user/e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_v14_10k_hyperopt_20251111_175141/checkpoints/model_epoch_62_val_loss_1.1463.keras"
MT_MODEL="/eos/user/e/evilla/dune/sn-tps/neural_networks/mt_identifier/v26_200k/mt_fixed_20251117_150514/model_best.keras"
CT_MODEL="/eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras"
N_ES=8
N_CC=83
MAX_CATS=""
REPORT_FILE="sn_pointing_report.pdf"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --max-cats)
            MAX_CATS="--max-cats $2"
            shift 2
            ;;
        --report)
            REPORT_FILE="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --output-dir DIR     Output directory (default: results/systematic_sn)"
            echo "  --max-cats N         Limit to first N categories (default: all 598)"
            echo "  --report FILE        PDF report filename (default: sn_pointing_report.pdf)"
            echo "  --help               Show this help message"
            echo ""
            echo "Example:"
            echo "  # Test run on 5 categories"
            echo "  $0 --output-dir results/test --max-cats 5 --report test_report.pdf"
            echo ""
            echo "  # Full analysis on all 598 categories"
            echo "  $0 --output-dir results/full_analysis --report full_report.pdf"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "SN POINTING SYSTEMATIC ANALYSIS PIPELINE"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  Output directory: $OUTPUT_DIR"
echo "  Report file: $REPORT_FILE"
echo "  Categories: ${MAX_CATS:-All 598}"
echo ""

# Step 1: Run systematic analysis
echo "=========================================="
echo "STEP 1: Running systematic analysis"
echo "=========================================="
python3 scripts/run_systematic_sn_analysis.py \
  --cat-dir-parent "$CAT_DIR_PARENT" \
  --energy-cosine-pdf "$ENERGY_PDF" \
  --output-dir "$OUTPUT_DIR" \
  --n-es $N_ES \
  --n-cc $N_CC \
  --run-all \
  --ed-model "$ED_MODEL" \
  --mt-model "$MT_MODEL" \
  --ct-model "$CT_MODEL" \
  $MAX_CATS

if [ $? -ne 0 ]; then
    echo "ERROR: Systematic analysis failed"
    exit 1
fi

echo ""
echo "Systematic analysis completed successfully!"
echo ""

# Step 2: Aggregate results (optional, creates JSON summary)
echo "=========================================="
echo "STEP 2: Aggregating results"
echo "=========================================="
python3 scripts/aggregate_sn_results.py \
  --results-dir "$OUTPUT_DIR" \
  --plot

if [ $? -ne 0 ]; then
    echo "WARNING: Result aggregation failed, but continuing..."
fi

echo ""

# Step 3: Generate PDF report
echo "=========================================="
echo "STEP 3: Generating PDF report"
echo "=========================================="
python3 scripts/generate_sn_report.py \
  --results-dir "$OUTPUT_DIR" \
  --output "$REPORT_FILE"

if [ $? -ne 0 ]; then
    echo "ERROR: Report generation failed"
    exit 1
fi

echo ""
echo "=========================================="
echo "PIPELINE COMPLETED SUCCESSFULLY"
echo "=========================================="
echo ""
echo "Results saved to: $OUTPUT_DIR"
echo "PDF report: $REPORT_FILE"
echo "Summary: $OUTPUT_DIR/analysis_summary.json"
echo "Aggregated results: $OUTPUT_DIR/aggregated_results.json"
echo ""
echo "Quick view of summary:"
cat "$OUTPUT_DIR/analysis_summary.json"
