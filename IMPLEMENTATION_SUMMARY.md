# Data Selection Pipeline v2.0 - Implementation Summary

**Date**: 2024
**Project**: SN Burst Event Selection and Analysis

## Overview

Complete redesign of the data-selection-pipeline for processing supernova burst samples with main track identification and channel tagging.

## Files Created

### Core Pipeline

1. **python/app/pipeline_v2.py** (280 lines)
   - Main pipeline orchestrator
   - 5-step workflow: Sample Selection → MT ID → Volume Creation → Channel Tagging → Report
   - JSON configuration loading
   - Comprehensive error handling and timing
   - Metrics tracking integration

2. **json/pipeline_config_template.json**
   - Complete JSON schema for pipeline configuration
   - Sections: input_data, sample_selection, neural_networks, volume_creation, output, processing
   - Documented with descriptions for each field

3. **json/example_config.json**
   - Working example configuration with actual paths
   - Ready to use for testing

### Supporting Modules

4. **python/sample_loader.py** (190 lines)
   - Event-based progressive selection (not cluster-based!)
   - Loads from CC and ES folders
   - Tracks events seen using event numbers (metadata col 0)
   - Stops when reaching target event count
   - Preserves all clusters from selected events

5. **python/mt_identifier.py** (220 lines)
   - Main Track identification using Keras CNN
   - Truth from metadata column 2 (is_main_track)
   - Calculates full confusion matrix, ROC curve, AUC
   - Returns indices of predicted main tracks
   - Performance metrics: accuracy, precision, recall, F1-score

6. **python/volume_creator.py** (180 lines)
   - Creates 3D volumes around main track clusters
   - Interfaces with online-pointing-utils submodule
   - Subprocess call to create_volumes.py script
   - Includes simple mode for testing (2D images as placeholders)
   - Tracks success rate of volume creation

7. **python/channel_tagger.py** (200 lines)
   - Channel tagging for ES vs CC classification
   - Truth from metadata column 3 (is_es_interaction)
   - Binary classification: 0=CC, 1=ES
   - Full metrics calculation with ROC curves
   - Distribution analysis functions

8. **python/metrics_tracker.py** (200 lines)
   - MetricsTracker class for pipeline-wide metrics
   - Step timing and metric collection
   - JSON persistence with numpy type conversion
   - Human-readable summary generation
   - Specialized methods for each pipeline step

9. **python/report_generator.py** (280 lines)
   - PDF report generation with matplotlib
   - 4-page comprehensive report:
     * Page 1: Title and text summary
     * Page 2: Sample flow diagram
     * Page 3: MT identification metrics (confusion matrix, ROC, distributions)
     * Page 4: Channel tagging metrics (confusion matrix, ROC, distributions)
   - Professional formatting with plots

### Documentation

10. **PIPELINE_V2_README.md**
    - Complete documentation for v2.0
    - Pipeline overview and steps
    - Configuration guide with examples
    - Input/output data formats
    - Module descriptions
    - Usage examples
    - Metadata column documentation

## Architecture

### Design Principles

1. **Modular**: Each step is a separate module with clear interfaces
2. **Event-based**: Selection counts events, not clusters
3. **Metadata-aware**: Properly extracts truth labels from correct columns
4. **Metrics-driven**: Comprehensive tracking at each step
5. **Reportable**: Automated PDF generation with visualizations

### Data Flow

```
Input Folders
    ↓
Sample Selection (event-based)
    ↓ (all clusters from selected events)
MT Identification (X-plane clusters)
    ↓ (predicted main tracks)
Volume Creation (3D volumes)
    ↓ (volumes around main tracks)
Channel Tagging (ES vs CC)
    ↓ (classification results)
Report Generation (PDF + JSON metrics)
```

### Metadata Usage

The pipeline correctly uses the 13-column metadata format:

- **Column 0**: Event number - for event counting
- **Column 2**: is_main_track - truth for MT identification
- **Column 3**: is_es_interaction - truth for channel tagging
- **Columns 4-6**: true_pos (x,y,z) - for volume creation
- **Columns 7-9**: true_particle_mom (px,py,pz) - for direction (future use)
- **Column 12**: plane_number - for plane filtering

## Key Features

### 1. Event-Based Selection

Previous versions may have counted clusters. The new pipeline:
- Reads metadata column 0 (event number)
- Tracks which events have been seen
- Stops when reaching target event count
- Includes ALL clusters from selected events

### 2. Progressive File Loading

- Iterates through files in order
- Stops as soon as target is reached
- Tracks which files were used
- Handles incomplete data gracefully

### 3. Comprehensive Metrics

Each step tracks:
- Input/output sample counts
- Confusion matrix (TP/TN/FP/FN)
- Performance metrics (accuracy, precision, recall, F1, AUC)
- ROC curves with FPR/TPR arrays
- Timing information

### 4. Professional Reporting

PDF report includes:
- Summary statistics
- Flow diagram showing sample progression
- Confusion matrices with color coding
- ROC curves
- Prediction probability distributions
- Detailed metrics tables

