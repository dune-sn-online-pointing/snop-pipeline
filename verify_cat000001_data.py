#!/usr/bin/env python3
"""
Verify cat000001 cluster data includes neutrino momentum metadata.
"""
import numpy as np
from pathlib import Path
import glob

print("=" * 70)
print("Verifying cat000001 Cluster Data with Neutrino Momentum")
print("=" * 70)

# Data folder
data_folder = "/eos/project-e/ep-nu/evilla/sn-pointing/cat000001/cat000001_cluster_images_tick3_ch2_min2_tot3_e2p0"

# Check each plane
for plane in ['U', 'V', 'X']:
    plane_dir = Path(data_folder) / plane
    if not plane_dir.exists():
        print(f"\n❌ Plane {plane} directory not found: {plane_dir}")
        continue
    
    # Find all npz files
    npz_files = list(plane_dir.glob(f"*_plane{plane}.npz"))
    if not npz_files:
        print(f"\n⚠  No NPZ files found in {plane_dir}")
        continue
    
    print(f"\n{'='*70}")
    print(f"Plane {plane}: Found {len(npz_files)} NPZ files")
    print(f"{'='*70}")
    
    # Load first file as sample
    sample_file = npz_files[0]
    print(f"\nSample file: {sample_file.name}")
    
    data = np.load(sample_file, allow_pickle=True)
    
    images = data['images']
    metadata = data['metadata']
    
    print(f"\n📊 Data shapes:")
    print(f"   Images: {images.shape}")
    print(f"   Metadata: {metadata.shape}")
    
    # Check metadata size
    n_clusters = metadata.shape[0]
    metadata_cols = metadata.shape[1]
    
    print(f"\n✓ Metadata has {metadata_cols} columns (expected 18)")
    
    if metadata_cols < 18:
        print(f"   ❌ ERROR: Metadata should have 18 columns!")
        continue
    
    # Check neutrino momentum fields (indices 15-17)
    nu_mom_x = metadata[:, 15]
    nu_mom_y = metadata[:, 16]
    nu_mom_z = metadata[:, 17]
    
    print(f"\n🔍 Neutrino Momentum Statistics:")
    print(f"   X-component: min={nu_mom_x.min():.3f}, max={nu_mom_x.max():.3f}, mean={nu_mom_x.mean():.3f}")
    print(f"   Y-component: min={nu_mom_y.min():.3f}, max={nu_mom_y.max():.3f}, mean={nu_mom_y.mean():.3f}")
    print(f"   Z-component: min={nu_mom_z.min():.3f}, max={nu_mom_z.max():.3f}, mean={nu_mom_z.mean():.3f}")
    
    # Calculate magnitudes
    nu_mom_mag = np.sqrt(nu_mom_x**2 + nu_mom_y**2 + nu_mom_z**2)
    non_zero = nu_mom_mag > 0
    
    print(f"\n   Magnitude: min={nu_mom_mag.min():.3f}, max={nu_mom_mag.max():.3f}, mean={nu_mom_mag.mean():.3f}")
    print(f"   Non-zero entries: {non_zero.sum()} / {n_clusters} ({100*non_zero.sum()/n_clusters:.1f}%)")
    
    # Show a few sample clusters
    print(f"\n📋 Sample clusters (first 5):")
    print(f"   {'Event':<8} {'Is_MT':<6} {'Is_ES':<6} {'E_nu(MeV)':<12} {'|p_nu|(MeV/c)':<15}")
    print(f"   {'-'*60}")
    
    for i in range(min(5, n_clusters)):
        event = int(metadata[i, 0])
        is_mt = int(metadata[i, 2])
        is_es = int(metadata[i, 3])
        e_nu = metadata[i, 14]
        p_nu = np.sqrt(metadata[i, 15]**2 + metadata[i, 16]**2 + metadata[i, 17]**2)
        print(f"   {event:<8} {is_mt:<6} {is_es:<6} {e_nu:<12.2f} {p_nu:<15.2f}")
    
    # Count main tracks
    is_main_track = metadata[:, 2]
    n_main_tracks = int(is_main_track.sum())
    
    print(f"\n✓ Main tracks: {n_main_tracks} / {n_clusters} ({100*n_main_tracks/n_clusters:.1f}%)")

# Check volume images if they exist
volume_folder = "/eos/project-e/ep-nu/evilla/sn-pointing/cat000001/cat000001_volume_images_tick3_ch2_min2_tot3_e2p0"
if Path(volume_folder).exists():
    print(f"\n{'='*70}")
    print(f"Volume Images")
    print(f"{'='*70}")
    
    for plane in ['U', 'V', 'X']:
        plane_dir = Path(volume_folder) / plane
        if not plane_dir.exists():
            continue
        
        npz_files = list(plane_dir.glob(f"*_plane{plane}.npz"))
        if not npz_files:
            continue
        
        print(f"\nPlane {plane}: Found {len(npz_files)} volume files")
        
        # Load first file
        sample_file = npz_files[0]
        data = np.load(sample_file, allow_pickle=True)
        
        volume_images = data['volume_images']
        volume_metadata = data['volume_metadata']
        
        print(f"   Sample file: {sample_file.name}")
        print(f"   Volume images shape: {volume_images.shape}")
        print(f"   Volume metadata entries: {len(volume_metadata)}")
        
        # Check if neutrino momentum is in metadata
        if len(volume_metadata) > 0:
            sample_meta = volume_metadata[0]
            has_nu_mom = 'main_track_neutrino_momentum_x' in sample_meta
            print(f"   Has neutrino momentum fields: {has_nu_mom}")
            
            if has_nu_mom:
                nu_mom_x = sample_meta['main_track_neutrino_momentum_x']
                nu_mom_y = sample_meta['main_track_neutrino_momentum_y']
                nu_mom_z = sample_meta['main_track_neutrino_momentum_z']
                nu_mom = sample_meta['main_track_neutrino_momentum']
                print(f"   Sample neutrino momentum: ({nu_mom_x:.2f}, {nu_mom_y:.2f}, {nu_mom_z:.2f}) |p|={nu_mom:.2f} MeV/c")

print(f"\n{'='*70}")
print("✅ Verification complete!")
print(f"{'='*70}")
