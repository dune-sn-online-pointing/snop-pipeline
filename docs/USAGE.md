# Pipeline Usage Guide

## Summary of Changes

1. **Added True Neutrino Direction Comparison**: ED metrics now include precision vs. ground truth
2. **Flexible Condor GPU Submission**: Easy job submission with `--use-condor`
3. **Quick Test Mode**: Use `--cat <name>` for standard category testing

## Quick Commands

### Test Locally (No GPU Queue)
```bash
# Fast test without ED
python3 scripts/run_pipeline.py --cat cat000010

# With ED (takes longer)
python3 scripts/run_pipeline.py --cat cat000010 --enable-ed
```

### Submit to Condor GPU Queue
```bash
# Quick test (1 hour limit)
python3 scripts/run_pipeline.py --cat cat000010 --enable-ed --use-condor

# Longer job (2 hours)
python3 scripts/run_pipeline.py --cat cat000010 --enable-ed --use-condor --condor-flavour longlunch

# Full production (8 hours)
python3 scripts/run_pipeline.py --cat cat000010 --enable-ed --use-condor --condor-flavour workday
```

### Monitor Jobs
```bash
# Check status
condor_q

# Check specific job
condor_q <job_id>

# View logs
ls logs/pipeline_*.out
tail -f logs/pipeline_full_cat000010_<job_id>.out
```

## What's New

### 1. True Direction Metrics
The ED report now includes precision vs. true neutrino direction:
- **Median error**: Median angle between reconstructed and true direction
- **68% containment**: 68% of events within this angle
- **90% containment**: 90% of events within this angle

These metrics use `main_track_momentum_{x,y,z}` from volume metadata as ground truth.

### 2. Condor Integration
- GPU jobs run on Tesla V100 nodes (much faster)
- Jobs run in background - you can logout
- Flexible job duration (20min to 1 week)
- Same script for testing and production

### 3. Quick Test Mode
Instead of specifying full paths:
```bash
--data-dir /eos/project-e/ep-nu/public/sn-pointing/cat000010 \
--output-dir results/pipeline_cat000010
```

Just use:
```bash
--cat cat000010
```

## Technical Details

### Modified Files
1. **`scripts/run_ct_inference.py`**: Saves `true_direction` in ED volumes NPZ
2. **`python/ed_inference_from_mt.py`**: Passes true direction through to MCMC
3. **`scripts/run_pipeline.py`**: 
   - Computes precision metrics (true vs reconstructed direction)
   - Adds `--cat`, `--use-condor`, `--condor-flavour`, `--condor-memory` arguments
   - Generates precision plot and metrics in reports
4. **`python/condor_helper.py`**: New module for job submission
5. **`condor/run_pipeline_wrapper.sh`**: New wrapper script for condor execution
6. **`condor/submit_pipeline.sub`**: Template for condor submit files

### Output Changes
- **Summary text**: Now shows "PRECISION vs TRUE ν DIRECTION" section
- **PDF plots**: New plot #11 shows angular error distribution
- **Text report**: Includes median/mean/p68/p90 angular errors

## Examples

### Development/Debugging
```bash
# Run locally to see errors immediately
python3 scripts/run_pipeline.py --cat cat000010 --max-files 1
```

### Production Run
```bash
# Submit long job for full analysis with ED
python3 scripts/run_pipeline.py \
  --cat cat000010 \
  --enable-ed \
  --mcmc-steps 5000 \
  --use-condor \
  --condor-flavour workday \
  --condor-memory 16GB
```

### Skip Steps for Testing
```bash
# Skip MT (use existing results)
python3 scripts/run_pipeline.py --cat cat000010 --skip-mt --use-condor

# Skip CT (assume perfect tagging)
python3 scripts/run_pipeline.py --cat cat000010 --skip-ct --use-condor
```

## Best Practices

1. **Testing**: Always test locally first with `--max-files 1`
2. **Job Duration**: Match to expected runtime:
   - Without ED: `microcentury` (1h)
   - With ED: `longlunch` (2h) or `workday` (8h)
3. **Memory**: Default 8GB is usually enough, use 16GB for large datasets
4. **Monitoring**: Check logs regularly to catch issues early

## Troubleshooting

### Job Failed
```bash
# Check error log
cat logs/pipeline_full_cat000010_<job_id>.err

# Check output log
cat logs/pipeline_full_cat000010_<job_id>.out
```

### Job Stuck
```bash
# Check if still running
condor_q <job_id>

# Check node it's on
condor_q -l <job_id> | grep RemoteHost

# Remove if needed
condor_rm <job_id>
```

### Local Test Before Submission
```bash
# Test the exact command that will run on condor
python3 scripts/run_pipeline.py --cat cat000010 --enable-ed --max-files 1
```
