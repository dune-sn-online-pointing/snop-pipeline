# Repository Cleanup Summary

**Date:** November 21, 2025  
**Action:** Repository organization and documentation

## Changes Made

### 1. File Organization

#### Created New Directory Structure
```
analysis_outputs/
├── reports/           # PDF/PNG analysis reports
├── figures/           # Individual plots
├── cat_examples/      # Example category visualizations
└── aggregated_data/   # Aggregated metrics

scripts/analysis/      # Centralized analysis scripts

archive/test_runs/     # Archived test directories
```

#### Files Moved

**Analysis Scripts** → `scripts/analysis/`:
- `analyze_6scenarios_aggregate.py`
- `plot_electron_skymap.py`

**Reports** → `analysis_outputs/reports/`:
- `emcee_6scenarios_aggregate_analysis.pdf`
- `emcee_6scenarios_aggregate_analysis.png`

**Example Figures** → `analysis_outputs/cat_examples/`:
- `cat000072_*.png` (all skymap examples)

**HTCondor Files** → `condor/`:
- `cat_list_batched.txt`
- `cat_list_resubmit.txt`

**Aggregated Data** → `analysis_outputs/aggregated_data/`:
- `aggregated_39cats/`
- `aggregated_39cats_complete/`
- `aggregated_complete_report/`
- `aggregated_complete_report_v2/`

**Test Runs** → `archive/test_runs/`:
- `test_aggregation/`
- `test_aggregation_multi/`

### 2. Documentation Created

#### New Documentation Files

1. **`docs/axis_aligned_analysis_notes.md`**
   - Explains axis-aligned performance analysis
   - Documents non-uniform angular distribution issue
   - Discusses statistical considerations
   - Provides recommendations for future work

2. **`docs/REPOSITORY_STRUCTURE.md`**
   - Complete directory structure documentation
   - Usage examples
   - Workflow descriptions
   - Maintenance guidelines

3. **`docs/CLEANUP_SUMMARY.md`** (this file)
   - Summary of cleanup actions
   - Before/after comparison

#### Existing Documentation
- `README.md` - Main project documentation (unchanged)
- `README_skymap_tool.md` - Skymap tool docs (unchanged)

### 3. Version Control

#### Updated `.gitignore`
Added patterns for:
- Python cache and build files
- Analysis outputs (large PDFs/PNGs)
- Results directories (stored on EOS)
- Log files
- HTCondor outputs
- Backup files
- IDE configurations
- Large data files (*.npz, *.root)
- Archive directory

#### Backup Created
- `analyze_6scenarios_aggregate.py.backup` - Backup of main analysis script

### 4. Analysis Findings Documented

#### Key Issue Identified
**Problem:** X-aligned neutrinos showed unexpectedly better performance than Z-aligned

**Root Causes:**
1. **Non-uniform angular distribution** in input data
   - X-component: 0.559 (dominant)
   - Y-component: 0.477
   - Z-component: 0.443
   - Expected uniform: 0.577

2. **Low statistics** in axis-aligned subsamples
   - ~39-72 total cats analyzed
   - Only ~10-15 events per axis category
   - Statistical fluctuations significant

3. **Sample bias** rather than detector performance
   - Supernova location creates directional bias
   - More X-aligned neutrinos in sample
   - Not indicative of actual detector capability

**Resolution:**
- Documented in `docs/axis_aligned_analysis_notes.md`
- Recommendations provided for future analyses
- Code logic verified as correct (using `abs()` is intentional)

## Repository Status

### Before Cleanup
- Loose files in root directory
- Analysis outputs mixed with code
- Test directories cluttering workspace
- No clear organization
- Undocumented analysis issues

### After Cleanup
- ✅ Organized directory structure
- ✅ Separated code from outputs
- ✅ Archived test runs
- ✅ Comprehensive documentation
- ✅ Analysis considerations documented
- ✅ Clear file locations
- ✅ Updated .gitignore

## Usage

### Finding Files

**Analysis Scripts:**
```bash
cd scripts/analysis/
```

**Latest Reports:**
```bash
cd analysis_outputs/reports/
evince emcee_6scenarios_aggregate_analysis.pdf
```

**Documentation:**
```bash
cd docs/
ls -l *.md
```

### Running Analysis
```bash
cd scripts/analysis/
python analyze_6scenarios_aggregate.py
```
Output automatically goes to `analysis_outputs/reports/`

## Recommendations for Future Work

### Analysis Improvements
1. Generate uniform angular distribution of neutrinos
2. Increase sample size (>50 events per axis)
3. Add statistical uncertainties to plots
4. Include angular distribution plot in reports

### Repository Maintenance
1. Keep analysis outputs in `analysis_outputs/`
2. Archive old test runs regularly
3. Update documentation when adding new scripts
4. Use git tags for stable versions

### Next Steps
- [ ] Regenerate analysis with uniform angular sampling
- [ ] Add statistical error bars to axis-aligned plots
- [ ] Create true direction distribution visualization
- [ ] Increase cat sample size for robust statistics

## Contact

For questions about this cleanup or repository structure:
- See `docs/REPOSITORY_STRUCTURE.md` for detailed structure
- See `docs/axis_aligned_analysis_notes.md` for analysis methodology
- Check git history for detailed change log

---

**Cleanup performed by:** GitHub Copilot (with E. Villa)  
**Date:** November 21, 2025
