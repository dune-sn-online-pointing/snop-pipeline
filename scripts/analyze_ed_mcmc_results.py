#!/usr/bin/env python3
"""
Analyze ED+MCMC results to understand performance variation.
Check correlation with neutrino direction and investigate poor performance.
"""

import numpy as np
from pathlib import Path
import uproot
import matplotlib.pyplot as plt


def load_neutrino_direction(cat_dir):
    """Load true neutrino direction for a category."""
    tps_dir = cat_dir / 'tps'
    es_files = sorted(tps_dir.glob('es_*_tps.root'))
    
    if len(es_files) == 0:
        return None
    
    all_neutrino_px = []
    all_neutrino_py = []
    all_neutrino_pz = []
    
    for es_file in es_files:
        try:
            with uproot.open(es_file) as f:
                tree = f['tps']
                nu_px = tree['neutrino_px'].array(library='np')
                nu_py = tree['neutrino_py'].array(library='np')
                nu_pz = tree['neutrino_pz'].array(library='np')
                
                all_neutrino_px.extend(nu_px)
                all_neutrino_py.extend(nu_py)
                all_neutrino_pz.extend(nu_pz)
        except:
            continue
    
    if len(all_neutrino_px) == 0:
        return None
    
    true_nu_px = np.mean(all_neutrino_px)
    true_nu_py = np.mean(all_neutrino_py)
    true_nu_pz = np.mean(all_neutrino_pz)
    
    nu_norm = np.sqrt(true_nu_px**2 + true_nu_py**2 + true_nu_pz**2)
    return np.array([true_nu_px, true_nu_py, true_nu_pz]) / nu_norm


def check_es_filtering(cat_dir):
    """Check if ES filtering is working correctly."""
    cluster_dir = cat_dir / f"{cat_dir.name}_cluster_images_tick3_ch2_min2_tot3_e2p0" / "X"
    
    # Count files
    es_files = sorted(cluster_dir.glob('es_*_matched_plane*.npz'))
    cc_files = sorted(cluster_dir.glob('cc_*_matched_plane*.npz'))
    
    if len(es_files) == 0:
        return None
    
    # Load ES files
    all_metadata = []
    for cf in es_files:
        data = np.load(cf)
        all_metadata.append(data['metadata'])
    
    metadata = np.vstack(all_metadata)
    
    # Check is_main_track filtering
    is_main_track = metadata[:, 2] == 1
    n_total = len(metadata)
    n_main = np.sum(is_main_track)
    
    return {
        'n_es_files': len(es_files),
        'n_cc_files': len(cc_files),
        'n_total_clusters': n_total,
        'n_main_track': n_main,
        'pct_main_track': 100 * n_main / n_total if n_total > 0 else 0
    }


