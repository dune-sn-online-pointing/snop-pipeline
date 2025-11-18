#!/usr/bin/env python3
import sys
import numpy as np
sys.path.insert(0, '/afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline')

# Manually set args
class Args:
    cat_dir = '/eos/project-e/ep-nu/public/sn-pointing/cat000020'
    cat_name = 'cat000020'
    max_events = 1

args = Args()

# Load cluster images manually
from pathlib import Path

def load_cluster_images(cat_dir, cat_name, plane='X'):
    cluster_dir = Path(cat_dir) / f"{cat_name}_cluster_images_tick3_ch2_min2_tot3_e2p0" / plane
    
    if not cluster_dir.exists():
        return None, None, None
    
    all_images = []
    all_event_ids = []
    all_energies = []
    
    for npz_file in sorted(cluster_dir.glob('*.npz')):
        data = np.load(npz_file, allow_pickle=True)
        images = data['images']
        metadata = data['metadata']
        
        event_ids = metadata[:, 0].astype(int)
        energies = metadata[:, 4]
        
        all_images.append(images)
        all_event_ids.append(event_ids)
        all_energies.append(energies)
    
    if not all_images:
        return None, None, None
    
    return np.concatenate(all_images), np.concatenate(all_event_ids), np.concatenate(all_energies)

print("Loading cluster images...")
X_images, X_event_ids, X_energies = load_cluster_images(args.cat_dir, args.cat_name, 'X')
U_images, U_event_ids, U_energies = load_cluster_images(args.cat_dir, args.cat_name, 'U')
V_images, V_event_ids, V_energies = load_cluster_images(args.cat_dir, args.cat_name, 'V')

print(f"Loaded: X={len(X_images)}, U={len(U_images)}, V={len(V_images)}")

# Get unique events
unique_events = np.unique(X_event_ids)
if args.max_events:
    unique_events = unique_events[:args.max_events]

print(f"unique_events type: {type(unique_events)}")
print(f"unique_events length: {len(unique_events)}")
print(f"unique_events content: {unique_events}")

print("\nTrying to loop:")
for i, event_id in enumerate(unique_events):
    print(f"  Iteration {i}: event_id = {event_id}")
