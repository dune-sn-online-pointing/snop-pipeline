# SN Burst Data Selection Pipeline v2.0

Redesigned pipeline for supernova burst event selection and analysis.

## Overview

This pipeline processes cluster images from CC and ES burst samples, identifies main tracks, creates volumes, and performs channel tagging to distinguish ES from CC interactions.

## Pipeline Steps

1. **Sample Selection**: Load and select specified number of events from CC/ES folders
2. **Main Track Identification**: Run CNN on X-plane clusters to identify main tracks
3. **Volume Creation**: Create 3D volumes around selected main tracks
4. **Channel Tagging**: Run CNN on volumes to classify ES vs CC
5. **Report Generation**: Generate PDF report with metrics and visualizations

## Configuration

The pipeline is configured via JSON file. See `json/pipeline_config_template.json` for the schema.

### Key Configuration Sections

- **input_data**: Paths to CC and ES sample folders
- **sample_selection**: Number of events to select from each type
- **neural_networks**: Paths to trained models for MT identification and channel tagging
- **volume_creation**: Configuration for volume generation
- **output**: Output directory and file paths
- **processing**: Shuffle, random seed, verbosity options

## Usage

### Basic Usage

```bash
python3 python/app/pipeline_v2.py \
    --config json/my_pipeline_config.json \
    --output /path/to/output \
    --verbose
```

### Create Configuration from Template

```bash
cp json/pipeline_config_template.json json/my_config.json
# Edit my_config.json with your paths and settings
```

### Command Line Options

- `--config`: Path to JSON configuration file (required)
- `--output`: Output directory (overrides config file)
- `--verbose`: Enable detailed progress output
- `--n-cc-events`: Override number of CC events to select
- `--n-es-events`: Override number of ES events to select

## Input Data Format

### Cluster NPZ Files

Expected structure for X-plane cluster files (`*_planeX.npz`):

```python
{
    'images': np.array of shape (N, H, W, C),  # Cluster images
    'metadata': np.array of shape (N, 13)      # Metadata for each cluster
}
```

### Metadata Columns (13 total)

0. `event`: Event number
1. `is_marley`: Marley event flag (0/1)
2. `is_main_track`: Main track truth label (0/1) ← Used for MT identification
3. `is_es_interaction`: ES interaction truth label (0/1) ← Used for channel tagging
4. `true_pos_x`: True position x (cm)
5. `true_pos_y`: True position y (cm)
6. `true_pos_z`: True position z (cm)
7. `true_particle_mom_px`: True momentum px (GeV/c)
8. `true_particle_mom_py`: True momentum py (GeV/c)
9. `true_particle_mom_pz`: True momentum pz (GeV/c)
10. `cluster_energy`: Cluster energy (MeV)
11. `true_particle_energy`: True particle energy (GeV)
12. `plane_number`: Plane number (0=U, 1=V, 2=X)

## Output Structure

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
├── metrics.json
└── report.pdf
```

## Module Descriptions

### sample_loader.py

Loads cluster images from CC and ES folders and selects events progressively.

- **Event-based selection**: Counts events (not clusters) to reach targets
- **Metadata tracking**: Preserves full 13-column metadata
- **File tracking**: Records which files were used

### mt_identifier.py

Runs main track identification neural network on X-plane clusters.

- **Model loading**: Loads Keras model from file
- **Truth extraction**: Uses metadata column 2 (`is_main_track`)
- **Metrics**: Calculates confusion matrix, ROC curve, AUC, F1-score
- **Selection**: Returns indices of predicted main tracks

### volume_creator.py

Creates 3D volumes around main track clusters using online-pointing-utils.

- **Subprocess interface**: Calls `create_volumes.py` from submodule
- **X-plane only**: Processes only X-plane clusters as specified
- **Success tracking**: Tracks volume creation success rate

### channel_tagger.py

Runs channel tagging neural network on volume images.

- **Model loading**: Loads Keras model from file
- **Truth extraction**: Uses metadata column 3 (`is_es_interaction`)
- **Binary classification**: ES (1) vs CC (0)
- **Metrics**: Full performance analysis with ROC curves

### metrics_tracker.py

Tracks and persists metrics from each pipeline step to JSON.

- **Step timing**: Records duration of each pipeline step
- **Metric collection**: Gathers metrics from all steps
- **JSON serialization**: Converts numpy types for storage
- **Summary generation**: Creates human-readable summaries

### report_generator.py

Generates comprehensive PDF reports with plots and metrics.

- **4-page report**:
  - Page 1: Title and summary
  - Page 2: Sample flow diagram
  - Page 3: MT identification metrics
  - Page 4: Channel tagging metrics
- **Visualizations**: Confusion matrices, ROC curves, distributions
- **Performance metrics**: Accuracy, precision, recall, F1-score, AUC

## Performance Metrics

### Main Track Identification

- **Input**: All X-plane clusters from selected events
- **Output**: Subset predicted as main tracks
- **Metrics**: Precision, recall, F1-score for MT identification
- **Truth**: `metadata[:, 2]` (is_main_track)

### Channel Tagging

- **Input**: Volumes created from main tracks
- **Output**: Classification as ES or CC
- **Metrics**: Precision, recall, F1-score for ES identification
- **Truth**: `metadata[:, 3]` (is_es_interaction)

## Example Configuration

```json
{
  "input_data": {
    "cc_folder": "/eos/.../production_cc/images_cc_prod_main",
    "es_folder": "/eos/.../production_es/images_es_prod_main"
  },
  "sample_selection": {
    "n_cc_events": 3300,
    "n_es_events": 325
  },
  "neural_networks": {
    "mt_identifier": "/path/to/mt_model.keras",
    "channel_tagger": "/path/to/ct_model.keras"
  },
  "output": {
    "base_folder": "/eos/.../burst_pipeline_output",
    "metrics_file": "metrics.json",
    "report_file": "report.pdf"
  }
}
```

## Requirements

- Python 3.8+
- TensorFlow 2.x
- NumPy
- Matplotlib
- scikit-learn

## Version History

- **v2.0** (2024): Complete redesign
  - Event-based selection (not cluster-based)
  - Modular architecture with separate components
  - Comprehensive metrics tracking
  - PDF report generation
  - X-plane only processing for volumes

- **v1.0**: Original pipeline
  - Included clustering and pointing steps
  - Different data flow and organization

## Notes

- **X-plane only**: Volume creation and channel tagging use only X-plane data
- **Event counting**: Sample selection counts events, not individual clusters
- **Progressive selection**: Stops when reaching target event count
- **Metadata preservation**: Full 13-column metadata maintained throughout pipeline
