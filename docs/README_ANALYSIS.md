# MT Identification Analysis - November 2025

This directory contains the complete analysis of Main Track (MT) identification performance on corrected production data.

## What Was Done

### 1. Data Correction (Nov 14, 2025)
- **Fixed bug:** Main cluster selection used MC truth instead of reconstructed energy
- **Regenerated:** All production data (4,326 ES + 4,326 CC CAT files)
- **Verified:** 0% incorrect main cluster assignments
- **Details:** See `docs/DATA_CORRECTION_SUMMARY.md`

### 2. MT Model Analysis (200 CATs)
- **Model:** v10 (91.4% training accuracy)
- **Test data:** 13,202 events (6,601 CC + 6,601 ES)
- **Key results:** 83.9% accuracy, 96.0% recall, 54.3% precision
- **Details:** See `docs/MT_IDENTIFICATION_ANALYSIS.md`

### 3. False Positive Investigation
- **Discovery:** 85% of FPs are Marley secondary tracks (not background!)
- **Implication:** Model identifies Marley physics but can't distinguish primary/secondary
- **Root cause:** No energy information in input images
- **Recommendation:** Add energy as input feature or post-processing filter

## Key Files

### Documentation (`docs/`)
- `MT_IDENTIFICATION_ANALYSIS.md` - Complete MT performance analysis
- `DATA_CORRECTION_SUMMARY.md` - Main cluster bug fix details
- `QUICK_REFERENCE.md` - Quick lookup for paths, commands, results

### Analysis Tools (`tests/`)
- `analyze_mt_full.py` - Unified MT analysis tool (run on any N CATs)
- `test_mt_corrected_data.py` - Original 20 CAT test
- `analyze_false_positives.py` - Detailed FP breakdown

### Results (`results/`)
- `mt_analysis_200cats/` - Full 200 CAT analysis
  - `mt_analysis_200cats.pdf` - 12 comprehensive plots
  - `predictions.npz` - All predictions + metadata (5.2 MB)
  - `summary.txt` - Performance metrics
  
- `mt_corrected_data_test/` - Original 20 CAT test
  - `mt_analysis_corrected_data.pdf` - 6 plots
  - `false_positive_analysis.pdf` - FP diagnostic plots

## Quick Start

### Run Analysis on N CATs
```bash
source scripts/init.sh
python3 tests/analyze_mt_full.py --n-cc <N*33> --n-es <N*33> --output my_analysis
```

### View Results
```bash
code results/mt_analysis_200cats/mt_analysis_200cats.pdf
cat results/mt_analysis_200cats/summary.txt
```

## Key Numbers (200 CATs)

| Metric | Value |
|--------|-------|
| Accuracy | 83.90% |
| Precision | 54.34% |
| Recall | 96.03% |
| F1-Score | 0.6941 |
| AUC-ROC | 0.9214 |

**False Positives:**
- 85.1% are Marley secondary tracks
- 14.9% are background
- FP rate for Marley secondaries: 74.9%
- FP rate for background: 3.6%

## Thesis Sections

Use these documents for thesis writing:

1. **Data Quality Section:**
   - `docs/DATA_CORRECTION_SUMMARY.md` (main cluster bug fix)
   - Tables: verification results, before/after comparison

2. **MT Performance Section:**
   - `docs/MT_IDENTIFICATION_ANALYSIS.md` (complete performance analysis)
   - Tables: confusion matrix, metrics, energy distributions
   - Figures: From `results/mt_analysis_200cats/mt_analysis_200cats.pdf`

3. **Discussion Section:**
   - Use "Implications and Recommendations" from MT analysis doc
   - Key insight: Model limitation vs model failure
   - Physical interpretation of false positives

4. **Methods Section:**
   - Tool: `tests/analyze_mt_full.py`
   - Dataset: 200 CATs from corrected production
   - Model: v10 specifications

## Timeline

- **Nov 14, 06:00** - Discovered 2-3% incorrect main cluster assignments
- **Nov 14, 08:00** - Identified root cause (true_energy vs total_energy)
- **Nov 14, 10:00** - Fixed C++ code, fixed verification script
- **Nov 14, 19:06** - Completed data regeneration (8,652 CAT files)
- **Nov 14, 20:00** - Verified 0% incorrect in new data
- **Nov 14, 21:00** - Submitted 7 training jobs with corrected data
- **Nov 14, 23:00** - Ran 200 CAT MT analysis
- **Nov 14, 23:30** - Discovered FP nature (85% Marley secondary)
- **Nov 15, 00:00** - Completed documentation

## Next Steps

1. **CT/ED Results:** Wait for v40-42, v28-29 training completion
2. **Energy Filter:** Test post-processing with energy threshold
3. **Multi-Input Model:** Retrain with energy as explicit input
4. **Full Pipeline:** Run end-to-end burst selection on 1000+ CATs

## Contact

For questions about this analysis, refer to:
- Code: `tests/analyze_mt_full.py`
- Docs: `docs/` directory
- Results: `results/mt_analysis_200cats/`
