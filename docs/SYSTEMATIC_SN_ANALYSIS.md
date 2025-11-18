# Systematic SN Pointing Performance Analysis

This framework evaluates supernova (SN) neutrino pointing performance across three scenarios using exactly **325 ES + 3300 CC samples** per category (nominal values for a 10 kpc SN explosion).

## Overview

### Three Analysis Scenarios

1. **Best Case (True Directions)**: Uses ground truth electron directions
   - Upper bound on pointing performance
   - No ML inference - perfect reconstruction assumed
   - MCMC optimization with true electron tracks

2. **ED Network (Perfect Channel Tagging)**: Feeds all true ES tracks through ED model
   - Assumes perfect channel identification (no CT errors)
   - ED network inference on all CC electron tracks
   - Shows ED model performance in isolation

3. **Full Pipeline (Realistic)**: Complete MT → CT → ED chain
   - Realistic end-to-end performance
   - MT identifies main tracks, CT tags ES channels, ED reconstructs directions
   - Includes all detection and identification uncertainties

## Directory Structure

```
python/
  sn_sample_utils.py          # Sample validation and loading utilities

scripts/
  run_best_case_sn_analysis.py       # Scenario 1: Best case
  run_ed_network_sn_analysis.py      # Scenario 2: ED network
  run_full_pipeline_sn_analysis.py   # Scenario 3: Full pipeline
  run_systematic_sn_analysis.py      # Wrapper to run all scenarios
  aggregate_sn_results.py            # Aggregate results across categories
```

## Usage

### Quick Start: Complete Pipeline

Run all steps with a single command (recommended):

```bash
# Test run on 5 categories
./scripts/run_full_sn_pipeline.sh \
  --output-dir results/test \
  --max-cats 5 \
  --report test_report.pdf

# Full analysis on all 598 categories
./scripts/run_full_sn_pipeline.sh \
  --output-dir results/full_598 \
  --report full_report.pdf
```

This automatically runs:
1. Systematic analysis (all 3 scenarios)
2. Result aggregation (JSON summaries)
3. PDF report generation (statistics + plots)

### Manual Execution: Step-by-Step

For more control over individual steps:

### 1. Run Single Scenario on One Category

#### Best Case (Scenario 1)
```bash
python3 scripts/run_best_case_sn_analysis.py \
  --cat-dir /path/to/cat000001 \
  --cat-name cat000001 \
  --energy-cosine-pdf /path/to/energy_cosine_pdf.npz \
  --output-dir results/sn_analysis \
  --n-es 325 \
  --n-cc 3300
```

#### ED Network (Scenario 2)
```bash
python3 scripts/run_ed_network_sn_analysis.py \
  --cat-dir /path/to/cat000001 \
  --cat-name cat000001 \
  --ed-model /path/to/ed_model.h5 \
  --energy-cosine-pdf /path/to/energy_cosine_pdf.npz \
  --output-dir results/sn_analysis \
  --n-es 325 \
  --n-cc 3300 \
  --batch-size 512
```

#### Full Pipeline (Scenario 3)
```bash
python3 scripts/run_full_pipeline_sn_analysis.py \
  --cat-dir /path/to/cat000001 \
  --cat-name cat000001 \
  --mt-model /path/to/mt_model.h5 \
  --ct-model /path/to/ct_model.h5 \
  --ed-model /path/to/ed_model.h5 \
  --energy-cosine-pdf /path/to/energy_cosine_pdf.npz \
  --output-dir results/sn_analysis \
  --n-es 325 \
  --n-cc 3300 \
  --mt-threshold 0.5 \
  --ct-threshold 0.5 \
  --batch-size 512
```

### 2. Run All Scenarios Systematically Across Categories

```bash
python3 scripts/run_systematic_sn_analysis.py \
  --cat-dir-parent /path/to/all_cats/ \
  --energy-cosine-pdf /path/to/energy_cosine_pdf.npz \
  --output-dir results/systematic_sn_analysis \
  --mt-model /path/to/mt_model.h5 \
  --ct-model /path/to/ct_model.h5 \
  --ed-model /path/to/ed_model.h5 \
  --run-all \
  --n-es 325 \
  --n-cc 3300
```

**Options:**
- `--run-all`: Run all three scenarios
- `--run-best-case`: Run only scenario 1
- `--run-ed-network`: Run only scenario 2  
- `--run-full-pipeline`: Run only scenario 3
- `--max-cats N`: Process only first N categories
- `--cat-range "1-100"`: Process specific category range

### 3. Aggregate Results

```bash
python3 scripts/aggregate_sn_results.py \
  --results-dir results/systematic_sn_analysis \
  --output-dir results/systematic_sn_analysis \
  --plot
```

## Output Structure

```
results/
  best_case/
    cat000001/
      metrics.json          # Per-cat metrics with per-event results
    cat000002/
      metrics.json
    ...
  
  ed_network/
    cat000001/
      metrics.json
    ...
  
  full_pipeline/
    cat000001/
      metrics.json
    ...
  
  analysis_summary.json       # Overall execution summary
  aggregated_results.json     # Cross-cat aggregated metrics
  angular_resolution_comparison.png  # Comparison plot
```

