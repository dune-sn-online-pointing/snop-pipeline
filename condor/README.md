# Condor GPU Job Submission for Pipeline

## Quick Start

### Test Mode with Condor
For testing on a single category (e.g., cat000010):
```bash
python3 scripts/run_pipeline.py --cat cat000010 --enable-ed --use-condor
```

This automatically:
- Uses standard data path: `/eos/user/e/evilla/dune/sn-tps/data/cat000010_volume_images`
- Saves to: `results/pipeline_cat000010`
- Submits to condor GPU queue
- Uses default job duration (1 hour = microcentury)

### Custom Job Duration
```bash
# 20 minutes (for quick tests)
python3 scripts/run_pipeline.py --cat cat000010 --use-condor --condor-flavour espresso

# 2 hours
python3 scripts/run_pipeline.py --cat cat000010 --use-condor --condor-flavour longlunch

# 8 hours (full workday)
python3 scripts/run_pipeline.py --cat cat000010 --use-condor --condor-flavour workday
```

Available flavours:
- `espresso`: 20 minutes
- `microcentury`: 1 hour (default)
- `longlunch`: 2 hours
- `workday`: 8 hours
- `tomorrow`: 1 day
- `testmatch`: 3 days
- `nextweek`: 1 week

### Monitor Jobs
```bash
# Check job status
condor_q <job_id>

# View live output
condor_tail <job_id>

# Check all your jobs
condor_q

# View log files
ls logs/pipeline_*_<job_id>.*
cat logs/pipeline_full_cat000010_<job_id>.out
```

### Local Execution (No Condor)
For immediate local testing (no GPU queue wait):
```bash
python3 scripts/run_pipeline.py --cat cat000010 --skip-ed
```

## Examples

### Full Pipeline with ED on GPU
```bash
python3 scripts/run_pipeline.py \
  --cat cat000010 \
  --enable-ed \
  --use-condor \
  --condor-flavour longlunch \
  --condor-memory 16GB
```

### Just CT + ED (Skip MT)
```bash
python3 scripts/run_pipeline.py \
  --cat cat000010 \
  --skip-mt \
  --enable-ed \
  --use-condor
```

### Custom Paths (Production Mode)
```bash
python3 scripts/run_pipeline.py \
  --data-dir /path/to/data \
  --output-dir results/custom \
  --mt-model /path/to/mt/model \
  --ct-model /path/to/ct/model \
  --enable-ed \
  --ed-model /path/to/ed/model \
  --use-condor \
  --condor-flavour workday
```

## Benefits of Condor Submission

1. **GPU Access**: Jobs run on nodes with GPUs (much faster inference)
2. **No Blocking**: Submit and continue working, job runs in background
3. **Reliability**: Condor handles failures, restarts if needed
4. **Resource Management**: Proper memory/GPU allocation
5. **Job History**: All logs saved automatically

## Flexible Usage

The same script works for:
- **Testing**: `--cat cat000010` for quick checks
- **Local runs**: Without `--use-condor` for immediate results
- **Production**: Full paths with `--use-condor` for large-scale processing
- **Debugging**: Local execution to see errors immediately

## Notes

- GPU is requested when CT or MT inference is needed
- Logs saved to `logs/pipeline_*_<job_id>.*`
- Output goes to directory specified by `--output-dir` (or `results/pipeline_<cat>`)
- Job duration should match expected runtime (use longer flavours for ED+MCMC)

## SN Systematic Analysis (598 Categories)

### GPU-Accelerated Full Analysis

For running the complete systematic analysis across all 598 categories with 3 scenarios (best_case, ed_network, full_pipeline):

```bash
# Direct submission
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline
condor_submit condor/submit_sn_analysis_gpu.sub
```

Or use the helper script:

```bash
# Interactive submission (asks for confirmation)
./condor/submit_gpu_job.sh
```

### Job Configuration

- **GPU**: 1x (A100 or V100 preferred)
- **CPUs**: 4 cores
- **Memory**: 32GB
- **Disk**: 20GB
- **Duration**: 24 hours (tomorrow flavour)
- **Output**: `results/full_598_cats_gpu/`

### Monitor Progress

```bash
# Check job status
condor_q -nobatch | grep sn_analysis

# View live output
tail -f condor/logs/sn_analysis_gpu_*.out

# Check for errors
tail -f condor/logs/sn_analysis_gpu_*.err
```

### After Completion

Once the job finishes, aggregate results and generate PDF report:

```bash
# Aggregate all results
python3 scripts/aggregate_sn_results.py \
  --results-dir results/full_598_cats_gpu \
  --plot

# Generate comprehensive PDF report
python3 scripts/generate_sn_report.py \
  --results-dir results/full_598_cats_gpu \
  --output full_598_gpu_report.pdf
```

The PDF report includes:
- Page 1: Summary statistics for all scenarios
- Page 2: Comparison plots (angular resolution, cluster stats, matching efficiency, per-category trends)
- Page 3: Cosine distribution with 68% quantile

### Expected Runtime

- **Best case scenario**: ~2-4 hours (598 cats, MCMC only)
- **ED network scenario**: ~4-6 hours (598 cats, ED inference + MCMC)
- **Full pipeline scenario**: ~6-10 hours (598 cats, MT→CT→ED→MCMC)
- **Total estimated runtime**: 12-20 hours with GPU acceleration

### Files Generated

```
condor/
├── logs/
│   ├── sn_analysis_gpu_<cluster_id>.out
│   ├── sn_analysis_gpu_<cluster_id>.err
│   └── sn_analysis_gpu_<cluster_id>.log

results/full_598_cats_gpu/
├── best_case/
│   ├── cat000001/metrics.json
│   ├── cat000002/metrics.json
│   └── ...
├── ed_network/
│   └── cat*/metrics.json
├── full_pipeline/
│   └── cat*/metrics.json
├── analysis_summary.json
├── aggregated_results.json
└── plots/
```

### Troubleshooting

If job fails or is held:

```bash
# Check why job is held
condor_q -hold

# View detailed job status
condor_q -better-analyze <cluster_id>

# Remove and resubmit if needed
condor_rm <cluster_id>
condor_submit condor/submit_sn_analysis_gpu.sub
```
