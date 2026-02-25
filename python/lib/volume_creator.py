#!/usr/bin/env python3
"""
Volume Creator Module

Creates 3D volumes around selected clusters using the online-pointing-utils
submodule scripts.
"""

import numpy as np
from pathlib import Path
import subprocess
import tempfile
import shutil


def create_volumes(images, metadata, pointing_utils_dir, output_dir,
                  temp_dir=None, verbose=False):
    """
    Create 3D volumes for selected clusters.
    
    This function interfaces with the online-pointing-utils submodule to create
    volumes around the selected clusters. It:
    1. Saves selected clusters to temporary NPZ file
    2. Calls create_volumes.py script from online-pointing-utils
    3. Loads the created volume images
    
    Args:
        images: Selected cluster images (N, H, W, C)
        metadata: Main track cluster metadata (N, 13)
        pointing_utils_dir: Path to online-pointing-utils directory
        output_dir: Directory to save volume data
        temp_dir: Optional temporary directory for intermediate files
        verbose: Print detailed progress
        
    Returns:
        dict with volume images, metadata, and statistics
    """
    
    if verbose:
        print(f"\nVolume Creation:")
        print(f"  Input clusters: {len(images)}")
        print(f"  Pointing utils: {pointing_utils_dir}")
    
    # Verify paths
    pointing_utils_path = Path(pointing_utils_dir)
    if not pointing_utils_path.exists():
        raise ValueError(f"online-pointing-utils directory not found: {pointing_utils_dir}")
    
    create_volumes_script = pointing_utils_path / "python" / "create_volumes.py"
    if not create_volumes_script.exists():
        raise ValueError(f"create_volumes.py script not found: {create_volumes_script}")
    
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Use temporary directory for intermediate files
    if temp_dir:
        temp_path = Path(temp_dir)
        temp_path.mkdir(parents=True, exist_ok=True)
        cleanup_temp = False
    else:
        temp_path = Path(tempfile.mkdtemp(prefix='volumes_'))
        cleanup_temp = True
    
    try:
        # Save clusters to temporary file
        clusters_file = temp_path / "clusters_for_volumes.npz"
        np.savez(clusters_file, images=images, metadata=metadata)
        
        if verbose:
            print(f"  ✓ Saved clusters to temporary file")
        
        # Prepare output directory for volumes
        volumes_dir = temp_path / "volumes"
        volumes_dir.mkdir(exist_ok=True)
        
        # Call create_volumes.py script
        if verbose:
            print(f"  Running volume creation script...")
        
        cmd = [
            "python3",
            str(create_volumes_script),
            "--input", str(clusters_file),
            "--output", str(volumes_dir),
            "--plane", "X"  # Only X-plane as specified
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=300  # 5 minute timeout
            )
            
            if verbose:
                print(f"  ✓ Volume creation completed")
                if result.stdout:
                    print(f"    Output: {result.stdout[:200]}")
                    
        except subprocess.TimeoutExpired:
            raise RuntimeError("Volume creation timed out after 5 minutes")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Volume creation failed: {e.stderr}")
        
        # Load created volumes
        volume_files = list(volumes_dir.glob("volume_*.npz"))
        
        if not volume_files:
            raise RuntimeError(f"No volume files created in {volumes_dir}")
        
        if verbose:
            print(f"  Found {len(volume_files)} volume files")
        
        # Load all volumes
        volume_images = []
        volume_metadata = []
        
        for vol_file in sorted(volume_files):
            try:
                data = np.load(vol_file)
                volume_images.append(data['image'])
                volume_metadata.append(data['metadata'])
            except Exception as e:
                print(f"  Warning: Failed to load {vol_file.name}: {e}")
                continue
        
        if not volume_images:
            raise RuntimeError("No volumes could be loaded")
        
        volumes = np.array(volume_images, dtype=np.float32)
        vol_metadata = np.array(volume_metadata, dtype=np.float32)
        
        if verbose:
            print(f"  ✓ Loaded {len(volumes)} volumes")
            print(f"    Volume shape: {volumes[0].shape}")
        
        # Save to output directory
        output_file = output_path / "volumes.npz"
        np.savez(output_file, images=volumes, metadata=vol_metadata)
        
        if verbose:
            print(f"  ✓ Saved volumes to {output_file}")
        
        # Save summary
        summary_file = output_path / "volume_summary.txt"
        with open(summary_file, 'w') as f:
            f.write("Volume Creation Summary\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Input clusters: {len(images)}\n")
            f.write(f"Volumes created: {len(volumes)}\n")
            f.write(f"Volume shape: {volumes[0].shape}\n")
            f.write(f"Success rate: {len(volumes)/len(images)*100:.1f}%\n")
        
        result_dict = {
            'images': volumes,
            'metadata': vol_metadata,
            'n_volumes': len(volumes),
            'n_input_clusters': len(images),
            'volume_shape': volumes[0].shape,
            'success_rate': len(volumes) / len(images)
        }
        
    finally:
        # Clean up temporary directory if we created it
        if cleanup_temp and temp_path.exists():
            shutil.rmtree(temp_path)
            if verbose:
                print(f"  ✓ Cleaned up temporary directory")
    
    return result_dict


def create_volumes_simple(images, metadata, output_dir, verbose=False):
    """
    Simple volume creation without external scripts (placeholder).
    
    This is a simplified version that just repackages the 2D images as "volumes"
    for testing purposes. In production, use create_volumes() which calls the
    proper online-pointing-utils scripts.
    
    Args:
        images: Cluster images (N, H, W, C)
        metadata: Cluster metadata (N, 13)
        output_dir: Directory to save volume data
        verbose: Print progress
        
    Returns:
        dict with volume data (same as input for now)
    """
    
    if verbose:
        print(f"\nVolume Creation (Simple Mode):")
        print(f"  Input clusters: {len(images)}")
        print(f"  WARNING: Using simplified volume creation for testing")
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # In simple mode, just save the 2D images as "volumes"
    # In production, these would be actual 3D volumes
    output_file = output_path / "volumes.npz"
    np.savez(output_file, images=images, metadata=metadata)
    
    if verbose:
        print(f"  ✓ Saved {len(images)} 'volumes' to {output_file}")
        print(f"    (Note: These are still 2D images, not true 3D volumes)")
    
    return {
        'images': images,
        'metadata': metadata,
        'n_volumes': len(images),
        'n_input_clusters': len(images),
        'volume_shape': images[0].shape,
        'success_rate': 1.0
    }
