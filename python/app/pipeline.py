#!/usr/bin/env python3
"""
SN Burst Pipeline

Pipeline for processing supernova burst samples through the complete
analysis chain: sample selection -> volume creation
-> channel tagging -> (electron direction later)

Processes both CC and ES samples, tracks metrics, and generates a PDF report.
Cluster selection is performed directly from sampled inputs in the current flow.
"""

import sys
import json
import numpy as np
import argparse
from pathlib import Path
from datetime import datetime
import time

# Add python modules to path
python_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(python_root))
sys.path.insert(0, str(python_root / 'lib'))

from sample_loader import load_and_select_samples
from volume_creator import create_volumes, create_volumes_simple
from channel_tagger import tag_channels
from metrics_tracker import MetricsTracker
from report_generator import generate_report


def load_config(config_path):
    """Load and validate JSON configuration."""
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Validate required fields
    required_fields = ['input_data', 'sample_selection', 'neural_networks', 'output', 'volume_creation']
    for field in required_fields:
        if field not in config:
            raise ValueError(f"Missing required field in config: {field}")
    
    return config


def setup_output_folder(base_folder):
    """Create output directory structure."""
    base_path = Path(base_folder)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = base_path / f"pipeline_run_{timestamp}"
    
    # Create subdirectories
    (output_dir / "selected_clusters").mkdir(parents=True, exist_ok=True)
    (output_dir / "volume_images").mkdir(parents=True, exist_ok=True)
    (output_dir / "predictions").mkdir(parents=True, exist_ok=True)
    (output_dir / "plots").mkdir(parents=True, exist_ok=True)
    
    return output_dir


