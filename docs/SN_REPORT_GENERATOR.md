# SN Pointing Analysis PDF Report Generator

Generates comprehensive PDF reports for systematic SN pointing analysis results.

## Quick Start

```bash
python3 scripts/generate_sn_report.py \
  --results-dir results/systematic_sn \
  --output sn_pointing_report.pdf
```

## Usage

### Basic Report Generation

```bash
# Full analysis report (all scenarios)
python3 scripts/generate_sn_report.py \
  --results-dir results/systematic_sn \
  --output full_report.pdf

# Test run report
python3 scripts/generate_sn_report.py \
  --results-dir results/systematic_sn_test \
  --output test_report.pdf
```

### Scenario Selection

```bash
# Compare best case vs full pipeline only
python3 scripts/generate_sn_report.py \
  --results-dir results/systematic_sn \
  --output comparison_report.pdf \
  --scenarios best_case full_pipeline

# Single scenario report
python3 scripts/generate_sn_report.py \
  --results-dir results/systematic_sn \
  --output ed_network_report.pdf \
  --scenarios ed_network
```

## Report Contents

### Page 1: Summary Statistics
- Overall analysis summary (number of categories, scenarios completed)
- Per-scenario metrics:
  - Angular resolution (median, mean, p68, p90, std)
  - Cluster statistics (input vs matched, main vs non-main)
  - 3-plane matching efficiency
- Key findings:
  - Pipeline degradation quantification
  - Main track matching rates

### Page 2: Detailed Plots
- **Angular Resolution Comparison**: Box plots comparing all scenarios
- **Cluster Statistics**: Bar charts showing input vs matched clusters (main tracks)
- **Matching Efficiency**: 3-plane matching efficiency distribution
- **Per-Category Trends**: Angular resolution across all categories

## Report Features

- **Automatic aggregation**: Loads and processes results from all categories
- **Statistical analysis**: Computes medians, means, percentiles, standard deviations
- **Visual comparisons**: Side-by-side scenario comparisons
- **Metadata tracking**: Includes generation timestamp and analysis parameters
- **PDF compliance**: Standard PDF format with searchable text and metadata

## Input Structure

The script expects results organized as:
```
results/systematic_sn/
├── best_case/
│   ├── cat000001/
│   │   └── metrics.json
│   ├── cat000002/
│   │   └── metrics.json
│   └── ...
├── ed_network/
│   └── ...
└── full_pipeline/
    └── ...
```

## Output

Single PDF file containing:
- Multi-page report with text summaries and plots
- Embedded metadata (title, author, creation date)
- High-quality vector graphics (matplotlib figures)

## Requirements

- Python 3.7+
- matplotlib
- numpy
- Standard library: json, pathlib, datetime

## Integration with Pipeline

The report generator is designed to run after systematic analysis:

```bash
# 1. Run systematic analysis
python3 scripts/run_systematic_sn_analysis.py [options]

# 2. Aggregate results (optional, for JSON summary)
python3 scripts/aggregate_sn_results.py [options]

# 3. Generate PDF report
python3 scripts/generate_sn_report.py \
  --results-dir results/systematic_sn \
  --output report.pdf
```

## Troubleshooting

**No data found:**
- Check that results directory exists and contains scenario subdirectories
- Verify metrics.json files exist in category subdirectories

**Missing scenarios:**
- Use `--scenarios` to specify only available scenarios
- Check systematic analysis completed successfully

**Empty plots:**
- Verify results contain angular_resolution and cluster_statistics fields
- Check that metrics.json files have valid data (not null values)

## Examples

### Full 598-Category Analysis Report
```bash
python3 scripts/generate_sn_report.py \
  --results-dir results/systematic_sn_full \
  --output full_598cat_report.pdf
```

### Quick Test Report (5 categories)
```bash
python3 scripts/generate_sn_report.py \
  --results-dir results/systematic_sn_test \
  --output test_5cat_report.pdf
```

### Performance Comparison Report
```bash
# Compare best case vs full pipeline to quantify degradation
python3 scripts/generate_sn_report.py \
  --results-dir results/systematic_sn \
  --output performance_comparison.pdf \
  --scenarios best_case full_pipeline
```
