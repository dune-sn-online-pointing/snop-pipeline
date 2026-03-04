#!/usr/bin/env python3
"""
Metrics Tracker Module

Tracks and persists metrics from each pipeline step to JSON file.
"""

import json
from pathlib import Path
from datetime import datetime
import numpy as np


class MetricsTracker:
    """
    Tracks metrics throughout the pipeline and saves to JSON.
    """
    
    def __init__(self, output_path=None):
        """
        Initialize metrics tracker.
        
        Args:
            output_path: Path to save metrics JSON file
        """
        self.metrics = {
            'pipeline_info': {
                'start_time': datetime.now().isoformat(),
                'version': '2.0'
            },
            'steps': {}
        }
        self.output_path = output_path
        self.step_times = {}
    
    def start_step(self, step_name):
        """Record the start time of a pipeline step."""
        self.step_times[step_name] = datetime.now()
    
    def end_step(self, step_name, metrics_dict=None):
        """
        Record the end time and metrics of a pipeline step.
        
        Args:
            step_name: Name of the pipeline step
            metrics_dict: Optional dictionary of metrics to save
        """
        if step_name not in self.step_times:
            raise ValueError(f"Step '{step_name}' was never started")
        
        duration = (datetime.now() - self.step_times[step_name]).total_seconds()
        
        step_data = {
            'duration_seconds': duration,
            'completed_at': datetime.now().isoformat()
        }
        
        if metrics_dict:
            # Convert numpy types to Python types for JSON serialization
            step_data['metrics'] = self._convert_numpy_types(metrics_dict)
        
        self.metrics['steps'][step_name] = step_data
        
        # Auto-save if output path is set
        if self.output_path:
            self.save()
    
    def add_sample_selection_metrics(self, sample_data):
        """Add metrics from sample selection step."""
        self.metrics['steps']['sample_selection'] = {
            'n_cc_events': sample_data['n_cc_events'],
            'n_es_events': sample_data['n_es_events'],
            'n_cc_clusters': sample_data['n_cc_clusters'],
            'n_es_clusters': sample_data['n_es_clusters'],
            'total_clusters': sample_data['total_clusters'],
            'cc_files_used': len(sample_data['cc_files_used']),
            'es_files_used': len(sample_data['es_files_used'])
        }
    
    def add_cluster_selection_metrics(self, selected_data):
        """Add metrics from cluster selection step."""
        self.metrics['steps']['cluster_selection'] = {
            'selected_clusters': selected_data['total_clusters'],
            'selected_cc_clusters': selected_data['n_cc_clusters'],
            'selected_es_clusters': selected_data['n_es_clusters']
        }
    
    def add_volume_creation_metrics(self, volume_results):
        """Add metrics from volume creation step."""
        self.metrics['steps']['volume_creation'] = {
            'input_clusters': volume_results['n_input_clusters'],
            'volumes_created': volume_results['n_volumes'],
            'success_rate': volume_results['success_rate'],
            'volume_shape': list(volume_results['volume_shape'])
        }
    
    def add_channel_tagging_metrics(self, channel_results):
        """Add metrics from channel tagging step."""
        metrics = channel_results['metrics']
        
        self.metrics['steps']['channel_tagging'] = {
            'input_volumes': len(channel_results['y_true']),
            'predicted_es': channel_results['n_predicted_es'],
            'predicted_cc': channel_results['n_predicted_cc'],
            'confusion_matrix': {
                'true_positives_es': metrics['true_positives'],
                'true_negatives_cc': metrics['true_negatives'],
                'false_positives': metrics['false_positives'],
                'false_negatives': metrics['false_negatives']
            },
            'performance': {
                'accuracy': metrics['accuracy'],
                'precision': metrics['precision'],
                'recall': metrics['recall'],
                'specificity': metrics['specificity'],
                'f1_score': metrics['f1_score'],
                'auc': metrics['auc']
            }
        }
    
    def _convert_numpy_types(self, obj):
        """
        Recursively convert numpy types to Python types for JSON serialization.
        """
        if isinstance(obj, dict):
            return {key: self._convert_numpy_types(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_types(item) for item in obj]
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.int_, np.intc, np.intp, np.int8, np.int16, np.int32, 
                             np.int64, np.uint8, np.uint16, np.uint32, np.uint64)):
            return int(obj)
        elif isinstance(obj, (np.float_, np.float16, np.float32, np.float64)):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        else:
            return obj
    
    def save(self, output_path=None):
        """
        Save metrics to JSON file.
        
        Args:
            output_path: Optional path to save to (overrides instance path)
        """
        path = output_path or self.output_path
        if not path:
            raise ValueError("No output path specified")
        
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Add completion time
        self.metrics['pipeline_info']['end_time'] = datetime.now().isoformat()
        
        with open(path, 'w') as f:
            json.dump(self.metrics, f, indent=2)
    
    def load(self, input_path):
        """
        Load metrics from JSON file.
        
        Args:
            input_path: Path to JSON file
        """
        with open(input_path, 'r') as f:
            self.metrics = json.load(f)
    
    def get_summary(self):
        """
        Get a human-readable summary of the metrics.
        
        Returns:
            str: Formatted summary
        """
        lines = ["Pipeline Metrics Summary", "=" * 60, ""]
        
        # Sample selection
        if 'sample_selection' in self.metrics['steps']:
            ss = self.metrics['steps']['sample_selection']
            lines.append("Sample Selection:")
            lines.append(f"  CC Events: {ss.get('n_cc_events', 'N/A')}")
            lines.append(f"  ES Events: {ss.get('n_es_events', 'N/A')}")
            lines.append(f"  Total Clusters: {ss.get('total_clusters', 'N/A')}")
            lines.append("")
        
        if 'cluster_selection' in self.metrics['steps']:
            cs = self.metrics['steps']['cluster_selection']
            lines.append("Cluster Selection:")
            lines.append(f"  Selected Clusters: {cs.get('selected_clusters', 'N/A')}")
            lines.append(f"  Selected CC Clusters: {cs.get('selected_cc_clusters', 'N/A')}")
            lines.append(f"  Selected ES Clusters: {cs.get('selected_es_clusters', 'N/A')}")
            lines.append("")
        
        # Volume creation
        if 'volume_creation' in self.metrics['steps']:
            vc = self.metrics['steps']['volume_creation']
            lines.append("Volume Creation:")
            lines.append(f"  Input Clusters: {vc.get('input_clusters', 'N/A')}")
            lines.append(f"  Volumes Created: {vc.get('volumes_created', 'N/A')}")
            lines.append(f"  Success Rate: {vc.get('success_rate', 0)*100:.1f}%")
            lines.append("")
        
        # Channel tagging
        if 'channel_tagging' in self.metrics['steps']:
            ct = self.metrics['steps']['channel_tagging']
            lines.append("Channel Tagging:")
            lines.append(f"  Input Volumes: {ct.get('input_volumes', 'N/A')}")
            lines.append(f"  Predicted ES: {ct.get('predicted_es', 'N/A')}")
            lines.append(f"  Predicted CC: {ct.get('predicted_cc', 'N/A')}")
            if 'performance' in ct:
                perf = ct['performance']
                lines.append(f"  Accuracy: {perf.get('accuracy', 0):.4f}")
                lines.append(f"  F1-Score: {perf.get('f1_score', 0):.4f}")
            lines.append("")
        
        return "\n".join(lines)
    
    def print_summary(self):
        """Print the metrics summary to stdout."""
        print(self.get_summary())
