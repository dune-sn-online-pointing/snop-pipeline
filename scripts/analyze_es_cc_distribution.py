#!/usr/bin/env python3
"""
Analyze cluster metadata to understand ES vs CC distribution.
"""

import numpy as np
from pathlib import Path
import argparse


def analyze_category(cat_name):
    """Analyze ES/CC distribution for a category."""
    
    print(f"\n{'='*60}")
    print(f"Analyzing {cat_name}")
    print(f"{'='*60}\n")
    
    # Path structure: /eos/project-e/ep-nu/public/sn-pointing/{cat_name}/{cat_name}_cluster_images_tick3_ch2_min2_tot3_e2p0/X
    cat_dir = Path(f"/eos/project-e/ep-nu/public/sn-pointing/{cat_name}")
    cluster_dir = cat_dir / f"{cat_name}_cluster_images_tick3_ch2_min2_tot3_e2p0" / "X"
    
    if not cluster_dir.exists():
        print(f"✗ Directory not found: {cluster_dir}")
        return
    
    npz_files = sorted(cluster_dir.glob("*.npz"))
    
    print(f"Found {len(npz_files)} NPZ files in:")
    print(f"  {cluster_dir}")
    
    if len(npz_files) == 0:
        print("✗ No NPZ files found")
        return
    
    # Check filenames for ES/CC
    es_files = [f for f in npz_files if '_es_' in f.name.lower()]
    cc_files = [f for f in npz_files if '_cc_' in f.name.lower()]
    
    print(f"  Files with 'es' in name: {len(es_files)}")
    print(f"  Files with 'cc' in name: {len(cc_files)}")
    
    if es_files:
        print(f"\nES file examples:")
        for f in es_files[:3]:
            print(f"  {f.name}")
    
    if cc_files:
        print(f"\nCC file examples:")
        for f in cc_files[:3]:
            print(f"  {f.name}")
    
    # Load all metadata
    all_metadata = []
    for npz_file in npz_files:
        data = np.load(npz_file)
        all_metadata.append(data['metadata'])
    
    metadata = np.concatenate(all_metadata, axis=0)
    
    print(f"\nTotal clusters: {metadata.shape[0]}")
    
    # Metadata positions:
    # 0: event_id
    # 1: is_marley
    # 2: is_main_track
    # 3: is_es_interaction
    # 10: cluster_energy_mev
    
    # Analyze flags
    is_marley = metadata[:, 1] > 0.5
    is_main = metadata[:, 2] > 0.5
    is_es = metadata[:, 3] > 0.5
    
    print(f"\nCluster-level statistics:")
    print(f"  Marley clusters: {np.sum(is_marley)} ({100*np.mean(is_marley):.1f}%)")
    print(f"  Main track clusters: {np.sum(is_main)} ({100*np.mean(is_main):.1f}%)")
    print(f"  ES clusters: {np.sum(is_es)} ({100*np.mean(is_es):.1f}%)")
    
    # Combined filters
    marley_main = is_marley & is_main
    marley_main_es = is_marley & is_main & is_es
    marley_main_cc = is_marley & is_main & (~is_es)
    
    print(f"\nCombined filters:")
    print(f"  Marley + Main: {np.sum(marley_main)} clusters")
    print(f"  Marley + Main + ES: {np.sum(marley_main_es)} clusters")
    print(f"  Marley + Main + CC: {np.sum(marley_main_cc)} clusters")
    
    # Event-level statistics
    event_ids = np.unique(metadata[:, 0]).astype(int)
    print(f"\nTotal events: {len(event_ids)}")
    
    es_events = []
    cc_events = []
    main_events = []
    
    for event_id in event_ids:
        mask = (metadata[:, 0] == event_id)
        event_meta = metadata[mask]
        
        has_main = np.any(event_meta[:, 2] > 0.5)
        has_es = np.any(event_meta[:, 3] > 0.5)
        
        if has_main:
            main_events.append(event_id)
        
        if has_es:
            es_events.append(event_id)
        else:
            cc_events.append(event_id)
    
    print(f"\nEvent-level statistics:")
    print(f"  Events with main track: {len(main_events)}")
    print(f"  ES events: {len(es_events)}")
    print(f"  CC events: {len(cc_events)}")
    
    # Check energy distribution
    energies = metadata[:, 10]
    print(f"\nCluster energy statistics:")
    print(f"  Min: {np.min(energies):.2f} MeV")
    print(f"  Max: {np.max(energies):.2f} MeV")
    print(f"  Mean: {np.mean(energies):.2f} MeV")
    print(f"  Median: {np.median(energies):.2f} MeV")
    
    # ES vs CC energy
    if np.sum(is_es) > 0:
        print(f"\nES cluster energies:")
        es_energies = energies[is_es]
        print(f"  Mean: {np.mean(es_energies):.2f} MeV")
        print(f"  Median: {np.median(es_energies):.2f} MeV")
    
    if np.sum(~is_es) > 0:
        print(f"\nCC cluster energies:")
        cc_energies = energies[~is_es]
        print(f"  Mean: {np.mean(cc_energies):.2f} MeV")
        print(f"  Median: {np.median(cc_energies):.2f} MeV")
    
    print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description='Analyze ES/CC distribution')
    parser.add_argument('--cat', type=str, required=True, help='Category name')
    args = parser.parse_args()
    
    analyze_category(args.cat)


if __name__ == '__main__':
    main()
