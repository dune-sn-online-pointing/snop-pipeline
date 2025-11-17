#!/usr/bin/env python3
"""
Run MT (Main Track) inference on cat000001 cluster images.
Uses the best trained MT model (v10) to identify main track clusters.
"""

import numpy as np
import json
from pathlib import Path
import argparse
from tqdm import tqdm
import pandas as pd

def load_model(model_path):
    """Load trained MT model from file or directory."""
    print(f"Loading TensorFlow (this may take a minute on first import)...")
    import tensorflow as tf
    
    print(f"Loading model from: {model_path}")
    # Look for .keras file in models subdirectory
    model_file = Path(model_path) / "models" / "best_model.keras"
    if not model_file.exists():
        model_file = Path(model_path) / "best_model.keras"
    if not model_file.exists():
        model_file = Path(model_path)
    
    model = tf.keras.models.load_model(str(model_file))
    print(f"Model loaded successfully")
    return model

def _resolve_cluster_dir(data_dir, plane):
    """Resolve the directory containing plane-specific cluster NPZ files."""
    plane = plane.upper()
    base_path = Path(data_dir)
    if not base_path.exists():
        raise ValueError(f"Directory not found: {base_path}")

    def has_plane_files(path: Path) -> bool:
        return any(path.glob(f"*_plane{plane}.npz"))

    # Direct directory containing NPZ files
    if base_path.is_dir() and has_plane_files(base_path):
        return base_path

    # Plane subdirectory (e.g., .../X)
    plane_dir = base_path / plane
    if plane_dir.is_dir() and has_plane_files(plane_dir):
        return plane_dir

    # Directories that match *cluster_images*
    cluster_dirs = sorted([p for p in base_path.glob("*cluster_images*") if p.is_dir()])
    for cluster_dir in cluster_dirs:
        plane_candidate = cluster_dir / plane
        if plane_candidate.is_dir() and has_plane_files(plane_candidate):
            return plane_candidate
        if has_plane_files(cluster_dir):
            return cluster_dir

    raise ValueError(
        f"Could not locate cluster files for plane {plane} under {data_dir}. "
        "Pass --data-dir pointing directly to the directory that contains the *_planeX.npz files."
    )


def load_cluster_images(data_dir, plane='X', max_files=None):
    """
    Load cluster images from a cat dataset.
    
    Args:
        data_dir: Directory or base path containing cluster images
        plane: Which plane to load (U, V, or X)
        max_files: Maximum number of files to load (None = all)
    
    Returns:
        images: Array of cluster images (N, H, W)
        metadata: Array of metadata (N, 14)
        file_indices: Array mapping each cluster to its source file
    """
    plane = plane.upper()
    cluster_dir = _resolve_cluster_dir(data_dir, plane)
    
    # Get all cluster files (both CC and ES)
    cc_files = sorted(cluster_dir.glob(f"cc_*_bg_matched_plane{plane}.npz"))
    es_files = sorted(cluster_dir.glob(f"es_*_bg_matched_plane{plane}.npz"))
    cluster_files = es_files + cc_files  # ES first, then CC
    
    if max_files:
        cluster_files = cluster_files[:max_files]
    
    print(f"Found {len(es_files)} ES + {len(cc_files)} CC = {len(cluster_files)} total cluster files in {plane} plane")
    
    all_images = []
    all_metadata = []
    all_file_indices = []
    
    for file_idx, cluster_file in enumerate(tqdm(cluster_files, desc="Loading cluster files")):
        data = np.load(cluster_file)
        images = data['images']
        metadata = data['metadata']
        
        all_images.append(images)
        all_metadata.append(metadata)
        all_file_indices.extend([file_idx] * len(images))
    
    images = np.concatenate(all_images, axis=0)
    metadata = np.concatenate(all_metadata, axis=0)
    file_indices = np.array(all_file_indices)
    
    print(f"Loaded {len(images)} total clusters")
    print(f"Image shape: {images.shape}")
    print(f"Metadata shape: {metadata.shape}")
    
    return images, metadata, file_indices

def preprocess_images(images):
    """
    Preprocess images for model input.
    - Add channel dimension
    - DON'T normalize - images are already ADC values in correct range
    """
    # Add channel dimension: (N, H, W) -> (N, H, W, 1)
    images = np.expand_dims(images, axis=-1)
    
    # Convert to float32
    return images.astype(np.float32)

