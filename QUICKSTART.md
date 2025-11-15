# Quick Start Guide - Data Selection Pipeline v2.0

## 1. Test the Installation

```bash
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline
./tests/run_tests.sh
```

Expected: `✓ All tests passed!`

## 2. Create Your Configuration

```bash
# Copy the example config
cp json/example_config.json json/my_config.json

# Edit with your paths
vim json/my_config.json
```

Key fields to update:
- `input_data.cc_folder`: Path to CC cluster images
- `input_data.es_folder`: Path to ES cluster images
- `neural_networks.mt_identifier.model_path`: Path to MT model
- `neural_networks.channel_tagger.model_path`: Path to CT model
- `output.base_folder`: Where to save results

## 3. Run the Pipeline

```bash
./scripts/run_pipeline.sh --config json/my_config.json --verbose
```

## 4. Check the Output

The pipeline creates:
```
output_dir/
├── sample_selection/
│   ├── selected_samples.npz
│   └── selection_summary.txt
├── mt_identification/
│   ├── mt_predictions.npz
│   ├── mt_metrics.txt
│   └── selected_main_tracks.npz
├── volume_creation/
│   ├── volumes.npz
│   └── volume_summary.txt
├── channel_tagging/
│   ├── channel_predictions.npz
│   └── channel_metrics.txt
├── pipeline_metrics.json          ← All metrics in one file
└── pipeline_report.pdf            ← Visual report with plots
```

## 5. View the Report

```bash
# Open the PDF report
evince output_dir/pipeline_report.pdf

# Or view metrics as JSON
cat output_dir/pipeline_metrics.json | jq '.'
```

## Command Line Options

```bash
./scripts/run_pipeline.sh \
    --config json/my_config.json \     # Configuration file (required)
    --output /path/to/output \         # Override output directory
    --n-cc-events 1000 \               # Override CC event count
    --n-es-events 100 \                # Override ES event count
    --verbose                          # Detailed progress output
```

## Common Tasks

### Run with Small Sample (Testing)

```bash
./scripts/run_pipeline.sh \
    --config json/example_config.json \
    --n-cc-events 100 \
    --n-es-events 10 \
    --verbose
```

### Run Full Production

```bash
./scripts/run_pipeline.sh \
    --config json/example_config.json \
    --n-cc-events 3300 \
    --n-es-events 325 \
    --output /eos/user/e/evilla/DUNE/solar/burst_analysis_$(date +%Y%m%d)
```

### Check Metrics Only

```bash
# View summary of existing run
cd /path/to/output
cat pipeline_metrics.json | jq '.steps | keys'
cat pipeline_metrics.json | jq '.steps.mt_identification.performance'
cat pipeline_metrics.json | jq '.steps.channel_tagging.performance'
```

## Troubleshooting

### "No module named 'sklearn'"
```bash
# Make sure you're using the wrapper script
./scripts/run_pipeline.sh --config ...

# Or source the environment manually
source scripts/init.sh
```

### "Model file not found"
```bash
# Check your config has correct model paths
cat json/my_config.json | grep model_path

# Verify files exist
ls -lh /path/to/mt_model.keras
ls -lh /path/to/ct_model.keras
```

### "Folder not found"
```bash
# Check input folders are correct
cat json/my_config.json | grep folder

# Verify folders exist and contain data
ls /path/to/cc_folder/*_planeX.npz | head -5
ls /path/to/es_folder/*_planeX.npz | head -5
```

### "Not enough events"
```bash
# Check how many events are available
python3 -c "
import numpy as np
import glob
files = glob.glob('/path/to/folder/*_planeX.npz')
events = set()
for f in files[:10]:
    data = np.load(f)
    events.update(data['metadata'][:, 0].astype(int))
print(f'Found {len(events)} events in first 10 files')
"
```

## Performance Notes

### Timing (Approximate)

For 3300 CC + 325 ES events:
- Sample selection: ~2-5 minutes
- MT identification: ~1-3 minutes (CPU) or ~30 seconds (GPU)
- Volume creation: ~5-10 minutes
- Channel tagging: ~1-2 minutes (CPU) or ~20 seconds (GPU)
- Report generation: ~30 seconds
- **Total**: ~10-20 minutes (CPU) or ~5-10 minutes (GPU)

### Memory Usage

- Peak memory: ~4-8 GB depending on batch sizes
- Safe to run on lxplus login nodes for small samples
- Use HTCondor for large production runs

## Next Steps

1. **Analyze Results**: Open `pipeline_report.pdf` to see performance metrics
2. **Tune Models**: Adjust classification thresholds in config if needed
3. **Scale Up**: Run with full event counts once validated
4. **Automate**: Create job submission scripts for batch processing

## Help

For detailed documentation:
- Pipeline overview: `PIPELINE_V2_README.md`
- Implementation details: `IMPLEMENTATION_SUMMARY.md`
- Environment setup: `ENVIRONMENT_SETUP.md`
