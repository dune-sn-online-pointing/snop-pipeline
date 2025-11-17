#!/usr/bin/env python3
"""
Compare true particle energy (electrons) with true neutrino energy.
This validates that the ES sample is correctly identified.
"""

import uproot
import numpy as np
from pathlib import Path
import argparse
import matplotlib.pyplot as plt


def load_es_data(cat_dir):
    """Load all ES event data from ROOT files."""
    
    tps_dir = cat_dir / 'tps'
    es_files = sorted(tps_dir.glob('es_*_tps.root'))
    
    if len(es_files) == 0:
        print(f"No ES files found in {tps_dir}")
        return None
    
    print(f"Found {len(es_files)} ES files")
    
    all_neutrino_energy = []
    all_particle_energy = []
    all_neutrino_px = []
    all_neutrino_py = []
    all_neutrino_pz = []
    all_particle_px = []
    all_particle_py = []
    all_particle_pz = []
    
    for es_file in es_files:
        try:
            with uproot.open(es_file) as f:
                tree = f['tps']
                
                # Neutrino properties
                nu_energy = tree['neutrino_energy'].array(library='np')
                nu_px = tree['neutrino_px'].array(library='np')
                nu_py = tree['neutrino_py'].array(library='np')
                nu_pz = tree['neutrino_pz'].array(library='np')
                
                # Particle properties (electron)
                part_energy = tree['particle_energy'].array(library='np')
                part_px = tree['particle_px'].array(library='np')
                part_py = tree['particle_py'].array(library='np')
                part_pz = tree['particle_pz'].array(library='np')
                
                all_neutrino_energy.extend(nu_energy)
                all_particle_energy.extend(part_energy)
                all_neutrino_px.extend(nu_px)
                all_neutrino_py.extend(nu_py)
                all_neutrino_pz.extend(nu_pz)
                all_particle_px.extend(part_px)
                all_particle_py.extend(part_py)
                all_particle_pz.extend(part_pz)
                
        except Exception as e:
            print(f"Error reading {es_file}: {e}")
            continue
    
    return {
        'neutrino_energy': np.array(all_neutrino_energy),
        'particle_energy': np.array(all_particle_energy),
        'neutrino_px': np.array(all_neutrino_px),
        'neutrino_py': np.array(all_neutrino_py),
        'neutrino_pz': np.array(all_neutrino_pz),
        'particle_px': np.array(all_particle_px),
        'particle_py': np.array(all_particle_py),
        'particle_pz': np.array(all_particle_pz),
    }


def analyze_energies(data):
    """Analyze energy correlation between neutrino and electron."""
    
    nu_e = data['neutrino_energy']
    part_e = data['particle_energy']
    
    # Filter for non-zero energies
    valid_mask = (nu_e > 0) & (part_e > 0)
    nu_e_valid = nu_e[valid_mask]
    part_e_valid = part_e[valid_mask]
    
    print("\n" + "="*70)
    print("ENERGY COMPARISON")
    print("="*70)
    print(f"\nTotal events: {len(nu_e)}")
    print(f"Valid events (E > 0): {len(nu_e_valid)}")
    
    print(f"\nNeutrino Energy (valid events):")
    print(f"  Mean:   {np.mean(nu_e_valid):7.3f} MeV")
    print(f"  Median: {np.median(nu_e_valid):7.3f} MeV")
    print(f"  Std:    {np.std(nu_e_valid):7.3f} MeV")
    print(f"  Min:    {np.min(nu_e_valid):7.3f} MeV")
    print(f"  Max:    {np.max(nu_e_valid):7.3f} MeV")
    
    print(f"\nElectron Energy (valid events):")
    print(f"  Mean:   {np.mean(part_e_valid):7.3f} MeV")
    print(f"  Median: {np.median(part_e_valid):7.3f} MeV")
    print(f"  Std:    {np.std(part_e_valid):7.3f} MeV")
    print(f"  Min:    {np.min(part_e_valid):7.3f} MeV")
    print(f"  Max:    {np.max(part_e_valid):7.3f} MeV")
    
    # Energy difference
    energy_diff = nu_e_valid - part_e_valid
    energy_ratio = part_e_valid / nu_e_valid
    
    print(f"\nEnergy Difference (ν - e):")
    print(f"  Mean:   {np.mean(energy_diff):7.3f} MeV")
    print(f"  Median: {np.median(energy_diff):7.3f} MeV")
    print(f"  Std:    {np.std(energy_diff):7.3f} MeV")
    
    print(f"\nEnergy Ratio (e / ν):")
    print(f"  Mean:   {np.mean(energy_ratio):7.3f}")
    print(f"  Median: {np.median(energy_ratio):7.3f}")
    print(f"  Std:    {np.std(energy_ratio):7.3f}")
    
    # Correlation
    corr = np.corrcoef(nu_e_valid, part_e_valid)[0, 1]
    print(f"\nCorrelation coefficient: {corr:.4f}")
    
    # Check if energies are similar (ES scattering expectation)
    close_energy = np.abs(energy_ratio - 1.0) < 0.1  # within 10%
    print(f"\nEvents with E_e/E_ν within 10% of 1.0: {np.sum(close_energy)}/{len(nu_e_valid)} ({100*np.mean(close_energy):.1f}%)")
    
    return energy_ratio, energy_diff, valid_mask


