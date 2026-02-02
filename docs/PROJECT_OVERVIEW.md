# DUNE Data Selection Pipeline - Project Overview

## Project Purpose

This pipeline performs supernova neutrino event reconstruction and analysis for the DUNE experiment. The goal is to estimate the direction and energy of electron neutrinos from supernova events by:

1. **Cluster Tracking (CT)**: Identifying and tracking electron clusters in the detector
2. **Energy Deposition (ED)**: Estimating energy from charge deposits
3. **MCMC Reconstruction**: Using Markov Chain Monte Carlo (emcee) to reconstruct neutrino direction

## Repository Structure

```
data-selection-pipeline/
├── README.md                                    # Main project documentation
├── run_single_cat_emcee_6scenarios.sh          # CRITICAL: Wrapper for Condor jobs
├── scripts/
│   ├── run_cat_analysis_emcee_corrected.py     # CRITICAL: Main analysis script
│   └── [other analysis scripts]
├── json/
│   └── pipeline.json                            # Configuration file
├── python/
│   ├── analysis/                                # Analysis scripts
│   │   ├── analyze_6scenarios_aggregate.py     # Aggregate results from all cats
│   │   ├── compute_cluster_tracking.py         # Cluster tracking metrics
│   │   └── add_tracking*.py                    # Tracking visualization tools
│   ├── visualization/                           # Plotting tools
│   │   └── plot_emcee_results.py
│   └── utils/                                   # Utility functions
├── condor/                                      # HTCondor submission files
│   ├── submit_6scenarios_emcee.sub             # Main submission file
│   ├── submit_idle_cats_resubmit.sub           # Resubmission file
│   ├── check_6scenarios_progress.sh            # Progress monitoring
│   └── [other condor scripts]
├── results/                                     # Output files
│   ├── plots/                                   # Generated plots
│   ├── reports/                                 # PDF reports
│   └── emcee_6scenarios_aggregate_analysis.pdf # Main aggregate report
├── tests/                                       # Test scripts
├── docs/                                        # Documentation
│   ├── PROJECT_OVERVIEW.md                     # This file
│   ├── PROPER_COMMAND_FLAGS.md                 # Command reference
│   ├── USAGE.md                                # Usage guide
│   ├── cat_list.txt                            # List of all cats to process
│   └── [other documentation]
├── logs/                                        # Execution logs
└── outputs/                                     # Processing outputs per cat
```

## Pipeline Architecture

### 6 Scenario Analysis

The pipeline runs 6 different reconstruction scenarios for each CAT (Coherent Activity Time window):

1. **best_case**: Using true electron direction (oracle, best possible performance)
2. **perfect_ct**: Using true electron scattering (ES) hits + Energy Deposition network
3. **full_pipeline**: Complete pipeline with Cluster Tracking + ED network
4. **weighted_ct**: Full pipeline with weighted cluster tracking
5. **perfect_ct_e_gt_10mev**: Perfect CT with energy cut E > 10 MeV
6. **perfect_ct_e_gt_5mev**: Perfect CT with energy cut E > 5 MeV (NEW - changed from 20 MeV)

### Data Flow

```
Raw Data (EOS)
    ↓
CAT Files (cat000001-cat000620)
    ↓
run_single_cat_emcee_6scenarios.sh (HTCondor job)
    ↓
scripts/run_cat_analysis_emcee_corrected.py
    ↓
MCMC Sampling (emcee: 64 walkers, 2000 steps)
    ↓
Output: *_emcee.npz files per scenario
    ↓
analyze_6scenarios_aggregate.py
    ↓
Final Report: emcee_6scenarios_aggregate_analysis.pdf
```

### Key Components

#### 1. Job Submission System (HTCondor)

**Critical Files** (DO NOT MOVE):
- `run_single_cat_emcee_6scenarios.sh` - Main wrapper script
- `scripts/run_cat_analysis_emcee_corrected.py` - Analysis implementation

**Submission Files**:
- `condor/submit_6scenarios_emcee.sub` - Main job submission template
- `condor/submit_idle_cats_resubmit.sub` - Resubmission for failed/idle jobs

