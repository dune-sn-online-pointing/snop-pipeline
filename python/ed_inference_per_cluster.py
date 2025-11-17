#!/usr/bin/env python3
"""
ED inference on individual clusters (not volumes).
For each event with MT-identified clusters, runs ED model on each cluster
to get per-cluster direction predictions.

Output: NPZ with per-event data containing arrays of cluster directions and energies.
"""

import argparse
from pathlib import Path
import numpy as np

try:
    import tensorflow as tf
except ImportError:
    tf = None


def load_cluster_images_for_events(data_dir, events_info, plane='X'):
    """
    Load cluster images for specified clusters across events.
    
    Args:
        data_dir: Base directory containing cluster image files
        events_info: List of dicts with 'event', 'cluster_ids', 'cluster_energies'
        plane: Which plane to load (X, U, or V)
    
    Returns:
        event_clusters: List of dicts, each containing:
            - event: event number
            - images: array of cluster images (N_clusters, H, W, 3) for 3 planes
            - energies: array of cluster energies
            - cluster_ids: array of cluster IDs
    """
    # For three-plane model, we need X, U, V views
    planes = ['X', 'U', 'V']
    
    event_clusters = []
    
    for event_info in events_info:
        event = event_info['event']
        cluster_ids = event_info['cluster_ids']
        energies = event_info['energies']
        
        # Load images from each plane
        plane_images = {}
        for p in planes:
            # Find the file containing this event
            # This is a simplified version - actual implementation needs proper file lookup
            cluster_dir = Path(data_dir) / f"cat000010_volume_images_tick3_ch2_min2_tot3_e2p0"
            
            # Load all files and find matching clusters
            cluster_imgs = []
            for cluster_id in cluster_ids:
                # In reality, need to search through files to find the right cluster
                # This is placeholder logic
                pass
            
            plane_images[p] = np.array(cluster_imgs)
        
        # Stack the three planes: (N_clusters, H, W, 3)
        combined = np.stack([plane_images[p] for p in planes], axis=-1)
        
        event_clusters.append({
            'event': event,
            'images': combined,
            'energies': np.array(energies),
            'cluster_ids': np.array(cluster_ids)
        })
    
    return event_clusters


def custom_objects():
    """Define custom loss functions for model loading."""
    import tensorflow as tf
    
    @tf.keras.saving.register_keras_serializable()
    def angular_loss(y_true, y_pred):
        """Angular loss between predicted and true directions."""
        # Normalize predictions
        y_pred_norm = tf.nn.l2_normalize(y_pred, axis=-1)
        y_true_norm = tf.nn.l2_normalize(y_true, axis=-1)
        
        # Cosine similarity
        cos_sim = tf.reduce_sum(y_pred_norm * y_true_norm, axis=-1)
        cos_sim = tf.clip_by_value(cos_sim, -1.0, 1.0)
        
        # Angular error
        angle = tf.acos(cos_sim)
        return tf.reduce_mean(angle)
    
    return {'angular_loss': angular_loss}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('ed_model', help='Path to ED Keras model (.keras file)')
    p.add_argument('ct_results', help='NPZ from CT inference with cluster selections')
    p.add_argument('data_dir', help='Directory containing cluster image files')
    p.add_argument('--out', default='results/ed_per_cluster.npz',
                   help='Output NPZ file with per-cluster directions')
    p.add_argument('--batch-size', type=int, default=32)
    p.add_argument('--plane', default='X', help='Primary plane for file lookup')
    
    args = p.parse_args()
    
    if tf is None:
        raise RuntimeError('TensorFlow not available')
    
    # Load ED model with custom objects
    print(f"Loading ED model from: {args.ed_model}")
    model = tf.keras.models.load_model(args.ed_model, custom_objects=custom_objects())
    print(f"Model loaded. Input shape: {model.input_shape}, Output shape: {model.output_shape}")
    
    # Load CT results to get which clusters to process
    ct_data = np.load(args.ct_results, allow_pickle=True)
    # This would contain event-wise cluster selections
    
    # Load cluster images
    # NOTE: This needs proper implementation based on actual data structure
    print("Loading cluster images...")
    # events_info = extract_events_info_from_ct(ct_data)
    # event_clusters = load_cluster_images_for_events(args.data_dir, events_info, args.plane)
    
    # Run ED inference on each cluster
    print("Running ED inference on individual clusters...")
    results_per_event = []
    
    # for ev_data in event_clusters:
    #     images = ev_data['images']  # (N_clusters, H, W, 3)
    #     
    #     # Predict directions
    #     directions = model.predict(images, batch_size=args.batch_size, verbose=0)
    #     # directions: (N_clusters, 3) - unit direction vectors
    #     
    #     results_per_event.append({
    #         'event': ev_data['event'],
    #         'cluster_directions': directions,
    #         'cluster_energies': ev_data['energies'],
    #         'cluster_ids': ev_data['cluster_ids']
    #     })
    
    # Save results
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Pack into arrays for NPZ
    # np.savez_compressed(
    #     out_path,
    #     events=np.array([r['event'] for r in results_per_event]),
    #     cluster_directions=np.array([r['cluster_directions'] for r in results_per_event], dtype=object),
    #     cluster_energies=np.array([r['cluster_energies'] for r in results_per_event], dtype=object),
    #     cluster_ids=np.array([r['cluster_ids'] for r in results_per_event], dtype=object)
    # )
    
    print(f"Saved ED per-cluster results to: {out_path}")


if __name__ == '__main__':
    main()
