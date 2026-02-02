# SN Pointing Analysis Tools Summary

Complete toolkit for systematic supernova neutrino pointing performance analysis.

## Core Analysis Scripts

### 1. `run_best_case_sn_analysis.py`
**Purpose**: Best-case performance using true electron directions  
**Key Features**:
- MCMC optimization with true tracks
- Upper bound on pointing resolution
- Per-event angular error computation

```bash
python3 scripts/run_best_case_sn_analysis.py \
  --cat-dir /path/to/category \
  --cat-name cat000001 \
  --energy-cosine-pdf /path/to/pdf.npz \
  --output-dir results/
```

### 2. `run_ed_network_sn_analysis.py`
**Purpose**: ED network performance with perfect channel tagging  
**Key Features**:
- ED model inference on true CC tracks
- Isolates ED reconstruction performance
- No MT/CT uncertainty

```bash
python3 scripts/run_ed_network_sn_analysis.py \
  --cat-dir /path/to/category \
  --cat-name cat000001 \
  --ed-model /path/to/ed_model.keras \
  --energy-cosine-pdf /path/to/pdf.npz \
  --output-dir results/
```

### 3. `run_full_pipeline_sn_analysis.py`
**Purpose**: Complete realistic MT→CT→ED pipeline  
**Key Features**:
- Full detection chain
- Efficiency tracking at each stage
- Realistic end-to-end performance

```bash
python3 scripts/run_full_pipeline_sn_analysis.py \
  --cat-dir /path/to/category \
  --cat-name cat000001 \
  --mt-model /path/to/mt_model.keras \
  --ct-model /path/to/ct_model.keras \
  --ed-model /path/to/ed_model.keras \
  --energy-cosine-pdf /path/to/pdf.npz \
  --output-dir results/
```

## Pipeline Management Scripts

### 4. `run_systematic_sn_analysis.py`
**Purpose**: Systematic analysis across all categories  
**Key Features**:
- Loops through all 598 categories
- Runs all 3 scenarios per category
- Validation and skip tracking
- Subprocess-based execution

```bash
python3 scripts/run_systematic_sn_analysis.py \
  --cat-dir-parent /eos/project-e/ep-nu/public/sn-pointing \
  --energy-cosine-pdf /path/to/pdf.npz \
  --output-dir results/systematic_sn \
  --run-all \
  --ed-model /path/to/ed.keras \
  --mt-model /path/to/mt.keras \
  --ct-model /path/to/ct.keras
```

### 5. `aggregate_sn_results.py`
**Purpose**: Aggregate results across categories  
**Key Features**:
- Combines per-category metrics
- Computes statistics (median, p68, p90)
- Generates comparison plots
- JSON output for further processing

```bash
python3 scripts/aggregate_sn_results.py \
  --results-dir results/systematic_sn \
  --plot
```

### 6. `generate_sn_report.py` ⭐ NEW
**Purpose**: Generate comprehensive PDF reports  
**Key Features**:
- Multi-page PDF with summaries and plots
- Angular resolution comparisons
- Cluster statistics (main vs non-main)
- Matching efficiency analysis
- Automated statistics computation

```bash
python3 scripts/generate_sn_report.py \
  --results-dir results/systematic_sn \
  --output sn_report.pdf
```

### 7. `run_full_sn_pipeline.sh` ⭐ NEW
**Purpose**: Complete end-to-end pipeline automation  
**Key Features**:
- Runs all steps automatically
- Analysis → Aggregation → Report
- Single command execution
- Error handling and status reporting

```bash
./scripts/run_full_sn_pipeline.sh \
  --output-dir results/test \
  --max-cats 5 \
  --report test_report.pdf
```

## Utility Modules

### 8. `python/sn_sample_utils.py`
**Purpose**: Data loading and validation utilities  
**Key Functions**:
- `validate_cat_samples()`: Check file availability
- `get_sample_event_ids()`: Extract event IDs by type
- `load_filtered_cluster_images()`: 3-plane cluster matching
- `save_scenario_results()`: JSON serialization

**Key Features**:
- Uses `match_id` for 3-plane alignment
- Tracks cluster statistics (main vs non-main)
- Filters by event IDs and interaction type
- Handles missing/invalid data gracefully

## Workflow Examples

### Quick Test (5 Categories)
```bash
# Single command - complete pipeline
./scripts/run_full_sn_pipeline.sh \
  --output-dir results/test \
  --max-cats 5 \
  --report test_report.pdf
```

### Full Production Run (598 Categories)
```bash
# Full systematic analysis with report
./scripts/run_full_sn_pipeline.sh \
  --output-dir results/full_598 \
  --report full_598_report.pdf
```

### Custom Scenario Selection
```bash
# Run only best case and full pipeline
python3 scripts/run_systematic_sn_analysis.py \
  --cat-dir-parent /eos/project-e/ep-nu/public/sn-pointing \
  --output-dir results/custom \
  --run-best-case \
  --run-full-pipeline \
  [other options...]

# Generate report for selected scenarios
python3 scripts/generate_sn_report.py \
  --results-dir results/custom \
  --output custom_report.pdf \
  --scenarios best_case full_pipeline
```

## Output Structure

```
results/systematic_sn/
├── analysis_summary.json          # Overall summary
├── aggregated_results.json        # Cross-category statistics
├── angular_resolution_comparison.png  # Plot
├── best_case/
│   ├── cat000001/
│   │   └── metrics.json          # Per-category metrics
│   ├── cat000002/
│   └── ...
├── ed_network/
│   └── ...
└── full_pipeline/
    └── ...

sn_report.pdf                      # Comprehensive PDF report
```

## Metrics Tracked

### Per-Category Metrics
- `n_events_processed`: Number of events analyzed
- `angular_resolution`: Median, mean, p68, p90, p95 (degrees)
- `cluster_statistics`:
  - Input cluster counts (total, main, non-main)
  - Matched cluster counts (total, main, non-main)
  - Matching efficiency
- `per_event_results`: Detailed per-event data

### Aggregate Metrics
- Cross-category statistics (median, std)
- Scenario comparisons
- Performance degradation quantification
- Pipeline efficiency tracking

## Documentation

- **SYSTEMATIC_SN_ANALYSIS.md**: Complete usage guide
- **SN_REPORT_GENERATOR.md**: PDF report generator reference
- **README.md**: Project overview and quick start

## Requirements

- Python 3.7+
- TensorFlow 2.x (for neural network models)
- NumPy, SciPy
- matplotlib (for plots and PDF reports)
- uproot (for ROOT file access)

## Key Improvements (Latest Version)

✅ **Correct metadata columns**: Fixed interaction type (column 3), energies, momenta  
✅ **3-plane matching**: Uses `match_id` field for proper cluster alignment  
✅ **Cluster statistics**: Separates main vs non-main electron tracks  
✅ **PDF reporting**: Automated comprehensive report generation  
✅ **Full pipeline script**: Single-command execution  
✅ **Enhanced logging**: Detailed cluster filtering statistics  

## Quick Reference

| Task | Command |
|------|---------|
| Test 5 categories | `./scripts/run_full_sn_pipeline.sh --max-cats 5 --report test.pdf` |
| Full 598 cats | `./scripts/run_full_sn_pipeline.sh --report full.pdf` |
| Generate report | `python3 scripts/generate_sn_report.py --results-dir results/ --output report.pdf` |
| Aggregate only | `python3 scripts/aggregate_sn_results.py --results-dir results/ --plot` |
| Single category | `python3 scripts/run_best_case_sn_analysis.py --cat-dir /path --cat-name cat000001 [...]` |
