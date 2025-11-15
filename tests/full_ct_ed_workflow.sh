#!/usr/bin/env bash
# Complete workflow example: CT inference, analysis, ED+MCMC
# This script demonstrates the full optional CT and ED+MCMC pipeline
set -euo pipefail

# ============================================================================
# CONFIGURATION - Update these paths for your setup
# ============================================================================

# Model paths
CT_MODEL="/eos/user/e/evilla/supernova/models/channel_tagger_best.keras"
ED_MODEL="/eos/user/e/evilla/supernova/models/electron_direction_best.keras"

# Input data paths
VOLUMES_NPZ="results/pipeline_run_001/volumes.npz"
MT_RESULTS_NPZ="results/pipeline_run_001/mt_predictions.npz"

# Output directory
OUTPUT_DIR="results/ct_ed_analysis_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTPUT_DIR"

echo "====================================================================="
echo "CT + ED + MCMC Workflow"
echo "====================================================================="
echo "Output directory: $OUTPUT_DIR"
echo ""

# ============================================================================
# STEP 1: Channel Tagger Inference
# ============================================================================
echo "[1/5] Running Channel Tagger inference..."
CT_PREDICTIONS="$OUTPUT_DIR/ct_predictions.npz"

python3 python/channel_tagger_runner.py \
  "$CT_MODEL" \
  "$VOLUMES_NPZ" \
  --out "$CT_PREDICTIONS" \
  --batch-size 64

echo "  ✓ CT predictions saved to: $CT_PREDICTIONS"
echo ""

# ============================================================================
# STEP 2: Analyze CT Results
# ============================================================================
echo "[2/5] Analyzing CT results..."
CT_ANALYSIS_DIR="$OUTPUT_DIR/ct_analysis"

python3 tests/analyze_ct_results.py \
  "$CT_PREDICTIONS" \
  "$CT_ANALYSIS_DIR"

echo "  ✓ CT analysis plots saved to: $CT_ANALYSIS_DIR/ct_analysis.pdf"
echo ""

# ============================================================================
# STEP 3: ED Inference on MT Clusters
# ============================================================================
echo "[3/5] Running ED inference on main-track clusters..."
ED_INFERENCE="$OUTPUT_DIR/ed_inference_on_mt.npz"

python3 python/ed_inference_from_mt.py \
  "$ED_MODEL" \
  "$VOLUMES_NPZ" \
  "$MT_RESULTS_NPZ" \
  --out "$ED_INFERENCE" \
  --batch-size 32

echo "  ✓ ED inference saved to: $ED_INFERENCE"
echo ""

# ============================================================================
# STEP 4: MCMC Direction Refinement
# ============================================================================
echo "[4/5] Running MCMC direction refinement..."
MCMC_RESULTS="$OUTPUT_DIR/ed_mcmc_results.npz"

python3 python/ed_mcmc.py \
  "$ED_INFERENCE" \
  --out "$MCMC_RESULTS" \
  --nsteps 3000 \
  --proposal-scale 0.08

echo "  ✓ MCMC results saved to: $MCMC_RESULTS"
echo ""

# ============================================================================
# STEP 5: Generate Summary Report
# ============================================================================
echo "[5/5] Generating summary report..."

cat > "$OUTPUT_DIR/SUMMARY.txt" << EOF
CT + ED + MCMC Analysis Summary
================================
Date: $(date)

Input Files:
- Volumes: $VOLUMES_NPZ
- MT Results: $MT_RESULTS_NPZ
- CT Model: $CT_MODEL
- ED Model: $ED_MODEL

Output Files:
- CT Predictions: $CT_PREDICTIONS
- CT Analysis: $CT_ANALYSIS_DIR/ct_analysis.pdf
- ED Inference: $ED_INFERENCE
- MCMC Results: $MCMC_RESULTS

To view results:
1. Open CT analysis: evince $CT_ANALYSIS_DIR/ct_analysis.pdf
2. Load MCMC results in Python:
   import numpy as np
   data = np.load('$MCMC_RESULTS')
   mean_dirs = data['mean_direction']
   best_dirs = data['best_direction']

Next Steps:
- Compare angular errors before/after MCMC
- Analyze MCMC acceptance rates (chain_likes trends)
- Integrate best directions into downstream analysis
EOF

echo "  ✓ Summary saved to: $OUTPUT_DIR/SUMMARY.txt"
echo ""

echo "====================================================================="
echo "Workflow complete!"
echo "====================================================================="
echo ""
echo "Results are in: $OUTPUT_DIR"
echo ""
echo "Quick checks:"
echo "  1. View CT analysis: evince $CT_ANALYSIS_DIR/ct_analysis.pdf"
echo "  2. Check summary: cat $OUTPUT_DIR/SUMMARY.txt"
echo "  3. Inspect MCMC: python3 -c \"import numpy as np; d=np.load('$MCMC_RESULTS'); print('Mean dirs shape:', d['mean_direction'].shape)\""
echo ""