def main():
    # Load results
    results_file = Path('results/ed_mcmc_100cats/ed_mcmc_98cats_results.npz')
    data = np.load(results_file)
    
    cos_angles = data['cos_angles']
    successful_cats = data['successful_cats']
    
    print("\n" + "="*70)
    print("ANALYZING ED+MCMC RESULTS")
    print("="*70)
    
    # Overall stats
    print(f"\nTotal events: {len(cos_angles)}")
    print(f"Forward (cos > 0): {np.sum(cos_angles > 0)} ({100*np.sum(cos_angles > 0)/len(cos_angles):.1f}%)")
    print(f"Backward (cos < 0): {np.sum(cos_angles < 0)} ({100*np.sum(cos_angles < 0)/len(cos_angles):.1f}%)")
    
    # Group by category
    base_path = Path('/eos/project-e/ep-nu/public/sn-pointing')
    
    print("\nLoading neutrino directions and checking ES filtering...")
    
    cat_results = []
    idx = 0
    
    for cat_name in successful_cats:
        cat_dir = base_path / cat_name
        
        # Get neutrino direction
        nu_dir = load_neutrino_direction(cat_dir)
        if nu_dir is None:
            continue
        
        # Get filtering info
        filter_info = check_es_filtering(cat_dir)
        if filter_info is None:
            continue
        
        # Get events for this category (40 events per cat)
        cat_cos = cos_angles[idx:idx+40]
        idx += 40
        
        # Calculate metrics
        cos_68 = np.percentile(cat_cos, 68)
        median_cos = np.median(cat_cos)
        forward_pct = 100 * np.sum(cat_cos > 0) / len(cat_cos)
        
        # Neutrino direction angles
        theta_nu = np.degrees(np.arccos(np.clip(nu_dir[2], -1, 1)))  # From Z-axis
        phi_nu = np.degrees(np.arctan2(nu_dir[1], nu_dir[0]))
        
        cat_results.append({
            'name': cat_name,
            'cos_68': cos_68,
            'median_cos': median_cos,
            'forward_pct': forward_pct,
            'nu_dir': nu_dir,
            'theta_nu': theta_nu,
            'phi_nu': phi_nu,
            'n_es_files': filter_info['n_es_files'],
            'n_cc_files': filter_info['n_cc_files'],
            'n_total_clusters': filter_info['n_total_clusters'],
            'n_main_track': filter_info['n_main_track'],
            'pct_main_track': filter_info['pct_main_track']
        })
    
    # Convert to arrays
    cos_68_array = np.array([r['cos_68'] for r in cat_results])
    median_cos_array = np.array([r['median_cos'] for r in cat_results])
    forward_pct_array = np.array([r['forward_pct'] for r in cat_results])
    theta_nu_array = np.array([r['theta_nu'] for r in cat_results])
    
    print(f"Analyzed {len(cat_results)} categories")
    
    # Check ES filtering
    print("\n" + "="*70)
    print("ES FILTERING CHECK")
    print("="*70)
    
    total_es_files = sum([r['n_es_files'] for r in cat_results])
    total_cc_files = sum([r['n_cc_files'] for r in cat_results])
    
    print(f"\nES files loaded: {total_es_files}")
    print(f"CC files found (not loaded): {total_cc_files}")
    print(f"ES files per category: {total_es_files/len(cat_results):.1f} avg")
    
    avg_pct_main = np.mean([r['pct_main_track'] for r in cat_results])
    print(f"Main track clusters: {avg_pct_main:.1f}% of ES clusters (avg)")
    
    # Performance vs neutrino direction
    print("\n" + "="*70)
    print("PERFORMANCE vs NEUTRINO DIRECTION")
    print("="*70)
    
    # Correlation
    corr_cos68_theta = np.corrcoef(cos_68_array, theta_nu_array)[0, 1]
    corr_forward_theta = np.corrcoef(forward_pct_array, theta_nu_array)[0, 1]
    
    print(f"\nCorrelation cos(θ) 68% vs θ_ν: {corr_cos68_theta:+.3f}")
    print(f"Correlation forward % vs θ_ν: {corr_forward_theta:+.3f}")
    
    # Best/worst categories
    best_idx = np.argmax(cos_68_array)
    worst_idx = np.argmin(cos_68_array)
    
    print(f"\nBest category: {cat_results[best_idx]['name']}")
    print(f"  cos(θ) 68%: {cat_results[best_idx]['cos_68']:.4f}")
    print(f"  θ_ν from Z: {cat_results[best_idx]['theta_nu']:.1f}°")
    print(f"  Forward: {cat_results[best_idx]['forward_pct']:.1f}%")
    
    print(f"\nWorst category: {cat_results[worst_idx]['name']}")
    print(f"  cos(θ) 68%: {cat_results[worst_idx]['cos_68']:.4f}")
    print(f"  θ_ν from Z: {cat_results[worst_idx]['theta_nu']:.1f}°")
    print(f"  Forward: {cat_results[worst_idx]['forward_pct']:.1f}%")
    
    # Binned by neutrino angle
    print("\n" + "="*70)
    print("BINNED BY NEUTRINO DIRECTION")
    print("="*70)
    
    bins = [(0, 30), (30, 60), (60, 90), (90, 120), (120, 150), (150, 180)]
    
    for bin_min, bin_max in bins:
        mask = (theta_nu_array >= bin_min) & (theta_nu_array < bin_max)
        if np.sum(mask) == 0:
            continue
        
        n_cats = np.sum(mask)
        avg_cos68 = np.mean(cos_68_array[mask])
        avg_forward = np.mean(forward_pct_array[mask])
        
        print(f"\nθ_ν = {bin_min:3d}-{bin_max:3d}° ({n_cats:2d} cats):")
        print(f"  cos(θ) 68%: {avg_cos68:.4f}")
        print(f"  Forward %:  {avg_forward:.1f}%")
    
    # Create plots
    output_dir = Path('results/ed_mcmc_100cats')
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    
    # cos(θ) 68% vs neutrino direction
    ax = axes[0, 0]
    scatter = ax.scatter(theta_nu_array, cos_68_array, c=forward_pct_array, 
                        cmap='RdYlGn', s=100, alpha=0.7, edgecolors='black')
    ax.set_xlabel('Neutrino θ from Z-axis (degrees)', fontsize=12, fontweight='bold')
    ax.set_ylabel('cos(θ) 68th percentile', fontsize=12, fontweight='bold')
    ax.set_title(f'Performance vs Neutrino Direction\n(correlation: {corr_cos68_theta:+.3f})',
                fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.axhline(0.9680, color='blue', linestyle='--', linewidth=2, alpha=0.7,
              label='Single cat (cat000035)')
    ax.axhline(0.9980, color='red', linestyle='--', linewidth=2, alpha=0.7,
              label='Best possible (true dirs)')
    ax.legend()
    
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label('Forward %', fontsize=11, fontweight='bold')
    
    # Forward % vs neutrino direction
    ax = axes[0, 1]
    ax.scatter(theta_nu_array, forward_pct_array, s=100, alpha=0.7, 
              edgecolors='black', c='steelblue')
    ax.set_xlabel('Neutrino θ from Z-axis (degrees)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Forward pointing %', fontsize=12, fontweight='bold')
    ax.set_title(f'Forward % vs Neutrino Direction\n(correlation: {corr_forward_theta:+.3f})',
                fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.axhline(100, color='red', linestyle='--', linewidth=2, alpha=0.7)
    
    # cos(θ) 68% distribution
    ax = axes[1, 0]
    ax.hist(cos_68_array, bins=30, alpha=0.7, edgecolor='black', color='coral')
    ax.axvline(np.median(cos_68_array), color='red', linestyle='--', linewidth=2,
              label=f'Median = {np.median(cos_68_array):.4f}')
    ax.axvline(0.9680, color='blue', linestyle='--', linewidth=2,
              label='Single cat = 0.9680')
    ax.set_xlabel('cos(θ) 68th percentile', fontsize=12, fontweight='bold')
    ax.set_ylabel('Number of categories', fontsize=12, fontweight='bold')
    ax.set_title('Distribution of cos(θ) 68% across categories', fontsize=13, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Neutrino direction distribution
    ax = axes[1, 1]
    ax.hist(theta_nu_array, bins=30, alpha=0.7, edgecolor='black', color='lightgreen')
    ax.axvline(np.median(theta_nu_array), color='red', linestyle='--', linewidth=2,
              label=f'Median = {np.median(theta_nu_array):.1f}°')
    ax.set_xlabel('Neutrino θ from Z-axis (degrees)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Number of categories', fontsize=12, fontweight='bold')
    ax.set_title('Distribution of neutrino directions', fontsize=13, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    output_file = output_dir / 'ed_mcmc_analysis.png'
    plt.savefig(output_file, dpi=200, bbox_inches='tight')
    print(f"\nSaved analysis plot: {output_file}")
    plt.close()
    
    # Save detailed results
    np.savez(output_dir / 'ed_mcmc_per_category.npz',
             cat_names=[r['name'] for r in cat_results],
             cos_68=cos_68_array,
             median_cos=median_cos_array,
             forward_pct=forward_pct_array,
             theta_nu=theta_nu_array,
             phi_nu=np.array([r['phi_nu'] for r in cat_results]))
    
    print("\n" + "="*70 + "\n")


if __name__ == '__main__':
    main()