## Configuration System

### JSON-based Configuration

- Single source of truth for pipeline parameters
- Overridable via command line arguments
- Template provided with documentation
- Example configuration with actual paths

### Configurable Parameters

- Input folders for CC/ES samples
- Target event counts (325 ES, 3300 CC)
- Model paths for MT/CT neural networks
- Classification thresholds
- Output directory structure
- Processing options (shuffle, seed, verbosity)

## Usage Examples

### Basic Run

```bash
python3 python/app/pipeline_v2.py \
    --config json/example_config.json \
    --verbose
```

### Override Event Counts

```bash
python3 python/app/pipeline_v2.py \
    --config json/example_config.json \
    --n-cc-events 1000 \
    --n-es-events 100 \
    --output /path/to/output
```

## Output Products

### 1. Selected Samples
- `selected_samples.npz`: Images + metadata
- `selection_summary.txt`: Event/cluster counts

### 2. MT Identification
- `mt_predictions.npz`: Truth, predictions, probabilities
- `mt_metrics.txt`: Performance metrics
- `selected_main_tracks.npz`: Filtered clusters

### 3. Volumes
- `volumes.npz`: 3D volume images + metadata
- `volume_summary.txt`: Creation statistics

### 4. Channel Tagging
- `channel_predictions.npz`: ES/CC classifications
- `channel_metrics.txt`: Performance metrics

### 5. Final Products
- `pipeline_metrics.json`: All metrics from all steps
- `pipeline_report.pdf`: 4-page visual report

## Testing Strategy

### Module-Level Testing

Each module can be tested independently:

```python
# Test sample loader
from sample_loader import load_and_select_samples
data = load_and_select_samples(
    cc_folder="...", es_folder="...",
    n_cc_events=10, n_es_events=10,
    verbose=True
)

# Test MT identifier
from mt_identifier import identify_main_tracks
results = identify_main_tracks(
    images=data['images'],
    metadata=data['metadata'],
    model_path="...",
    verbose=True
)
```

### Integration Testing

Run full pipeline with small sample counts:

```bash
python3 python/app/pipeline_v2.py \
    --config json/example_config.json \
    --n-cc-events 100 \
    --n-es-events 10 \
    --verbose
```

## Performance Considerations

### Memory Management

- Progressive file loading avoids loading entire dataset
- Batch processing in neural network inference
- Temporary files cleaned up after volume creation

### Scalability

- Can handle large datasets (3300 CC + 325 ES events)
- Configurable batch sizes for inference
- Subprocess timeout for volume creation (5 minutes)

## Future Enhancements

### Potential Additions

1. **Electron Direction**: Add ED neural network for directional reconstruction
2. **Parallel Processing**: Multi-GPU inference for large batches
3. **Data Augmentation**: Optional augmentation during selection
4. **Interactive Dashboard**: Web-based monitoring of pipeline progress
5. **Checkpointing**: Save/resume capability for long runs

### Model Integration

The pipeline is ready to integrate additional models:
- Update JSON config with new model paths
- Add corresponding module (e.g., `electron_direction.py`)
- Update report generator for new visualizations

## Comparison to v1.0

### Major Changes

| Aspect | v1.0 | v2.0 |
|--------|------|------|
| Selection | Cluster-based | Event-based |
| Architecture | Monolithic | Modular |
| Configuration | Hardcoded | JSON-based |
| Metrics | Basic | Comprehensive |
| Reporting | Text only | PDF + JSON |
| Modules | Integrated | Separate files |
| Documentation | Minimal | Extensive |

### Benefits of v2.0

1. **Correctness**: Event counting matches requirements
2. **Maintainability**: Clear module boundaries
3. **Flexibility**: Easy to reconfigure and extend
4. **Observability**: Detailed metrics and visualizations
5. **Reproducibility**: Config files + random seeds
6. **Professionalism**: Publication-ready reports

## Dependencies

### Python Packages

```
tensorflow>=2.0
numpy>=1.19
matplotlib>=3.3
scikit-learn>=0.24
```

### External Tools

- online-pointing-utils (submodule)
- Trained Keras models (.keras files)

## Validation

### Correctness Checks

1. **Event counting**: Verify column 0 used for event numbers
2. **Truth labels**: Verify columns 2 and 3 used correctly
3. **Metadata preservation**: Check all 13 columns maintained
4. **X-plane filtering**: Verify only X-plane data processed

### Expected Results

- MT identification: ~80-90% accuracy (depends on model quality)
- Channel tagging: ~85-95% accuracy (depends on model quality)
- Volume creation: ~100% success rate (should create volume for each cluster)
- Event selection: Exactly 325 ES and 3300 CC events

## Contact & Support

For questions about this pipeline implementation, refer to:
- PIPELINE_V2_README.md for usage
- Module docstrings for API details
- Example config for configuration guidance

## Version Control

**Version**: 2.0
**Status**: Complete implementation, ready for testing
**Next Steps**: Run with real data to validate all modules