def main():
    parser = argparse.ArgumentParser(
        description='Run SN Burst Analysis Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python pipeline.py -j config.json
    python pipeline.py -j config.json --output /path/to/output
    python pipeline.py -j config.json --verbose
        """
    )
    parser.add_argument('-j', '--json', '--config', dest='config',
                       required=True, help='JSON configuration file')
    parser.add_argument('-o', '--output', help='Output directory (overrides config)')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Enable verbose output')
    
    args = parser.parse_args()
    
    # Load configuration
    print("="*80)
    print("SN BURST ANALYSIS PIPELINE")
    print("="*80)
    print(f"\nLoading configuration: {args.config}")
    config = load_config(args.config)
    
    # Setup output folder
    output_folder = args.output if args.output else config['output']['base_folder']
    output_dir = setup_output_folder(output_folder)
    print(f"Output directory: {output_dir}")
    
    # Save config copy
    with open(output_dir / "config_used.json", 'w') as f:
        json.dump(config, f, indent=2)
    
    # Initialize metrics tracker
    metrics = MetricsTracker(output_dir / "metrics.json")
    
    # Start timer
    pipeline_start = time.time()
    
    # =========================================================================
    # STEP 1: Load and Select Samples
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 1: SAMPLE SELECTION")
    print("="*80)
    
    step_start = time.time()
    
    cc_folder = config['input_data'].get('cc_sample_folder') or config['input_data'].get('cc_folder')
    es_folder = config['input_data'].get('es_sample_folder') or config['input_data'].get('es_folder')
    if not cc_folder or not es_folder:
        raise ValueError("input_data must define cc_folder/es_folder (or cc_sample_folder/es_sample_folder)")

    selected_data = load_and_select_samples(
        cc_folder=cc_folder,
        es_folder=es_folder,
        n_cc_events=config['sample_selection']['n_cc_events'],
        n_es_events=config['sample_selection']['n_es_events'],
        file_pattern=config['input_data'].get('file_pattern', '*_planeX.npz'),
        cc_file_pattern=config['input_data'].get('cc_file_pattern'),
        es_file_pattern=config['input_data'].get('es_file_pattern'),
        shuffle=config.get('processing', {}).get('shuffle_clusters', config.get('processing', {}).get('shuffle', True)),
        random_seed=config.get('processing', {}).get('random_seed', 42),
        output_dir=output_dir / "selected_clusters",
        verbose=args.verbose
    )
    
    metrics.add_sample_selection_metrics(selected_data)
    
    print(f"\n✓ Sample selection complete ({time.time() - step_start:.1f}s)")
    print(f"  Selected: {selected_data['n_cc_events']} CC events ({selected_data['n_cc_clusters']} clusters)")
    print(f"           {selected_data['n_es_events']} ES events ({selected_data['n_es_clusters']} clusters)")
    print(f"  Total: {selected_data['total_clusters']} clusters")
    
    # =========================================================================
    # STEP 2: Cluster Selection
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 2: TRACK SELECTION")
    print("="*80)
    
    step_start = time.time()

    print("Model-based pre-selection step is disabled in the current pipeline flow.")
    print("Passing selected clusters directly to volume creation.")
    selected_clusters = {
        'images': selected_data['images'],
        'metadata': selected_data['metadata']
    }
    metrics.add_cluster_selection_metrics(selected_data)

    print(f"\n✓ Track selection complete ({time.time() - step_start:.1f}s)")
    print(f"  Clusters forwarded: {selected_data['total_clusters']}")
    
    # =========================================================================
    # STEP 3: Volume Creation
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 3: VOLUME IMAGE CREATION")
    print("="*80)
    
    step_start = time.time()
    
    use_simple_mode = config['volume_creation'].get('use_simple_mode', False)
    if use_simple_mode:
        volume_results = create_volumes_simple(
            images=selected_clusters['images'],
            metadata=selected_clusters['metadata'],
            output_dir=output_dir / "volume_images",
            verbose=args.verbose
        )
    else:
        pointing_utils_dir = config['volume_creation'].get('pointing_utils_dir') or config['volume_creation'].get('online_pointing_utils_path')
        if not pointing_utils_dir:
            raise ValueError("volume_creation must define pointing_utils_dir (or online_pointing_utils_path) when use_simple_mode=false")

        volume_results = create_volumes(
            images=selected_clusters['images'],
            metadata=selected_clusters['metadata'],
            pointing_utils_dir=pointing_utils_dir,
            output_dir=output_dir / "volume_images",
            verbose=args.verbose
        )
    
    metrics.add_volume_creation_metrics(volume_results)
    
    print(f"\n✓ Volume creation complete ({time.time() - step_start:.1f}s)")
    print(f"  Volumes created: {volume_results['n_volumes']}")
    
    # =========================================================================
    # STEP 4: Channel Tagging
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 4: CHANNEL TAGGING")
    print("="*80)
    
    step_start = time.time()
    
    # Channel tagging can be optional via config flag
    if not config['neural_networks'].get('channel_tagger', {}).get('enabled', True):
        print("Channel tagger disabled in config. Skipping channel tagging step.")
        ct_results = {
            'y_true': np.array([], dtype=int),
            'y_pred': np.array([], dtype=int),
            'y_pred_proba': np.array([], dtype=float),
            'total_volumes': len(volume_results.get('images', [])),
            'n_predicted_es': 0,
            'n_predicted_cc': 0,
            'n_true_es': 0,
            'n_true_cc': 0,
            'true_positives': 0,
            'false_positives': 0,
            'true_negatives': 0,
            'false_negatives': 0,
            'accuracy': 0.0,
            'precision': 0.0,
            'recall': 0.0,
            'f1_score': 0.0,
            'metrics': {
                'confusion_matrix': np.array([[0, 0], [0, 0]]),
                'true_positives': 0,
                'true_negatives': 0,
                'false_positives': 0,
                'false_negatives': 0,
                'accuracy': 0.0,
                'precision': 0.0,
                'recall': 0.0,
                'specificity': 0.0,
                'f1_score': 0.0,
                'auc': 0.0,
                'fpr': np.array([0.0, 1.0]),
                'tpr': np.array([0.0, 1.0]),
                'roc_thresholds': np.array([1.0, 0.0])
            }
        }
    else:
        ct_results = tag_channels(
            images=volume_results['images'],
            metadata=volume_results['metadata'],
            model_path=config['neural_networks']['channel_tagger']['model_path'],
            threshold=config['neural_networks']['channel_tagger']['threshold'],
            output_dir=output_dir / "predictions",
            verbose=args.verbose
        )

        y_true = ct_results['y_true']
        ct_results['n_true_es'] = int(np.sum(y_true == 1))
        ct_results['n_true_cc'] = int(np.sum(y_true == 0))
        ct_results['true_positives'] = ct_results['metrics']['true_positives']
        ct_results['false_positives'] = ct_results['metrics']['false_positives']
        ct_results['true_negatives'] = ct_results['metrics']['true_negatives']
        ct_results['false_negatives'] = ct_results['metrics']['false_negatives']
        ct_results['accuracy'] = ct_results['metrics']['accuracy']
        ct_results['precision'] = ct_results['metrics']['precision']
        ct_results['recall'] = ct_results['metrics']['recall']
        ct_results['f1_score'] = ct_results['metrics']['f1_score']
    
    if config['neural_networks'].get('channel_tagger', {}).get('enabled', True):
        metrics.add_channel_tagging_metrics(ct_results)
    
    print(f"\n✓ Channel tagging complete ({time.time() - step_start:.1f}s)")
    print(f"  Predicted ES: {ct_results['n_predicted_es']}")
    print(f"  Predicted CC: {ct_results['n_predicted_cc']}")
    print(f"  Accuracy: {ct_results['accuracy']:.3f}")
    
    # =========================================================================
    # STEP 5: Generate Report
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 5: GENERATING REPORT")
    print("="*80)
    
    step_start = time.time()
    
    total_time = time.time() - pipeline_start
    metrics.metrics['pipeline_info']['total_time_seconds'] = total_time
    metrics.save()
    
    report_filename = config['output'].get('report_pdf', config['output'].get('report_file', 'pipeline_report.pdf'))

    report_path = generate_report(
        metrics_tracker=metrics,
        channel_results=ct_results,
        output_path=output_dir / report_filename,
        verbose=args.verbose
    )
    
    print(f"\n✓ Report generation complete ({time.time() - step_start:.1f}s)")
    print(f"  Report saved: {report_path}")
    
    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "="*80)
    print("PIPELINE COMPLETE")
    print("="*80)
    print(f"\nTotal execution time: {total_time:.1f}s ({total_time/60:.1f} min)")
    print(f"Output directory: {output_dir}")
    print(f"Metrics JSON: {output_dir / 'metrics.json'}")
    print(f"Report PDF: {report_path}")
    print("\n" + "="*80)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nPipeline interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
