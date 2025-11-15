#!/usr/bin/env python3
"""
SN Burst Pipeline - Version 2.0

Pipeline for processing supernova burst samples through the complete
analysis chain: sample selection -> MT identification -> volume creation
-> channel tagging -> (electron direction later)

Processes both CC and ES samples, tracks metrics, generates PDF report.
"""

import sys
import os
import json
import numpy as np
import argparse
from pathlib import Path
from datetime import datetime
import time

# Add python modules to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from sample_loader import load_and_select_samples
from mt_identifier import run_main_track_identification
from volume_creator import create_volumes_for_selected_clusters
from channel_tagger import run_channel_tagging
from metrics_tracker import MetricsTracker
from report_generator import generate_pdf_report


def load_config(config_path):
    """Load and validate JSON configuration."""
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Validate required fields
    required_fields = ['input_data', 'sample_selection', 'neural_networks', 'output']
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
  python pipeline_v2.py -j config.json
  python pipeline_v2.py -j config.json --output /path/to/output
  python pipeline_v2.py -j config.json --verbose
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
    print("SN BURST ANALYSIS PIPELINE - Version 2.0")
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
    
    selected_data = load_and_select_samples(
        cc_folder=config['input_data']['cc_sample_folder'],
        es_folder=config['input_data']['es_sample_folder'],
        n_cc_events=config['sample_selection']['n_cc_events'],
        n_es_events=config['sample_selection']['n_es_events'],
        file_pattern=config['input_data'].get('file_pattern', '*_planeX.npz'),
        shuffle=config['processing'].get('shuffle_clusters', True),
        random_seed=config['processing'].get('random_seed', 42),
        output_dir=output_dir / "selected_clusters",
        verbose=args.verbose
    )
    
    metrics.add_step_metrics('sample_selection', {
        'n_cc_events_requested': config['sample_selection']['n_cc_events'],
        'n_es_events_requested': config['sample_selection']['n_es_events'],
        'n_cc_events_selected': selected_data['n_cc_events'],
        'n_es_events_selected': selected_data['n_es_events'],
        'n_cc_clusters': selected_data['n_cc_clusters'],
        'n_es_clusters': selected_data['n_es_clusters'],
        'total_clusters': selected_data['total_clusters'],
        'execution_time': time.time() - step_start
    })
    
    print(f"\n✓ Sample selection complete ({time.time() - step_start:.1f}s)")
    print(f"  Selected: {selected_data['n_cc_events']} CC events ({selected_data['n_cc_clusters']} clusters)")
    print(f"           {selected_data['n_es_events']} ES events ({selected_data['n_es_clusters']} clusters)")
    print(f"  Total: {selected_data['total_clusters']} clusters")
    
    # =========================================================================
    # STEP 2: Main Track Identification
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 2: MAIN TRACK IDENTIFICATION")
    print("="*80)
    
    step_start = time.time()
    
    mt_results = run_main_track_identification(
        images=selected_data['images'],
        metadata=selected_data['metadata'],
        model_path=config['neural_networks']['main_track_identifier']['model_path'],
        threshold=config['neural_networks']['main_track_identifier']['threshold'],
        output_dir=output_dir / "predictions",
        verbose=args.verbose
    )
    
    metrics.add_step_metrics('main_track_identification', {
        'total_clusters': len(selected_data['images']),
        'predicted_main_tracks': mt_results['n_predicted_mt'],
        'true_main_tracks': mt_results['n_true_mt'],
        'true_positives': mt_results['true_positives'],
        'false_positives': mt_results['false_positives'],
        'true_negatives': mt_results['true_negatives'],
        'false_negatives': mt_results['false_negatives'],
        'accuracy': mt_results['accuracy'],
        'precision': mt_results['precision'],
        'recall': mt_results['recall'],
        'f1_score': mt_results['f1_score'],
        'execution_time': time.time() - step_start
    })
    
    print(f"\n✓ Main track identification complete ({time.time() - step_start:.1f}s)")
    print(f"  Predicted main tracks: {mt_results['n_predicted_mt']}")
    print(f"  Accuracy: {mt_results['accuracy']:.3f}")
    print(f"  Precision: {mt_results['precision']:.3f}")
    print(f"  Recall: {mt_results['recall']:.3f}")
    
    # =========================================================================
    # STEP 3: Volume Creation
    # =========================================================================
    print("\n" + "="*80)
    print("STEP 3: VOLUME IMAGE CREATION")
    print("="*80)
    
    step_start = time.time()
    
    volume_results = create_volumes_for_selected_clusters(
        selected_metadata=mt_results['selected_metadata'],
        selected_indices=mt_results['selected_indices'],
        online_pointing_utils_path=config['volume_creation']['online_pointing_utils_path'],
        output_dir=output_dir / "volume_images",
        verbose=args.verbose
    )
    
    metrics.add_step_metrics('volume_creation', {
        'n_input_clusters': len(mt_results['selected_indices']),
        'n_volumes_created': volume_results['n_volumes_created'],
        'execution_time': time.time() - step_start
    })
    
    print(f"\n✓ Volume creation complete ({time.time() - step_start:.1f}s)")
    print(f"  Volumes created: {volume_results['n_volumes_created']}")
    
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
            'f1_score': 0.0
        }
    else:
        ct_results = run_channel_tagging(
            volume_images=volume_results['images'],
            metadata=volume_results['metadata'],
            model_path=config['neural_networks']['channel_tagger']['model_path'],
            threshold=config['neural_networks']['channel_tagger']['threshold'],
            output_dir=output_dir / "predictions",
            verbose=args.verbose
        )
    
    metrics.add_step_metrics('channel_tagging', {
        'total_volumes': len(volume_results['images']),
        'predicted_es': ct_results['n_predicted_es'],
        'predicted_cc': ct_results['n_predicted_cc'],
        'true_es': ct_results['n_true_es'],
        'true_cc': ct_results['n_true_cc'],
        'true_positives': ct_results['true_positives'],
        'false_positives': ct_results['false_positives'],
        'true_negatives': ct_results['true_negatives'],
        'false_negatives': ct_results['false_negatives'],
        'accuracy': ct_results['accuracy'],
        'precision': ct_results['precision'],
        'recall': ct_results['recall'],
        'f1_score': ct_results['f1_score'],
        'execution_time': time.time() - step_start
    })
    
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
    metrics.set_total_time(total_time)
    metrics.save()
    
    report_path = generate_pdf_report(
        metrics=metrics,
        mt_results=mt_results,
        ct_results=ct_results,
        output_path=output_dir / config['output']['report_pdf'],
        config=config
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