**Configuration**:
- JSON file: `json/pipeline.json` - Contains model paths and scenarios
- Cat list: `docs/cat_list.txt` - List of CATs to process (618 total)

**Resource Requirements**:
- 1 CPU
- 1 GPU (T4 or better)
- 32 GB RAM
- 4 GB disk
- Max runtime: 4 hours

#### 2. MCMC Reconstruction (`scripts/run_cat_analysis_emcee_corrected.py`)

Uses the `emcee` package for MCMC sampling:
- **Walkers**: 64 parallel chains
- **Steps**: 2000 total iterations
- **Burn-in**: First 400 steps discarded
- **Prior**: Uniform on unit sphere (neutrino direction)
- **Likelihood**: Gaussian based on angular distance to true direction

For each scenario:
1. Load ES (electron scattering) and CC (charged current) clusters
2. Apply scenario-specific energy cuts if needed
3. Initialize walkers around true direction (for testing)
4. Run MCMC sampling
5. Compute angular error statistics
6. Save results to `*_<scenario>_emcee.npz`

#### 3. Aggregation and Reporting

**Main Script**: `python/analysis/analyze_6scenarios_aggregate.py`

Generates a 5-page PDF report:
- **Page 1**: Aggregate analysis (6 comparison plots)
  - Angular error distributions for all scenarios
  - Box plots, histograms, CDFs, violin plots
  - Statistical comparisons (mean, median, IQR)
  
- **Page 2**: Cosine distributions (full range -1 to 1)
  - cos(θ) distributions with 68% quantiles
  - Angle conversions in legend
  
- **Page 3**: Cosine distributions (zoomed 0.9 to 1.0)
  - High-precision view of best performance region
  
- **Page 4**: Cluster tracking metrics table
  - Number of ES main tracks at each pipeline step
  - Track retention statistics per scenario
  
- **Page 5**: File and cluster distribution histograms
  - ES files per cat (unique clusters)
  - CC files per cat (unique clusters)
  - ES cluster files per cat (all planes U, V, X)
  - CC cluster files per cat (all planes)

#### 4. Cluster Tracking Analysis

**Script**: `python/analysis/compute_cluster_tracking.py`

Tracks how many ES (electron scattering) main tracks survive at each step:
1. Input: Total ES clusters in raw data
2. After CT: Clusters identified by cluster tracking
3. After ED: Clusters with successful energy deposition estimation
4. Final: Clusters used in MCMC reconstruction

## Recent Changes and Job Management

### Energy Cut Update (Nov 20, 2025)

Changed scenario 6 energy threshold:
- **Old**: `perfect_ct_e_gt_20mev` (E > 20 MeV)
- **New**: `perfect_ct_e_gt_5mev` (E > 5 MeV)

**Updated Files**:
- `scripts/run_cat_analysis_emcee_corrected.py`
- `json/pipeline.json`
- `condor/check_6scenarios_progress.sh`

### Idle Job Resubmission (Nov 20, 2025)

**Problem**: Cluster 13792804 had 316 idle jobs on bigbird16.cern.ch

**Actions**:
1. Saved idle cats: `docs/idle_cats_13792804.txt` (cat000303-cat000620)
2. Removed cluster: `condor_rm 13792804`
3. Changed scheduler: `myschedd bump` → bigbird28.cern.ch
4. Resubmitted: New cluster 6417132 with 316 jobs

**Files**:
- `docs/idle_cats_13792804.txt` - List of idle cats
- `docs/cat_list_resubmit.txt` - Resubmission list
- `condor/submit_idle_cats_resubmit.sub` - Resubmission template

## Usage

### Submit New Jobs

```bash
# Edit cat list
vim docs/cat_list.txt

# Submit to HTCondor
condor_submit condor/submit_6scenarios_emcee.sub
```

### Monitor Progress

```bash
# Check job status
condor_q

# Check completion for all 6 scenarios
./condor/check_6scenarios_progress.sh
```

### Generate Aggregate Report

```bash
# After jobs complete, generate PDF report
python3 python/analysis/analyze_6scenarios_aggregate.py
```