def run_inference(model, images, batch_size=128):
    """
    Run inference on cluster images.
    
    Args:
        model: Trained MT model
        images: Preprocessed images (N, H, W, 1)
        batch_size: Batch size for inference
    
    Returns:
        predictions: Probability of being main track (N,)
    """
    print(f"Running inference on {len(images)} images...")
    
    predictions = []
    n_batches = (len(images) + batch_size - 1) // batch_size
    
    for i in tqdm(range(n_batches), desc="Inference"):
        batch = images[i*batch_size:(i+1)*batch_size]
        pred = model.predict(batch, verbose=0)
        predictions.append(pred)
    
    predictions = np.concatenate(predictions, axis=0).flatten()
    
    return predictions

def save_predictions(output_dir, predictions, metadata, file_indices, threshold=0.5):
    """
    Save MT predictions and identified main track IDs.
    
    Args:
        output_dir: Directory to save results
        predictions: Model predictions (N,)
        metadata: Cluster metadata (N, 14)
        file_indices: File indices for each cluster (N,)
        threshold: Classification threshold
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get metadata columns from generate_cluster_arrays.py:
    # [0] event
    # [1] is_marley (1=signal, 0=background)
    # [2] is_main_track (1=main track, 0=non-main track)
    # [3] is_es_interaction (1=ES, 0=CC)
    # [4-6] position (x, y, z)
    # [7-9] momentum (x, y, z)
    # [10] cluster_energy (ADC-derived MeV)
    # [11] particle_energy (true energy MeV)
    # [12] plane_id (0=U, 1=V, 2=X)
    # [13] match_id
    
    # Create DataFrame with predictions
    results_df = pd.DataFrame({
        'file_index': file_indices,
        'event': metadata[:, 0].astype(int),
        'is_marley': metadata[:, 1].astype(int),
        'is_main_track': metadata[:, 2].astype(int),
        'is_es_interaction': metadata[:, 3].astype(int),
        'pos_x': metadata[:, 4],
        'pos_y': metadata[:, 5],
        'pos_z': metadata[:, 6],
        'momentum_x': metadata[:, 7],
        'momentum_y': metadata[:, 8],
        'momentum_z': metadata[:, 9],
        'cluster_energy': metadata[:, 10],
        'particle_energy': metadata[:, 11],
        'plane_id': metadata[:, 12].astype(int),
        'match_id': metadata[:, 13].astype(int),
        'true_label': metadata[:, 2].astype(int),  # is_main_track (1=main, 0=non-main)
        'prediction_prob': predictions,
        'predicted_label': (predictions >= threshold).astype(int),
    })
    
    # Save full predictions
    predictions_file = output_dir / "mt_predictions.csv"
    results_df.to_csv(predictions_file, index=False)
    print(f"Saved full predictions to: {predictions_file}")
    
    # Save identified main track IDs only
    main_tracks = results_df[results_df['predicted_label'] == 1].copy()
    main_tracks_file = output_dir / "mt_identified_main_tracks.csv"
    main_tracks.to_csv(main_tracks_file, index=False)
    print(f"Saved {len(main_tracks)} identified main tracks to: {main_tracks_file}")
    
    # Save cluster ID mapping for CT processing
    # Format: event -> list of match_ids (these map to cluster IDs in volumes)
    cluster_mapping = {}
    for _, row in main_tracks.iterrows():
        event = int(row['event'])
        match_id = int(row['match_id'])
        if event not in cluster_mapping:
            cluster_mapping[event] = []
        cluster_mapping[event].append(match_id)
    
    mapping_file = output_dir / "mt_cluster_id_mapping.json"
    with open(mapping_file, 'w') as f:
        json.dump(cluster_mapping, f, indent=2)
    print(f"Saved cluster ID mapping to: {mapping_file}")
    
    return results_df

def compute_metrics(results_df, threshold=0.5):
    """
    Compute performance metrics.
    
    Args:
        results_df: DataFrame with predictions and true labels
        threshold: Classification threshold
    
    Returns:
        Dictionary of metrics
    """
    # True labels: 1 = main track (positive class), 0 = non-main track (negative)
    y_true = results_df['true_label']
    y_pred = results_df['predicted_label']
    
    # Compute confusion matrix elements
    tp = np.sum((y_true == 1) & (y_pred == 1))
    tn = np.sum((y_true == 0) & (y_pred == 0))
    fp = np.sum((y_true == 0) & (y_pred == 1))
    fn = np.sum((y_true == 1) & (y_pred == 0))
    
    # Compute metrics
    accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    # Contamination (false positive rate among predicted positives)
    contamination = fp / (tp + fp) if (tp + fp) > 0 else 0
    
    metrics = {
        'threshold': threshold,
        'n_total': len(results_df),
        'n_true_main_tracks': int(np.sum(y_true)),
        'n_predicted_main_tracks': int(np.sum(y_pred)),
        'true_positives': int(tp),
        'true_negatives': int(tn),
        'false_positives': int(fp),
        'false_negatives': int(fn),
        'accuracy': float(accuracy),
        'precision': float(precision),
        'recall': float(recall),
        'f1_score': float(f1),
        'contamination': float(contamination),
    }
    
    return metrics

def main():
    parser = argparse.ArgumentParser(description='Run MT inference on cat datasets')
    parser.add_argument('--model-path', '--model-dir', dest='model_path', type=str, 
                        default='/eos/user/e/evilla/dune/sn-tps/neural_networks/mt_identifier/v10_100k_nov13/mt_identifier_simple_cnn_20251113_145400',
                        help='Path to trained MT model')
    parser.add_argument('--data-dir', type=str,
                        default='/eos/project-e/ep-nu/public/sn-pointing/cat000001',
                        help='Base directory or plane-specific folder containing cluster images')
    parser.add_argument('--output-dir', type=str,
                        default='results/mt_inference_cat000001',
                        help='Directory to save results')
    parser.add_argument('--plane', type=str, default='X',
                        choices=['U', 'V', 'X'],
                        help='Which plane to process')
    parser.add_argument('--threshold', type=float, default=0.5,
                        help='Classification threshold')
    parser.add_argument('--batch-size', type=int, default=128,
                        help='Batch size for inference')
    parser.add_argument('--max-files', type=int, default=None,
                        help='Maximum number of files to process (for testing)')
    
    args = parser.parse_args()
    
    # Load model
    model = load_model(args.model_path)
    
    # Load cluster images
    images, metadata, file_indices = load_cluster_images(
        args.data_dir, 
        plane=args.plane,
        max_files=args.max_files
    )
    
    # Preprocess images
    images = preprocess_images(images)
    
    # Run inference
    predictions = run_inference(model, images, batch_size=args.batch_size)
    
    # Save predictions and IDs
    results_df = save_predictions(
        args.output_dir,
        predictions,
        metadata,
        file_indices,
        threshold=args.threshold
    )
    
    # Compute metrics
    metrics = compute_metrics(results_df, threshold=args.threshold)
    
    # Print metrics
    print("\n" + "="*60)
    print("MT INFERENCE RESULTS")
    print("="*60)
    print(f"Total clusters:           {metrics['n_total']}")
    print(f"True main tracks:         {metrics['n_true_main_tracks']}")
    print(f"Predicted main tracks:    {metrics['n_predicted_main_tracks']}")
    print(f"\nConfusion Matrix:")
    print(f"  True Positives (TP):    {metrics['true_positives']}")
    print(f"  True Negatives (TN):    {metrics['true_negatives']}")
    print(f"  False Positives (FP):   {metrics['false_positives']}")
    print(f"  False Negatives (FN):   {metrics['false_negatives']}")
    print(f"\nPerformance Metrics:")
    print(f"  Accuracy:               {metrics['accuracy']:.4f}")
    print(f"  Precision:              {metrics['precision']:.4f}")
    print(f"  Recall:                 {metrics['recall']:.4f}")
    print(f"  F1 Score:               {metrics['f1_score']:.4f}")
    print(f"  Contamination (FP%):    {metrics['contamination']:.4f}")
    print("="*60)
    
    # Save metrics
    metrics_file = Path(args.output_dir) / "mt_metrics.json"
    with open(metrics_file, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"\nSaved metrics to: {metrics_file}")

if __name__ == "__main__":
    main()
