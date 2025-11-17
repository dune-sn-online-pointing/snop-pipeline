#!/usr/bin/env python3
"""
Find categories with neutrino directions close to (0,0,1).
"""

import uproot
import numpy as np
from pathlib import Path
import argparse


def check_category_direction(cat_name, cat_dir):
    """Check neutrino direction for a category."""
    
    tps_dir = cat_dir / 'tps'
    
    if not tps_dir.exists():
        return None
    
    # Get one ES file to check direction
    es_files = sorted(tps_dir.glob('es_*_tps.root'))
    
    if len(es_files) == 0:
        return None
    
    try:
        # Read first ES file
        with uproot.open(es_files[0]) as f:
            tree = f['tps']
            nu_px = tree['neutrino_px'].array(library='np')
            nu_py = tree['neutrino_py'].array(library='np')
            nu_pz = tree['neutrino_pz'].array(library='np')
        
        # Average (should be constant)
        true_px = np.mean(nu_px)
        true_py = np.mean(nu_py)
        true_pz = np.mean(nu_pz)
        
        # Normalize
        true_norm = np.sqrt(true_px**2 + true_py**2 + true_pz**2)
        direction = np.array([true_px, true_py, true_pz]) / true_norm
        
        # Angle to (0, 0, 1)
        target = np.array([0, 0, 1])
        cos_angle = np.dot(direction, target)
        angle_deg = np.degrees(np.arccos(np.clip(cos_angle, -1, 1)))
        
        return {
            'cat_name': cat_name,
            'direction': direction,
            'angle_to_z': angle_deg,
            'cos_to_z': cos_angle,
            'n_es_files': len(es_files)
        }
    except Exception as e:
        print(f"Error reading {cat_name}: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description='Find categories close to (0,0,1)')
    parser.add_argument('--tps-dir', default='/eos/project-e/ep-nu/public/sn-pointing', 
                       help='Base directory for categories')
    parser.add_argument('--max-cats', type=int, default=100, help='Number of categories to check')
    args = parser.parse_args()
    
    tps_base = Path(args.tps_dir)
    
    # Find all category directories
    cat_dirs = sorted([d for d in tps_base.glob('cat*') if d.is_dir()])
    
    print(f"\nSearching {len(cat_dirs[:args.max_cats])} categories for neutrino directions close to (0,0,1)...\n")
    
    results = []
    
    for cat_dir in cat_dirs[:args.max_cats]:
        cat_name = cat_dir.name
        
        result = check_category_direction(cat_name, cat_dir)
        
        if result:
            results.append(result)
    
    # Sort by angle to z-axis
    results.sort(key=lambda x: x['angle_to_z'])
    
    print(f"{'Category':<15} {'Direction (x, y, z)':<35} {'Angle to +z':<15} {'cos(θ)':<10} {'ES files'}")
    print("="*100)
    
    for r in results[:20]:
        dir_str = f"({r['direction'][0]:7.4f}, {r['direction'][1]:7.4f}, {r['direction'][2]:7.4f})"
        print(f"{r['cat_name']:<15} {dir_str:<35} {r['angle_to_z']:6.2f}°        {r['cos_to_z']:7.4f}    {r['n_es_files']}")
    
    print("\n" + "="*100)
    print(f"\nBest category: {results[0]['cat_name']} with angle = {results[0]['angle_to_z']:.2f}° to +z axis")
    print(f"Direction: {results[0]['direction']}")
    print("\n")


if __name__ == '__main__':
    main()
