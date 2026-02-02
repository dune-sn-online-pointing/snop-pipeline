#!/usr/bin/env python3
"""
Compare results between original MCMC and emcee ensemble sampler.
"""

import numpy as np
from pathlib import Path
import sys

def compare_cat_results(cat_name, base_path='/eos/project-e/ep-nu/evilla/sn-pointing'):
    """Compare original vs emcee results for a cat."""
    cat_dir = Path(base_path) / cat_name / 'pipeline'
    
    # Load original results
    orig_file = cat_dir / f'{cat_name}_scenario_perfect_ct.npz'
    emcee_file = cat_dir / f'{cat_name}_scenario_perfect_ct_emcee.npz'
    
    if not orig_file.exists():
        print(f"  ✗ Original file not found: {orig_file}")
        return None
    
    if not emcee_file.exists():
        print(f"  ✗ Emcee file not found: {emcee_file}")
        return None
    
    orig = np.load(orig_file, allow_pickle=True)
    emcee = np.load(emcee_file, allow_pickle=True)
    
    # Extract metrics
    orig_error = float(orig['perfect_ct_angular_error_deg'])
    orig_cos = float(orig['perfect_ct_cos_theta'])
    orig_n_clusters = int(orig['perfect_ct_n_clusters_used'])
    
    emcee_error = float(emcee['perfect_ct_emcee_angular_error_deg'])
    emcee_cos = float(emcee['perfect_ct_emcee_cos_theta'])
    emcee_n_clusters = int(emcee['perfect_ct_emcee_n_clusters_used'])
    emcee_theta_std = float(emcee['perfect_ct_emcee_theta_std'])
    emcee_phi_std = float(emcee['perfect_ct_emcee_phi_std'])
    emcee_omega_68 = float(emcee['perfect_ct_emcee_omega_68'])
    emcee_acceptance = float(emcee['perfect_ct_emcee_acceptance_fraction'])
    
    print(f"\n{cat_name}:")
    print(f"  N clusters: {orig_n_clusters}")
    print(f"  Original method:")
    print(f"    Angular error: {orig_error:.2f}°")
    print(f"    cos(θ): {orig_cos:.4f}")
    print(f"  Emcee method:")
    print(f"    Angular error: {emcee_error:.2f}°")
    print(f"    cos(θ): {emcee_cos:.4f}")
    print(f"    Uncertainties: Δθ={np.degrees(emcee_theta_std):.2f}°, Δφ={np.degrees(emcee_phi_std):.2f}°")
    print(f"    68% credible: {np.degrees(emcee_omega_68):.2f}°")
    print(f"    Acceptance: {100*emcee_acceptance:.1f}%")
    
    diff = emcee_error - orig_error
    if diff < 0:
        print(f"  ✅ Emcee BETTER by {abs(diff):.2f}°")
    elif diff > 0:
        print(f"  ❌ Emcee WORSE by {diff:.2f}°")
    else:
        print(f"  ⚖️  Same performance")
    
    return {
        'cat_name': cat_name,
        'n_clusters': orig_n_clusters,
        'orig_error': orig_error,
        'emcee_error': emcee_error,
        'diff': diff,
        'emcee_theta_std': emcee_theta_std,
        'emcee_phi_std': emcee_phi_std,
        'emcee_omega_68': emcee_omega_68,
        'emcee_acceptance': emcee_acceptance
    }


def main():
    cats = ['cat000001', 'cat000002', 'cat000003', 'cat000013', 'cat000062']
    
    print("="*70)
    print("EMCEE vs ORIGINAL MCMC COMPARISON")
    print("="*70)
    
    results = []
    for cat in cats:
        result = compare_cat_results(cat)
        if result:
            results.append(result)
    
    if not results:
        print("\n✗ No results to compare")
        return
    
    # Summary statistics
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    diffs = np.array([r['diff'] for r in results])
    orig_errors = np.array([r['orig_error'] for r in results])
    emcee_errors = np.array([r['emcee_error'] for r in results])
    acceptances = np.array([r['emcee_acceptance'] for r in results])
    
    print(f"\nNumber of cats: {len(results)}")
    print(f"\nOriginal method:")
    print(f"  Mean error: {orig_errors.mean():.2f}° ± {orig_errors.std():.2f}°")
    print(f"  Median: {np.median(orig_errors):.2f}°")
    print(f"  Range: [{orig_errors.min():.2f}°, {orig_errors.max():.2f}°]")
    
    print(f"\nEmcee method:")
    print(f"  Mean error: {emcee_errors.mean():.2f}° ± {emcee_errors.std():.2f}°")
    print(f"  Median: {np.median(emcee_errors):.2f}°")
    print(f"  Range: [{emcee_errors.min():.2f}°, {emcee_errors.max():.2f}°]")
    print(f"  Mean acceptance: {100*acceptances.mean():.1f}% ± {100*acceptances.std():.1f}%")
    
    print(f"\nDifference (emcee - original):")
    print(f"  Mean: {diffs.mean():.2f}° ± {diffs.std():.2f}°")
    print(f"  Median: {np.median(diffs):.2f}°")
    
    n_better = np.sum(diffs < 0)
    n_worse = np.sum(diffs > 0)
    n_same = np.sum(diffs == 0)
    
    print(f"\nPerformance:")
    print(f"  Emcee better: {n_better}/{len(results)} ({100*n_better/len(results):.1f}%)")
    print(f"  Emcee worse:  {n_worse}/{len(results)} ({100*n_worse/len(results):.1f}%)")
    print(f"  Same:         {n_same}/{len(results)}")
    
    if diffs.mean() < 0:
        print(f"\n✅ Overall: Emcee performs BETTER by {abs(diffs.mean()):.2f}° on average")
    elif diffs.mean() > 0:
        print(f"\n❌ Overall: Emcee performs WORSE by {diffs.mean():.2f}° on average")
    else:
        print(f"\n⚖️  Overall: Same performance on average")
    
    print("\n" + "="*70)


if __name__ == '__main__':
    main()