def analyze_directions(data, valid_mask):
    """Analyze direction correlation between neutrino and electron."""
    
    # Compute directions
    nu_px = data['neutrino_px'][valid_mask]
    nu_py = data['neutrino_py'][valid_mask]
    nu_pz = data['neutrino_pz'][valid_mask]
    
    part_px = data['particle_px'][valid_mask]
    part_py = data['particle_py'][valid_mask]
    part_pz = data['particle_pz'][valid_mask]
    
    # Normalize
    nu_norm = np.sqrt(nu_px**2 + nu_py**2 + nu_pz**2)
    part_norm = np.sqrt(part_px**2 + part_py**2 + part_pz**2)
    
    nu_dir = np.column_stack([nu_px / nu_norm, nu_py / nu_norm, nu_pz / nu_norm])
    part_dir = np.column_stack([part_px / part_norm, part_py / part_norm, part_pz / part_norm])
    
    # Compute angle between neutrino and electron
    cos_angle = np.sum(nu_dir * part_dir, axis=1)
    angle_deg = np.degrees(np.arccos(np.clip(cos_angle, -1, 1)))
    
    print("\n" + "="*70)
    print("DIRECTION COMPARISON")
    print("="*70)
    print(f"\nAngle between neutrino and electron direction:")
    print(f"  Mean:   {np.mean(angle_deg):7.2f}°")
    print(f"  Median: {np.median(angle_deg):7.2f}°")
    print(f"  Std:    {np.std(angle_deg):7.2f}°")
    print(f"  Min:    {np.min(angle_deg):7.2f}°")
    print(f"  Max:    {np.max(angle_deg):7.2f}°")
    
    # Check consistency with neutrino direction
    avg_nu_dir = np.mean(nu_dir, axis=0)
    avg_nu_dir /= np.linalg.norm(avg_nu_dir)
    
    print(f"\nAverage neutrino direction: ({avg_nu_dir[0]:7.4f}, {avg_nu_dir[1]:7.4f}, {avg_nu_dir[2]:7.4f})")
    
    # Angle of each electron to average neutrino direction
    cos_to_avg_nu = np.dot(part_dir, avg_nu_dir)
    angle_to_avg_nu = np.degrees(np.arccos(np.clip(cos_to_avg_nu, -1, 1)))
    
    print(f"\nElectron angle to average neutrino direction:")
    print(f"  Mean:   {np.mean(angle_to_avg_nu):7.2f}°")
    print(f"  Median: {np.median(angle_to_avg_nu):7.2f}°")
    print(f"  Std:    {np.std(angle_to_avg_nu):7.2f}°")
    
    return angle_deg, angle_to_avg_nu


