#!/usr/bin/env python3
"""
Run CT (Cluster Type) inference on volume images.
Uses selected cluster IDs to choose relevant volumes.
"""

import numpy as np
import tensorflow as tf
import json
from pathlib import Path
import argparse
from tqdm import tqdm
import pandas as pd

def load_model(model_path):
    """Load trained CT model."""
    print(f"Loading model from: {model_path}")
    model = tf.keras.models.load_model(model_path)
    print(f"Model loaded successfully")
    return model

def load_selected_cluster_mapping(mapping_file):
    """
    Load selected cluster IDs.
    
    Args:
        mapping_file: JSON file with event -> cluster_id mapping
    
    Returns:
        Dictionary mapping event -> list of selected cluster IDs
    """
    with open(mapping_file, 'r') as f:
        mapping = json.load(f)
    
    # Convert string keys back to integers
    mapping = {int(k): v for k, v in mapping.items()}
    
    print(f"Loaded cluster mapping for {len(mapping)} events")
    total_clusters = sum(len(v) for v in mapping.values())
    print(f"Total selected clusters: {total_clusters}")
    
    return mapping

def _resolve_volume_dir(data_dir):
    """Resolve directory that contains volume image NPZ files."""
    base_path = Path(data_dir)
    if not base_path.exists():
        raise ValueError(f"Directory not found: {base_path}")

    def has_npz(path: Path) -> bool:
        return any(path.glob("*.npz"))

    if base_path.is_dir() and has_npz(base_path):
        return base_path

    volume_dirs = sorted([p for p in base_path.glob("*volume_images*") if p.is_dir()])
    if not volume_dirs:
        raise ValueError(
            f"Could not locate a volume_images directory under {data_dir}. "
            "Pass --data-dir pointing directly to the *_volume_images* folder."
        )

    # Prefer directory that includes the base name (cat id)
    for cand in volume_dirs:
        if base_path.name and base_path.name in cand.name:
            return cand

    return volume_dirs[0]


def load_volume_images(data_dir, cluster_mapping, plane='X', skip_ct=False):
    """
    Load volume images from a cat dataset.
    Only loads volumes containing selected cluster IDs.
    
    Args:
        data_dir: Base directory or volume folder containing images
        cluster_mapping: Dictionary mapping event -> cluster IDs
        plane: Which plane to load (U, V, or X)
        skip_ct: If True, assume perfect CT tagging (all selected clusters accepted)
    
    Returns:
        images: List of volume images (variable size)
        metadata: List of metadata dictionaries
        selected_indices: Indices of volumes that contain selected clusters
    """
    plane = plane.upper()
    volume_dir = _resolve_volume_dir(data_dir)
    
    # Get all volume files for the selected plane
    volume_files = sorted(volume_dir.glob(f"*plane{plane}.npz"))
    
    print(f"Loading volumes from: {volume_dir}")
    print(f"Found {len(volume_files)} volume files for plane {plane}")
    
    images = []
    metadata_list = []
    selected_indices = []
    skipped_no_match = 0
    skipped_wrong_cluster = 0
    
    for volume_file in tqdm(volume_files, desc="Loading volume files"):
        data = np.load(volume_file, allow_pickle=True)
        volume_images = data['images']
        volume_metadata = data['metadata']
        
        for i, meta in enumerate(volume_metadata):
            event = meta['event']
            main_cluster_id = meta['main_cluster_id']
            
            # Check if this volume contains a selected cluster
            if event in cluster_mapping:
                if main_cluster_id in cluster_mapping[event]:
                    images.append(volume_images[i])
                    metadata_list.append(meta)
                    selected_indices.append((volume_file.stem, i))
                else:
                    skipped_wrong_cluster += 1
            else:
                skipped_no_match += 1
    
    print(f"\nSelected {len(images)} volumes")
    print(f"Skipped {skipped_no_match} volumes (event not in selection mapping)")
    print(f"Skipped {skipped_wrong_cluster} volumes (cluster ID not in selection mapping)")
    
    if skip_ct:
        print("\n*** SKIP_CT MODE: Assuming perfect CT tagging ***")
        print("All selected volumes are treated as accepted by selection")
    
    return images, metadata_list, selected_indices

def preprocess_volume(volume):
    """
    Preprocess volume for model input.
    - Normalize using log transform
    - Pad/crop to fixed size if needed
    """
    volume = np.asarray(volume, dtype=np.float32)
    # Add channel dimension if needed: (H, W) -> (H, W, 1)
    if len(volume.shape) == 2:
        volume = np.expand_dims(volume, axis=-1)
    
    # Normalize using log transform
    volume = np.log1p(volume)
    
    # Scale to [0, 1]
    max_val = np.max(volume)
    if max_val > 0:
        volume = volume / max_val
    
    return volume.astype(np.float32)

