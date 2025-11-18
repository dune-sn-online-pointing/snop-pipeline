#!/usr/bin/env python3
"""
Utilities for systematic SN analysis - simplified to use all available events.
"""

import numpy as np
from pathlib import Path
import json


def validate_cat_samples(cat_dir, cat_name, required_es=8, required_cc=83):
    """
    Check if category has sufficient ES and CC tpstream files.
    
    Args:
        cat_dir: Path to category directory
        cat_name: Category name
        required_es: Required ES file count (default: 8)
        required_cc: Required CC file count (default: 83)
    
    Returns:
        tuple: (is_valid, actual_es_files, actual_cc_files)
    """
    tpstream_dir = Path(cat_dir) / 'tpstreams'
    
    if not tpstream_dir.exists():
        return False, 0, 0
    
    es_files = list(tpstream_dir.glob('es_*.root'))
    cc_files = list(tpstream_dir.glob('cc_*.root'))
    
    actual_es = len(es_files)
    actual_cc = len(cc_files)
    is_valid = (actual_es >= required_es) and (actual_cc >= required_cc)
    
    return is_valid, actual_es, actual_cc


def get_sample_event_ids(cat_dir, cat_name, n_es_files=8, n_cc_files=83, seed=42):
    """
    Get all ES and CC event IDs from a category.
    
    Note: Metadata columns (from generate_cluster_arrays.py):
        0: event, 1: is_marley, 2: is_main_track, 3: is_es_interaction,
        4-6: true_pos, 7-9: true_particle_mom, 10: cluster_energy_mev,
        11: true_particle_energy, 12: plane_number, 13: match_id
    
    Args:
        cat_dir: Path to category directory
        cat_name: Category name
        n_es_files: For validation only
        n_cc_files: For validation only
        seed: Not used (kept for API compatibility)
    
    Returns:
        dict: {'es': set of ES event IDs, 'cc': set of CC event IDs}
    """
    is_valid, _, _ = validate_cat_samples(cat_dir, cat_name, n_es_files, n_cc_files)
    
    if not is_valid:
        return None
    
    cluster_dir = Path(cat_dir) / f"{cat_name}_cluster_images_tick3_ch2_min2_tot3_e2p0"
    x_plane_dir = cluster_dir / 'X'
    
    all_es_events = set()
    all_cc_events = set()
    
    for npz_file in sorted(x_plane_dir.glob('*.npz')):
        try:
            data = np.load(npz_file, allow_pickle=True)
            metadata = data['metadata']
            
            event_ids = metadata[:, 0].astype(int)
            is_es_interaction = metadata[:, 3].astype(int)  # Column 3: is_es_interaction
            
            # ES interactions: is_es_interaction == 1
            es_mask = is_es_interaction == 1
            all_es_events.update(event_ids[es_mask])
            
            # CC interactions: is_es_interaction == 0
            cc_mask = is_es_interaction == 0
            all_cc_events.update(event_ids[cc_mask])
            
        except Exception:
            continue
    
    return {'es': all_es_events, 'cc': all_cc_events}


