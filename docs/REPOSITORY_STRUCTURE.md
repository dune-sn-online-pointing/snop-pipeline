# Data Selection Pipeline - Repository Structure

**Last Updated:** November 21, 2025

## Directory Organization

### Core Analysis Scripts

```
scripts/
├── analysis/                          # Analysis and aggregation scripts
│   ├── analyze_6scenarios_aggregate.py    # EMCEE 6-scenario aggregate analysis
│   ├── plot_electron_skymap.py           # Skymap visualization tool
│   ├── aggregate_pipeline_results.py     # Main pipeline results aggregator
│   ├── aggregate_sn_results.py          # Supernova analysis aggregator
│   └── aggregate_ed_mcmc_results.py     # ED+MCMC results aggregator
└── [other scripts]
```

### Analysis Outputs

```
analysis_outputs/
├── reports/                           # Generated PDF/PNG reports
│   ├── emcee_6scenarios_aggregate_analysis.pdf
│   └── emcee_6scenarios_aggregate_analysis.png
├── figures/                          # Individual plots and figures
├── cat_examples/                     # Example category visualizations
│   └── cat000072*.png               # Skymap examples
└── aggregated_data/                 # Aggregated metrics and results
    ├── aggregated_39cats/
    ├── aggregated_39cats_complete/
    ├── aggregated_complete_report/
    └── aggregated_complete_report_v2/
```

### Condor Job Management

```
condor/
├── logs/                            # HTCondor log files
├── cat_list_batched.txt            # Batched job lists
├── cat_list_resubmit.txt           # Resubmission lists
├── submit_*.sub                    # Condor submit files
└── [job scripts]
```

### Data and Results

```
results/                             # Per-cat and per-scenario results
├── [scenario_name]/
│   └── cat*/
│       └── metrics.json

outputs/                            # Pipeline outputs

logs/                              # Analysis and processing logs
├── aggregation_*.log
└── [other logs]
```

### Python Package

```
python/
├── analysis/                       # Analysis modules
├── [other modules]
└── __init__.py
```

### Documentation

```
docs/
├── REPOSITORY_STRUCTURE.md         # This file
├── axis_aligned_analysis_notes.md  # Analysis methodology notes
├── README_skymap_tool.md          # Skymap tool documentation
└── [other documentation]
```

### Configuration and Dependencies

```
json/                              # Configuration files
external/                          # External dependencies
submodules/                        # Git submodules
├── online-pointing-utils/
└── [other submodules]
```

### Archive

```
archive/
└── test_runs/                    # Archived test/development runs
    ├── test_aggregation/
    └── test_aggregation_multi/
```

## Key Files in Root Directory

- `README.md` - Main project documentation
- `submit_*.sub` - HTCondor submission scripts
- `run_*.sh` - Shell scripts for running analyses
- `.gitignore` - Git ignore patterns
- `.gitmodules` - Git submodule configuration

## Workflow

### 1. Data Processing
Raw data → `results/` directories → organized by scenario and category

### 2. Analysis
Scripts in `scripts/analysis/` → aggregate results → generate metrics

### 3. Visualization
Analysis outputs → `analysis_outputs/reports/` and `analysis_outputs/figures/`

### 4. Documentation
Analysis notes and methodology → `docs/`

## Usage Examples

### Running Aggregate Analysis
```bash
cd scripts/analysis/
python analyze_6scenarios_aggregate.py
```

Output location: `analysis_outputs/reports/emcee_6scenarios_aggregate_analysis.pdf`

### Viewing Results
```bash
# Latest aggregate report
cd analysis_outputs/reports/
evince emcee_6scenarios_aggregate_analysis.pdf

# Example category skymaps
cd analysis_outputs/cat_examples/
display cat000072_final.png
```

### Submitting HTCondor Jobs
```bash
# From repository root
condor_submit submit_6scenarios_emcee.sub
```

## Important Notes

### Data Locations
- **EOS Storage:** `/eos/project-e/ep-nu/evilla/sn-pointing/`
  - Contains per-category data (`cat*` directories)
  - Pipeline outputs stored here
  
- **AFS Work Area:** `/afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline/`
  - Analysis scripts and code
  - Configuration files
  - Aggregated results and reports

### Git Workflow
Repository is tracked with Git:
```bash
# Check status
git status

# View recent changes
git log --oneline -10

# Create feature branch
git checkout -b feature/new-analysis
```

### Backup Strategy
- Critical scripts backed up with `.backup` extension
- Test runs archived in `archive/test_runs/`
- Results on EOS provide redundancy

## Maintenance

### Regular Cleanup Tasks
1. Archive old test runs to `archive/`
2. Remove temporary files and logs
3. Update documentation when adding new scripts
4. Tag stable versions with git tags

### Adding New Analysis Scripts
1. Place in appropriate `scripts/` subdirectory
2. Add documentation to `docs/`
3. Update this structure document if creating new directories
4. Add example usage to README.md

## Contact & Support

For questions about this repository structure:
- Check documentation in `docs/`
- Review commit history for context
- See main `README.md` for project overview

---

**Repository maintained by:** E. Villa  
**Project:** DUNE Supernova Neutrino Pointing Analysis