def make_plots(data, energy_ratio, energy_diff, angle_deg, angle_to_avg_nu, valid_mask, output_dir):
    """Create diagnostic plots."""
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    nu_e = data['neutrino_energy'][valid_mask]
    part_e = data['particle_energy'][valid_mask]
    
    # Figure 1: Energy correlation
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    
    # Scatter plot
    ax = axes[0, 0]
    ax.scatter(nu_e, part_e, alpha=0.5, s=20)
    ax.plot([0, max(nu_e)], [0, max(nu_e)], 'r--', label='E_e = E_ν')
    ax.set_xlabel('Neutrino Energy (MeV)')
    ax.set_ylabel('Electron Energy (MeV)')
    ax.set_title('Energy Correlation')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Energy ratio histogram
    ax = axes[0, 1]
    ax.hist(energy_ratio, bins=50, alpha=0.7, edgecolor='black')
    ax.axvline(1.0, color='r', linestyle='--', label='Perfect match')
    ax.axvline(np.median(energy_ratio), color='g', linestyle='--', label=f'Median = {np.median(energy_ratio):.3f}')
    ax.set_xlabel('Energy Ratio (E_e / E_ν)')
    ax.set_ylabel('Count')
    ax.set_title('Energy Ratio Distribution')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Energy difference histogram
    ax = axes[1, 0]
    ax.hist(energy_diff, bins=50, alpha=0.7, edgecolor='black')
    ax.axvline(0.0, color='r', linestyle='--', label='Perfect match')
    ax.axvline(np.median(energy_diff), color='g', linestyle='--', label=f'Median = {np.median(energy_diff):.2f} MeV')
    ax.set_xlabel('Energy Difference (E_ν - E_e) [MeV]')
    ax.set_ylabel('Count')
    ax.set_title('Energy Difference Distribution')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Energy vs ratio
    ax = axes[1, 1]
    ax.scatter(nu_e, energy_ratio, alpha=0.5, s=20)
    ax.axhline(1.0, color='r', linestyle='--', label='Perfect match')
    ax.set_xlabel('Neutrino Energy (MeV)')
    ax.set_ylabel('Energy Ratio (E_e / E_ν)')
    ax.set_title('Energy Ratio vs Neutrino Energy')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'energy_comparison.png', dpi=150)
    print(f"\nSaved: {output_dir / 'energy_comparison.png'}")
    plt.close()
    
    # Figure 2: Direction analysis
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    # Angle between neutrino and electron
    ax = axes[0]
    ax.hist(angle_deg, bins=50, alpha=0.7, edgecolor='black')
    ax.axvline(np.median(angle_deg), color='r', linestyle='--', label=f'Median = {np.median(angle_deg):.1f}°')
    ax.set_xlabel('Angle between ν and e (degrees)')
    ax.set_ylabel('Count')
    ax.set_title('Neutrino-Electron Angle Distribution')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Electron angle to average neutrino direction
    ax = axes[1]
    ax.hist(angle_to_avg_nu, bins=50, alpha=0.7, edgecolor='black')
    ax.axvline(np.median(angle_to_avg_nu), color='r', linestyle='--', label=f'Median = {np.median(angle_to_avg_nu):.1f}°')
    ax.set_xlabel('Electron angle to avg ν direction (degrees)')
    ax.set_ylabel('Count')
    ax.set_title('Electron Direction Distribution')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'direction_comparison.png', dpi=150)
    print(f"Saved: {output_dir / 'direction_comparison.png'}")
    plt.close()


def main():
    parser = argparse.ArgumentParser(description='Compare electron and neutrino energies')
    parser.add_argument('--cat-name', default='cat000035', help='Category name')
    parser.add_argument('--cat-dir', help='Full path to category directory')
    parser.add_argument('--output-dir', default='results/energy_comparison', help='Output directory')
    args = parser.parse_args()
    
    if args.cat_dir:
        cat_dir = Path(args.cat_dir)
    else:
        cat_dir = Path('/eos/project-e/ep-nu/public/sn-pointing') / args.cat_name
    
    print(f"\nAnalyzing category: {cat_dir.name}")
    print(f"Path: {cat_dir}")
    
    # Load data
    data = load_es_data(cat_dir)
    
    if data is None:
        print("Failed to load data")
        return
    
    print(f"\nLoaded {len(data['neutrino_energy'])} events")
    
    # Analyze
    energy_ratio, energy_diff, valid_mask = analyze_energies(data)
    angle_deg, angle_to_avg_nu = analyze_directions(data, valid_mask)
    
    # Make plots
    make_plots(data, energy_ratio, energy_diff, angle_deg, angle_to_avg_nu, valid_mask, args.output_dir)
    
    print("\n" + "="*70)
    print("ANALYSIS COMPLETE")
    print("="*70 + "\n")


if __name__ == '__main__':
    main()