### Handle Failed/Idle Jobs

```bash
# Check for idle jobs
condor_q -idle

# Save idle cat list
condor_q <cluster_id> -nobatch | grep -oP 'cat\d{6}' | sort -u > docs/idle_cats_<cluster>.txt

# Remove jobs
condor_rm <cluster_id>

# Change scheduler
myschedd bump

# Resubmit
# (Edit submission file to use idle cat list)
condor_submit condor/submit_idle_cats_resubmit.sub
```

## File Naming Conventions

### Input Files
- CAT directories: `cat000001/`, `cat000002/`, ..., `cat000620/`
- ES files: `cluster_<id>_plane{U,V,X}_es.npz`
- CC files: `cluster_<id>_plane{U,V,X}_cc.npz`

### Output Files
- MCMC results: `<cat_name>_<scenario>_emcee.npz`
- Example: `cat000001_perfect_ct_emcee.npz`

### Reports
- Individual cat: `cat000001_pipeline_report.pdf`
- Aggregate: `emcee_6scenarios_aggregate_analysis.pdf`

## Models and Configuration

### Neural Network Models (from `json/pipeline.json`)
- **ED Model**: Energy deposition estimation network
- **CT Model**: Cluster tracking network
- **PDF File**: Probability density functions for reconstruction

### Data Paths
- **Base Path**: `/eos/user/e/evilla/larsoft-ND-v10-sep2024/`
- **Structure**: Uses `--use-eos-structure` flag for proper directory navigation

## Statistics and Metrics

### Angular Error Metrics
- **Mean Angular Error**: Average θ between reconstructed and true direction
- **Median Angular Error**: 50th percentile
- **68% Quantile**: cos(θ) value containing 68% of samples
- **IQR**: Interquartile range (25th to 75th percentile)

### Comparison Analysis
Report shows:
1. Performance improvement: Perfect CT vs Best Case
2. Pipeline degradation: Full Pipeline vs Perfect CT
3. Weighted CT impact: Weighted CT vs Full Pipeline
4. Energy cut effects: E>10 MeV vs E>3 MeV, E>5 MeV vs E>3 MeV

## Development Notes

### Critical Dependencies
- `emcee`: MCMC sampling
- `numpy`, `scipy`: Numerical computations
- `matplotlib`: Visualization
- `torch`: Neural network inference (ED, CT models)

### File Transfer (HTCondor)
Jobs transfer:
1. `run_single_cat_emcee_6scenarios.sh`
2. `scripts/run_cat_analysis_emcee_corrected.py`
3. `json/pipeline.json`

All other files accessed via shared filesystem (AFS/EOS).

### GPU Requirements
- Jobs request 1 GPU for neural network inference
- Typical runtime: 2-4 hours per CAT (all 6 scenarios)
- GPU used for ED and CT model inference

## Troubleshooting

### Jobs Stay Idle
- Check scheduler load: `condor_status`
- Try different scheduler: `myschedd bump`
- Check GPU availability: Jobs require GPU resources

### Jobs Fail
- Check error logs: `logs/emcee_<cat>_<cluster>.err`
- Verify data exists: Check EOS path for CAT directory
- Test locally: Run wrapper script manually for single CAT

### Missing Results
- Check output directory: `outputs/<cat>/`
- Verify all 6 scenarios completed
- Use progress checker: `condor/check_6scenarios_progress.sh`

## Contact and Support

This is a research pipeline for DUNE supernova neutrino analysis. For questions about:
- Pipeline design: See `docs/USAGE.md`
- Implementation details: See code comments in `scripts/`
- Job submission: See `docs/PROPER_COMMAND_FLAGS.md`

## Version History

- **Nov 20, 2025**: Changed scenario 6 from E>20 MeV to E>5 MeV
- **Nov 20, 2025**: Added file/cluster distribution analysis (Page 5)
- **Nov 19, 2025**: Implemented 6-scenario comparison pipeline
- **Earlier**: Development of CT, ED, and MCMC reconstruction methods

---

*Last Updated: November 20, 2025*