## Metrics Saved

### Per-Category Metrics (`metrics.json`)
- `scenario`: Scenario name
- `cat_name`: Category identifier
- `n_es_selected`: Number of ES samples used (325)
- `n_cc_selected`: Number of CC samples used (3300)
- `n_events_processed`: Total events with successful reconstruction
- `angular_resolution`: Median, mean, std, percentiles (50, 68, 90, 95)
- `n_clusters_per_event`: Statistics on cluster multiplicity
- `per_event_results`: Array of per-event results with:
  - `event_id`
  - `n_clusters` (or `n_es_clusters` for full pipeline)
  - `best_direction`: Reconstructed neutrino direction
  - `angular_error_deg`: Angular error vs true direction
  - `true_nu_direction`: Ground truth

### Full Pipeline Additional Metrics
- `n_total_clusters`: Total clusters before MT
- `n_mt_clusters`: Clusters identified as main tracks
- `n_es_clusters`: Clusters tagged as ES by CT
- `mt_efficiency`: MT identification efficiency
- `ct_efficiency`: CT tagging efficiency (ES / MT)
- `overall_efficiency`: End-to-end efficiency (ES / all)

### Aggregated Metrics (`aggregated_results.json`)
- Cross-category statistics for each scenario
- Combined angular resolution distributions
- Per-category summary table
- Efficiency metrics (full pipeline only)

## Sample Validation

Categories are automatically validated before processing:
- **Required**: 325 ES events + 3300 CC events
- **Skipped**: Categories with insufficient samples
- **Tracked**: All skipped categories logged in `analysis_summary.json`

## Key Features

1. **Fixed Sample Counts**: Ensures fair comparison by using identical samples (325 ES + 3300 CC)
2. **Reproducibility**: Fixed random seed (default: 42) for consistent sample selection
3. **Skip Tracking**: Automatically tracks and reports categories with insufficient samples
4. **Per-Event Results**: Full per-event reconstruction saved for detailed analysis
5. **MCMC Optimization**: Multi-start MCMC (50 trials × 1000 steps) for robust direction finding
6. **Comprehensive Metrics**: Angular resolution, efficiency, cluster multiplicity

## Sample Loading Details

The framework uses `sn_sample_utils.py` utilities:

- `validate_cat_samples()`: Check if category has sufficient ES+CC samples
- `get_sample_event_ids()`: Randomly select exactly 325 ES + 3300 CC event IDs
- `load_filtered_cluster_images()`: Load only selected event IDs
- `save_scenario_results()`: Save metrics in standardized JSON format

All samples are loaded from:
```
cat_dir/cat_name_cluster_images_tick3_ch2_min2_tot3_e2p0/{X,U,V}/
```

Interaction types:
- `interaction_type == 0`: ES (elastic scattering)
- `interaction_type == 1`: CC (charged current)

## Example Workflow

```bash
# Step 1: Run systematic analysis on first 10 categories
python3 scripts/run_systematic_sn_analysis.py \
  --cat-dir-parent /path/to/cats/ \
  --energy-cosine-pdf models/energy_cosine_pdf.npz \
  --mt-model models/mt_model.h5 \
  --ct-model models/ct_model.h5 \
  --ed-model models/ed_model.h5 \
  --output-dir results/test_run \
  --run-all \
  --max-cats 10

# Step 2: Aggregate results
python3 scripts/aggregate_sn_results.py \
  --results-dir results/test_run \
  --plot

# Step 3: Generate PDF report
python3 scripts/generate_sn_report.py \
  --results-dir results/test_run \
  --output test_report.pdf

# Step 4: Review summary
cat results/test_run/analysis_summary.json
cat results/test_run/aggregated_results.json
```

## PDF Report Generation

Generate a comprehensive PDF report with statistics and plots:

```bash
python3 scripts/generate_sn_report.py \
  --results-dir results/systematic_sn \
  --output sn_pointing_report.pdf
```

**Report contents:**
- Summary page with overall statistics
- Angular resolution comparison across scenarios
- Cluster statistics (input vs matched, main vs non-main)
- 3-plane matching efficiency analysis
- Per-category angular resolution trends
- Performance degradation quantification

**Options:**
```bash
# Include specific scenarios only
python3 scripts/generate_sn_report.py \
  --results-dir results/systematic_sn \
  --output report.pdf \
  --scenarios best_case full_pipeline
```

## Requirements

- Python 3.7+
- TensorFlow 2.x (for ED, MT, CT models)
- NumPy
- SciPy
- uproot (for ROOT file access)
- matplotlib (for plotting and PDF reports)

## Notes

- Categories are validated based on file counts (8 ES files, 83 CC files minimum)
- Cluster matching uses `match_id` field to align clusters across X, U, V planes
- Only clusters with valid `match_id` that appear in all 3 planes are used
- Cluster statistics track main vs non-main electron tracks separately
- MCMC uses 50 random initializations with 1000 steps each
- Energy-cosine PDF is used for likelihood computation in MCMC
- Results are saved incrementally (per-cat) for fault tolerance
- Random seed ensures reproducible sample selection across runs