def load_filtered_cluster_images(cat_dir, cat_name, event_ids):
    """
    Load cluster images for specified event IDs, matched across all three planes using match_id.
    
    Clusters are matched using the match_id field (column 13 in metadata).
    Only clusters with match_id >= 0 that appear in ALL three planes are returned.
    
    Returns dict with matched clusters and statistics about filtering.
    """
    cluster_dir = Path(cat_dir) / f"{cat_name}_cluster_images_tick3_ch2_min2_tot3_e2p0"
    
    # Load data from all three planes
    plane_data = {}
    for plane in ['X', 'U', 'V']:
        plane_dir = cluster_dir / plane
        images_list = []
        metadata_list = []
        
        for npz_file in sorted(plane_dir.glob('*.npz')):
            try:
                data = np.load(npz_file, allow_pickle=True)
                images = data['images']
                metadata = data['metadata']
                
                # Filter by event IDs
                event_col = metadata[:, 0].astype(int)
                mask = np.isin(event_col, list(event_ids))
                
                if np.any(mask):
                    images_list.append(images[mask])
                    metadata_list.append(metadata[mask])
                    
            except Exception as e:
                print(f"Warning: Failed to load {npz_file}: {e}")
                continue
        
        if images_list:
            plane_data[plane] = {
                'images': np.concatenate(images_list),
                'metadata': np.concatenate(metadata_list)
            }
        else:
            plane_data[plane] = {
                'images': np.array([]),
                'metadata': np.array([])
            }
    
    # Extract match_ids from each plane (column 13)
    x_match_ids = plane_data['X']['metadata'][:, 13].astype(int) if len(plane_data['X']['metadata']) > 0 else np.array([])
    u_match_ids = plane_data['U']['metadata'][:, 13].astype(int) if len(plane_data['U']['metadata']) > 0 else np.array([])
    v_match_ids = plane_data['V']['metadata'][:, 13].astype(int) if len(plane_data['V']['metadata']) > 0 else np.array([])
    
    # Extract is_main_track for statistics (column 2)
    x_is_main = plane_data['X']['metadata'][:, 2].astype(int) if len(plane_data['X']['metadata']) > 0 else np.array([])
    
    # Find match_ids that appear in ALL three planes and are valid (>= 0)
    x_valid = set(x_match_ids[x_match_ids >= 0])
    u_valid = set(u_match_ids[u_match_ids >= 0])
    v_valid = set(v_match_ids[v_match_ids >= 0])
    
    common_match_ids = x_valid & u_valid & v_valid
    
    if not common_match_ids:
        return {
            'X_images': np.array([]), 'X_events': np.array([]), 'X_metadata': np.array([]),
            'U_images': np.array([]), 'U_events': np.array([]), 'U_metadata': np.array([]),
            'V_images': np.array([]), 'V_events': np.array([]), 'V_metadata': np.array([]),
            'n_input_clusters': len(x_match_ids),
            'n_input_main_clusters': np.sum(x_is_main == 1) if len(x_match_ids) > 0 else 0,
            'n_input_non_main_clusters': len(x_match_ids) - (np.sum(x_is_main == 1) if len(x_match_ids) > 0 else 0),
            'n_matched_clusters': 0,
            'n_matched_main_clusters': 0,
            'n_matched_non_main_clusters': 0
        }
    
    # Sort common match_ids for consistent ordering
    common_match_ids = sorted(common_match_ids)
    
    # Build index mappings for each plane
    result = {}
    for plane in ['X', 'U', 'V']:
        match_ids = plane_data[plane]['metadata'][:, 13].astype(int)
        
        # Find indices of clusters with common match_ids, in order
        indices = []
        for mid in common_match_ids:
            idx = np.where(match_ids == mid)[0]
            if len(idx) > 0:
                indices.append(idx[0])  # Take first occurrence if duplicates
        
        indices = np.array(indices)
        result[f'{plane}_images'] = plane_data[plane]['images'][indices]
        result[f'{plane}_events'] = plane_data[plane]['metadata'][indices, 0].astype(int)
        result[f'{plane}_metadata'] = plane_data[plane]['metadata'][indices]
    
    # Add statistics - separate main vs non-main clusters
    x_is_main = plane_data['X']['metadata'][:, 2].astype(int) if len(plane_data['X']['metadata']) > 0 else np.array([])
    n_input_main = np.sum(x_is_main == 1)
    n_input_non_main = len(x_match_ids) - n_input_main
    
    # For matched clusters, check how many are main
    matched_is_main = result['X_metadata'][:, 2].astype(int)
    n_matched_main = np.sum(matched_is_main == 1)
    n_matched_non_main = len(common_match_ids) - n_matched_main
    
    result['n_input_clusters'] = len(x_match_ids)
    result['n_input_main_clusters'] = n_input_main
    result['n_input_non_main_clusters'] = n_input_non_main
    result['n_matched_clusters'] = len(common_match_ids)
    result['n_matched_main_clusters'] = n_matched_main
    result['n_matched_non_main_clusters'] = n_matched_non_main
    
    return result


def save_scenario_results(output_path, cat_name, scenario_name, metrics):
    """Save per-cat scenario results to JSON."""
    output_dir = Path(output_path) / scenario_name / cat_name
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / 'metrics.json'
    
    def convert_to_native(obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {k: convert_to_native(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_to_native(item) for item in obj]
        else:
            return obj
    
    metrics_native = convert_to_native(metrics)
    
    with open(output_file, 'w') as f:
        json.dump(metrics_native, f, indent=2)
    
    return output_file