def run_inference(model, images, batch_size=32, skip_ct=False):
    """
    Run inference on volume images.
    
    Args:
        model: Trained CT model (or None if skip_ct=True)
        images: List of volume images (variable size)
        batch_size: Batch size for inference
        skip_ct: If True, skip actual inference and return dummy predictions
    
    Returns:
        predictions: Probability of each cluster being ES (per volume)
    """
    if skip_ct:
        print("Skipping CT inference (assuming perfect tagging)")
        # Return dummy predictions (all 1.0 for accepted cluster)
        return [np.ones(1) for _ in images]
    
    print(f"Running CT inference on {len(images)} volumes...")
    
    predictions = []
    
    # Process images individually (variable size)
    for img in tqdm(images, desc="CT Inference"):
        # Preprocess
        img_processed = preprocess_volume(img)
        img_batch = np.expand_dims(img_processed, axis=0)
        
        # Predict
        pred = model.predict(img_batch, verbose=0)
        predictions.append(pred[0])
    
    return predictions

def save_predictions(output_dir, predictions, metadata_list, selected_indices, skip_ct=False):
    """
    Save CT predictions.
    
    Args:
        output_dir: Directory to save results
        predictions: Model predictions (list of arrays)
        metadata_list: List of metadata dictionaries
        selected_indices: List of (file, index) tuples
        skip_ct: Whether CT was skipped
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create results DataFrame
    results = []
    for i, (pred, meta, (file, idx)) in enumerate(zip(predictions, metadata_list, selected_indices)):
        # Get number of clusters in this volume
        n_clusters = meta['n_clusters_in_volume']
        n_marley = meta['n_marley_clusters']
        n_non_marley = meta['n_non_marley_clusters']
        
        result = {
            'volume_index': i,
            'source_file': file,
            'file_volume_index': idx,
            'event': meta['event'],
            'plane': meta['plane'],
            'main_cluster_id': meta['main_cluster_id'],
            'n_clusters_in_volume': n_clusters,
            'n_marley_clusters': n_marley,
            'n_non_marley_clusters': n_non_marley,
            'particle_energy': meta['particle_energy'],
            'cluster_energy': meta['cluster_energy'],
            'avg_marley_distance_cm': meta.get('avg_marley_cluster_distance_cm', -1),
            'max_marley_distance_cm': meta.get('max_marley_cluster_distance_cm', -1),
        }
        
        # Add predictions (can be multiple if volume has multiple clusters)
        if isinstance(pred, (list, np.ndarray)) and len(pred) > 1:
            # Multiple cluster predictions
            for j, p in enumerate(pred):
                result[f'cluster_{j}_prob'] = float(p)
        else:
            # Single prediction
            result['selected_cluster_prob'] = float(pred[0] if isinstance(pred, np.ndarray) else pred)
        
        results.append(result)
    
    results_df = pd.DataFrame(results)
    
    # Save results
    predictions_file = output_dir / "ct_predictions.csv"
    results_df.to_csv(predictions_file, index=False)
    print(f"Saved CT predictions to: {predictions_file}")
    
    return results_df

def compute_metrics(results_df, skip_ct=False):
    """
    Compute CT performance metrics.
    
    Args:
        results_df: DataFrame with predictions
        skip_ct: Whether CT was skipped (perfect tagging assumed)
    
    Returns:
        Dictionary of metrics
    """
    n_volumes = len(results_df)
    total_clusters = results_df['n_clusters_in_volume'].sum()
    total_marley = results_df['n_marley_clusters'].sum()
    total_non_marley = results_df['n_non_marley_clusters'].sum()
    
    # Average contamination (non-Marley clusters per volume)
    avg_contamination = results_df['n_non_marley_clusters'].mean()
    contamination_rate = total_non_marley / total_clusters if total_clusters > 0 else 0
    
    metrics = {
        'skip_ct': skip_ct,
        'n_volumes': int(n_volumes),
        'total_clusters': int(total_clusters),
        'total_marley_clusters': int(total_marley),
        'total_non_marley_clusters': int(total_non_marley),
        'avg_clusters_per_volume': float(total_clusters / n_volumes) if n_volumes > 0 else 0,
        'avg_marley_per_volume': float(total_marley / n_volumes) if n_volumes > 0 else 0,
        'avg_non_marley_per_volume': float(avg_contamination),
        'contamination_rate': float(contamination_rate),
        'purity': float(total_marley / total_clusters) if total_clusters > 0 else 0,
    }
    
    return metrics

def main():
    parser = argparse.ArgumentParser(description='Run CT inference on cat000001 data')
    parser.add_argument('--model-path', type=str,
                        default='/eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/v40_corrected_10k/20251114_225600/best_model.keras',
                        help='Path to trained CT model (ignored if --skip-ct)')
    parser.add_argument('--data-dir', type=str,
                        default='/eos/project-e/ep-nu/public/sn-pointing/cat000001',
                        help='Base directory containing cat000001 data')
    parser.add_argument('--selected-mapping', dest='selected_mapping', type=str,
                        default='results/selection_cat000001/selected_cluster_mapping.json',
                        help='Path to selected cluster ID mapping file')
    parser.add_argument('--output-dir', type=str,
                        default='results/ct_inference_cat000001',
                        help='Directory to save results')
    parser.add_argument('--plane', type=str, default='X',
                        choices=['U', 'V', 'X'],
                        help='Which plane to process')
    parser.add_argument('--batch-size', type=int, default=32,
                        help='Batch size for inference')
    parser.add_argument('--skip-ct', action='store_true',
                        help='Skip CT inference, assume perfect tagging (for benchmarking)')
    parser.add_argument('--ed-volumes-npz', type=str, default=None,
                        help='If provided, save stacked volumes/metadata for ED inference to this NPZ path')
    parser.add_argument('--ed-selected-mask-npz', dest='ed_selected_mask_npz', type=str, default=None,
                        help='If provided, save selection mask and tentative directions for ED inference to this NPZ path')
    
    args = parser.parse_args()
    
    # Load selected cluster mapping
    cluster_mapping = load_selected_cluster_mapping(args.selected_mapping)
    
    # Load model (unless skipping CT)
    model = None
    if not args.skip_ct:
        model = load_model(args.model_path)
    
    # Load volume images
    images, metadata_list, selected_indices = load_volume_images(
        args.data_dir,
        cluster_mapping,
        plane=args.plane,
        skip_ct=args.skip_ct
    )
    
    if len(images) == 0:
        print("No volumes found matching selected clusters!")
        return
    
    # Optionally persist ED payloads before inference to avoid duplicating work
    if args.ed_volumes_npz or args.ed_selected_mask_npz:
        volumes_array = np.stack([np.asarray(img) for img in images])
        cluster_energy = np.array([
            meta.get('cluster_energy', np.nan) for meta in metadata_list
        ], dtype=np.float32)
        events = np.array([meta.get('event', -1) for meta in metadata_list], dtype=np.int64)
        cluster_ids = np.array([meta.get('main_cluster_id', -1) for meta in metadata_list], dtype=np.int64)
        momentum_components = np.array([
            [
                meta.get('main_track_momentum_x', 0.0),
                meta.get('main_track_momentum_y', 0.0),
                meta.get('main_track_momentum_z', 0.0),
            ]
            for meta in metadata_list
        ], dtype=np.float32)
        norms = np.linalg.norm(momentum_components, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        tentative_dirs = momentum_components / norms

        if args.ed_volumes_npz:
            ed_vol_path = Path(args.ed_volumes_npz)
            ed_vol_path.parent.mkdir(parents=True, exist_ok=True)
            save_dict = {
                'volumes': volumes_array,
                'event': events,
                'main_cluster_id': cluster_ids,
                'true_direction': tentative_dirs,  # True neutrino direction
            }
            if not np.all(np.isnan(cluster_energy)):
                save_dict['cluster_energy'] = cluster_energy
            np.savez_compressed(ed_vol_path, **save_dict)
            print(f"Saved ED volumes payload to: {ed_vol_path}")

        if args.ed_selected_mask_npz:
            selected_npz_path = Path(args.ed_selected_mask_npz)
            selected_npz_path.parent.mkdir(parents=True, exist_ok=True)
            selected_payload = {
                'is_selected_cluster': np.ones(len(images), dtype=bool),
                'tentative_dirs': tentative_dirs,
                'event': events,
                'main_cluster_id': cluster_ids,
            }
            np.savez_compressed(selected_npz_path, **selected_payload)
            print(f"Saved ED selection payload to: {selected_npz_path}")

    # Run inference
    predictions = run_inference(
        model,
        images,
        batch_size=args.batch_size,
        skip_ct=args.skip_ct
    )
    
    # Save predictions
    results_df = save_predictions(
        args.output_dir,
        predictions,
        metadata_list,
        selected_indices,
        skip_ct=args.skip_ct
    )
    
    # Compute metrics
    metrics = compute_metrics(results_df, skip_ct=args.skip_ct)
    
    # Print metrics
    print("\n" + "="*60)
    print("CT INFERENCE RESULTS")
    print("="*60)
    print(f"Volumes processed:        {metrics['n_volumes']}")
    print(f"Total clusters:           {metrics['total_clusters']}")
    print(f"Marley clusters:          {metrics['total_marley_clusters']}")
    print(f"Non-Marley clusters:      {metrics['total_non_marley_clusters']}")
    print(f"\nPer-Volume Statistics:")
    print(f"  Avg clusters/volume:    {metrics['avg_clusters_per_volume']:.2f}")
    print(f"  Avg Marley/volume:      {metrics['avg_marley_per_volume']:.2f}")
    print(f"  Avg non-Marley/volume:  {metrics['avg_non_marley_per_volume']:.2f}")
    print(f"\nPurity Metrics:")
    print(f"  Purity (Marley%):       {metrics['purity']:.4f}")
    print(f"  Contamination rate:     {metrics['contamination_rate']:.4f}")
    
    if args.skip_ct:
        print(f"\n*** SKIP_CT MODE ACTIVE ***")
        print(f"CT inference was skipped - assuming perfect tagging")
    
    print("="*60)
    
    # Save metrics
    metrics_file = Path(args.output_dir) / "ct_metrics.json"
    with open(metrics_file, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"\nSaved metrics to: {metrics_file}")

if __name__ == "__main__":
    main()
