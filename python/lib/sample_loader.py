#!/usr/bin/env python3
"""
Sample Loader Module

Loads cluster images from CC and ES sample folders and selects
a specified number of events from each type.
"""

import numpy as np
from pathlib import Path
import glob


def load_and_select_samples(cc_folder, es_folder, n_cc_events, n_es_events,
                            file_pattern='*_planeX.npz', shuffle=True,
                            random_seed=42, output_dir=None, verbose=False):
    """
    Load and select samples from CC and ES folders.
    
    Selection strategy: Go through files in order, count events (not clusters),
    stop when reaching the target number of events.
    
    Args:
        cc_folder: Path to CC cluster images folder
        es_folder: Path to ES cluster images folder
        n_cc_events: Number of CC events to select
        n_es_events: Number of ES events to select
        file_pattern: File pattern to match (default: *_planeX.npz for X plane only)
        shuffle: Whether to shuffle clusters after selection
        random_seed: Random seed for reproducibility
        output_dir: Optional directory to save selected data
        verbose: Print detailed progress
        
    Returns:
        dict with selected images, metadata, and statistics
    """
    
    if verbose:
        print(f"\nLoading samples:")
        print(f"  CC folder: {cc_folder}")
        print(f"  ES folder: {es_folder}")
        print(f"  Target: {n_cc_events} CC events, {n_es_events} ES events")
    
    # Load CC samples
    cc_data = _load_samples_from_folder(
        cc_folder, n_cc_events, file_pattern, 
        sample_type='CC', verbose=verbose
    )
    
    # Load ES samples
    es_data = _load_samples_from_folder(
        es_folder, n_es_events, file_pattern,
        sample_type='ES', verbose=verbose
    )
    
    # Combine data
    all_images = np.concatenate([cc_data['images'], es_data['images']], axis=0)
    all_metadata = np.concatenate([cc_data['metadata'], es_data['metadata']], axis=0)
    
    # Shuffle if requested
    if shuffle:
        np.random.seed(random_seed)
        indices = np.random.permutation(len(all_images))
        all_images = all_images[indices]
        all_metadata = all_metadata[indices]
        if verbose:
            print(f"\n✓ Shuffled {len(all_images)} clusters")
    
    # Save if output directory specified
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        np.savez(
            output_path / 'selected_samples.npz',
            images=all_images,
            metadata=all_metadata
        )
        
        # Save summary
        with open(output_path / 'selection_summary.txt', 'w') as f:
            f.write(f"Sample Selection Summary\n")
            f.write(f"{'='*60}\n\n")
            f.write(f"CC Events: {cc_data['n_events']} (requested: {n_cc_events})\n")
            f.write(f"CC Clusters: {cc_data['n_clusters']}\n\n")
            f.write(f"ES Events: {es_data['n_events']} (requested: {n_es_events})\n")
            f.write(f"ES Clusters: {es_data['n_clusters']}\n\n")
            f.write(f"Total Clusters: {len(all_images)}\n")
            f.write(f"Shuffled: {shuffle}\n")
            if shuffle:
                f.write(f"Random Seed: {random_seed}\n")
        
        if verbose:
            print(f"\n✓ Saved selected samples to {output_path}")
    
    return {
        'images': all_images,
        'metadata': all_metadata,
        'n_cc_events': cc_data['n_events'],
        'n_es_events': es_data['n_events'],
        'n_cc_clusters': cc_data['n_clusters'],
        'n_es_clusters': es_data['n_clusters'],
        'total_clusters': len(all_images),
        'cc_files_used': cc_data['files_used'],
        'es_files_used': es_data['files_used']
    }


def _load_samples_from_folder(folder, n_events_target, file_pattern, 
                              sample_type='CC', verbose=False):
    """
    Load samples from a single folder until reaching target number of events.
    
    Metadata format (13 columns):
      0: event number
      1: is_marley
            2: selected-cluster flag (legacy field name in source datasets)
      3: is_es_interaction
      4-6: true_pos (x,y,z)
      7-9: true_particle_mom (px,py,pz)
      10: cluster_energy
      11: true_particle_energy
      12: plane_number
    """
    
    folder_path = Path(folder)
    if not folder_path.exists():
        raise ValueError(f"Folder not found: {folder}")
    
    # Find all matching files
    files = sorted(folder_path.glob(file_pattern))
    if not files:
        raise ValueError(f"No files matching pattern '{file_pattern}' in {folder}")
    
    if verbose:
        print(f"\n  {sample_type}: Found {len(files)} files")
    
    images_list = []
    metadata_list = []
    events_seen = set()
    files_used = []
    
    for file_idx, file_path in enumerate(files):
        if len(events_seen) >= n_events_target:
            break
        
        try:
            data = np.load(file_path, allow_pickle=True)
            imgs = data['images']
            meta = data['metadata']
            
            # Process clusters from this file
            for i in range(len(imgs)):
                event_num = int(meta[i, 0])  # Column 0 is event number
                
                if event_num not in events_seen:
                    events_seen.add(event_num)
                    
                    if len(events_seen) > n_events_target:
                        # We've exceeded the target, don't include this cluster
                        break
                
                # Include all clusters from selected events
                if event_num in events_seen and len(events_seen) <= n_events_target:
                    images_list.append(imgs[i])
                    metadata_list.append(meta[i])
            
            files_used.append(str(file_path.name))
            
            if verbose and (file_idx + 1) % 10 == 0:
                print(f"    Processed {file_idx + 1}/{len(files)} files, "
                      f"{len(events_seen)} events, {len(images_list)} clusters", end='\r')
            
            # Stop if we've reached the target
            if len(events_seen) >= n_events_target:
                break
                
        except Exception as e:
            print(f"\n  Warning: Error loading {file_path.name}: {e}")
            continue
    
    if len(events_seen) < n_events_target:
        print(f"\n  WARNING: Only found {len(events_seen)} events "
              f"(requested {n_events_target})")
    
    images = np.array(images_list, dtype=np.float32)
    metadata = np.array(metadata_list, dtype=np.float32)
    
    if verbose:
        print(f"\n  {sample_type}: Loaded {len(events_seen)} events, "
              f"{len(images)} clusters from {len(files_used)} files")
    
    return {
        'images': images,
        'metadata': metadata,
        'n_events': len(events_seen),
        'n_clusters': len(images),
        'files_used': files_used
    }
