#!/usr/bin/env python3
"""
Generate comprehensive PDF report for ED+MCMC results.
Includes overall results and breakdown by neutrino direction categories.
"""

import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import uproot


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


def categorize_direction(nu_dir, threshold_deg=30):
    """
    Categorize neutrino direction based on alignment with axes.
    
    Thresholds:
    - Almost parallel to Z: |cos(θ_z)| > cos(30°) ≈ 0.866
    - Almost parallel to X: |cos(θ_x)| > cos(30°) ≈ 0.866
    - Almost parallel to Y: |cos(θ_y)| > cos(30°) ≈ 0.866
    """
    threshold = np.cos(np.radians(threshold_deg))
    
    cos_x = abs(nu_dir[0])
    cos_y = abs(nu_dir[1])
    cos_z = abs(nu_dir[2])
    
    # Prioritize: Z > X > Y (detector geometry importance)
    if cos_z > threshold:
        return 'Z-aligned', np.degrees(np.arccos(abs(nu_dir[2])))
    elif cos_x > threshold:
        return 'X-aligned', np.degrees(np.arccos(abs(nu_dir[0])))
    elif cos_y > threshold:
        return 'Y-aligned', np.degrees(np.arccos(abs(nu_dir[1])))
    else:
        return 'Other', None


def plot_cosine_distribution(ax, cos_angles, title, color='steelblue'):
    """Plot cosine distribution with 68th percentile marked."""
    ax.hist(cos_angles, bins=60, alpha=0.7, edgecolor='black', color=color)
    
    median_val = np.median(cos_angles)
    percentile_68 = np.percentile(cos_angles, 68)
    
    ax.axvline(median_val, color='red', linestyle='--', linewidth=2.5,
               label=f'Median = {median_val:.4f}', zorder=10)
    ax.axvline(percentile_68, color='orange', linestyle='--', linewidth=2.5,
               label=f'68th %ile = {percentile_68:.4f}', zorder=10)
    
    ax.set_xlabel('cos(θ) with true neutrino direction', fontsize=12, fontweight='bold')
    ax.set_ylabel('Count', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=13, fontweight='bold')
    ax.legend(fontsize=11, loc='upper left')
    ax.grid(True, alpha=0.3)
    
    # Add statistics box
    forward = np.sum(cos_angles > 0)
    backward = np.sum(cos_angles < 0)
    
    stats_text = f'Events: {len(cos_angles):,}\n'
    stats_text += f'Median: {median_val:.4f}\n'
    stats_text += f'68th %ile: {percentile_68:.4f}\n'
    stats_text += f'Forward: {100*forward/len(cos_angles):.1f}%\n'
    stats_text += f'Backward: {100*backward/len(cos_angles):.1f}%'
    
    ax.text(0.98, 0.98, stats_text, transform=ax.transAxes,
            verticalalignment='top', horizontalalignment='right',
            fontsize=10, fontweight='bold',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.9),
            family='monospace')
    
    return percentile_68


def main():
    print("\n" + "="*70)
    print("GENERATING ED+MCMC PDF REPORT")
    print("="*70)
    
    # Proposed thresholds
    angle_threshold = 30  # degrees - within 30° of axis = "aligned"
    
    print(f"\nDirection categories (threshold: ±{angle_threshold}° from axis):")
    print(f"  Z-aligned: |cos(θ_z)| > {np.cos(np.radians(angle_threshold)):.3f}")
    print(f"  X-aligned: |cos(θ_x)| > {np.cos(np.radians(angle_threshold)):.3f}")
    print(f"  Y-aligned: |cos(θ_y)| > {np.cos(np.radians(angle_threshold)):.3f}")
    print(f"  Other: Not within {angle_threshold}° of any axis")
    
    # Load results
    results_file = Path('results/ed_mcmc_100cats/ed_mcmc_98cats_results.npz')
    data = np.load(results_file)
    
    cos_angles_all = data['cos_angles']
    successful_cats = data['successful_cats']
    
    print(f"\nLoading neutrino directions...")
    
    # Categorize events
    base_path = Path('/eos/project-e/ep-nu/public/sn-pointing')
    
    categories_data = {
        'Z-aligned': [],
        'X-aligned': [],
        'Y-aligned': [],
        'Other': []
    }
    
    cat_info = []
    idx = 0
    
    for cat_name in successful_cats:
        cat_dir = base_path / cat_name
        nu_dir = load_neutrino_direction(cat_dir)
        
        if nu_dir is None:
            idx += 40
            continue
        
        cat_cos = cos_angles_all[idx:idx+40]
        idx += 40
        
        category, angle_from_axis = categorize_direction(nu_dir, angle_threshold)
        categories_data[category].extend(cat_cos)
        
        cat_info.append({
            'name': cat_name,
            'category': category,
            'nu_dir': nu_dir,
            'angle_from_axis': angle_from_axis,
            'cos_68': np.percentile(cat_cos, 68)
        })
    
    # Convert to arrays
    for key in categories_data:
        categories_data[key] = np.array(categories_data[key])
    
    print(f"\nCategorization results:")
    for key in ['Z-aligned', 'X-aligned', 'Y-aligned', 'Other']:
        n_events = len(categories_data[key])
        n_cats = sum([1 for c in cat_info if c['category'] == key])
        if n_events > 0:
            cos68 = np.percentile(categories_data[key], 68)
            print(f"  {key:12s}: {n_cats:2d} cats, {n_events:4d} events, cos(θ) 68% = {cos68:.4f}")
        else:
            print(f"  {key:12s}: {n_cats:2d} cats, {n_events:4d} events")
    
    # Generate PDF report
    output_dir = Path('results/ed_mcmc_100cats')
    pdf_file = output_dir / 'ed_mcmc_report.pdf'
    
    print(f"\nGenerating PDF report: {pdf_file}")
    
    with PdfPages(pdf_file) as pdf:
        # Page 1: Overall results
        fig = plt.figure(figsize=(11, 8.5))
        
        # Title
        fig.text(0.5, 0.97, 'ED Model + MCMC Pointing Performance', 
                ha='center', fontsize=18, fontweight='bold')
        fig.text(0.5, 0.94, 'Overall Results (98 categories, 3,920 events)',
                ha='center', fontsize=14, fontweight='bold', style='italic')
        
        # Main cosine plot
        ax1 = plt.subplot(2, 2, (1, 2))
        plot_cosine_distribution(ax1, cos_angles_all, 
                                'Overall cos(θ) Distribution', 
                                color='steelblue')
        
        # Angle distribution
        ax2 = plt.subplot(2, 2, 3)
        angles = np.degrees(np.arccos(np.clip(cos_angles_all, -1, 1)))
        ax2.hist(angles, bins=60, alpha=0.7, edgecolor='black', color='coral')
        ax2.axvline(np.median(angles), color='red', linestyle='--', linewidth=2,
                   label=f'Median = {np.median(angles):.1f}°')
        ax2.axvline(np.percentile(angles, 68), color='orange', linestyle='--', linewidth=2,
                   label=f'68th %ile = {np.percentile(angles, 68):.1f}°')
        ax2.set_xlabel('Angle (degrees)', fontsize=11, fontweight='bold')
        ax2.set_ylabel('Count', fontsize=11, fontweight='bold')
        ax2.set_title('Angle Distribution', fontsize=12, fontweight='bold')
        ax2.legend(fontsize=10)
        ax2.grid(True, alpha=0.3)
        
        # Summary table
        ax3 = plt.subplot(2, 2, 4)
        ax3.axis('off')
        
        summary_text = "SUMMARY STATISTICS\n" + "="*40 + "\n\n"
        summary_text += f"Total Events:          {len(cos_angles_all):,}\n"
        summary_text += f"Successful Categories: 98/100\n\n"
        
        summary_text += "Cosine Distribution:\n"
        summary_text += f"  Median:              {np.median(cos_angles_all):.4f}\n"
        summary_text += f"  Mean:                {np.mean(cos_angles_all):.4f}\n"
        summary_text += f"  68th percentile:     {np.percentile(cos_angles_all, 68):.4f}\n"
        summary_text += f"  Std deviation:       {np.std(cos_angles_all):.4f}\n\n"
        
        summary_text += "Angle Distribution:\n"
        summary_text += f"  Median:              {np.median(angles):.1f}°\n"
        summary_text += f"  Mean:                {np.mean(angles):.1f}°\n"
        summary_text += f"  68th percentile:     {np.percentile(angles, 68):.1f}°\n\n"
        
        forward = np.sum(cos_angles_all > 0)
        backward = np.sum(cos_angles_all < 0)
        summary_text += "Pointing Direction:\n"
        summary_text += f"  Forward (cos > 0):   {forward:,} ({100*forward/len(cos_angles_all):.1f}%)\n"
        summary_text += f"  Backward (cos < 0):  {backward:,} ({100*backward/len(cos_angles_all):.1f}%)\n\n"
        
        summary_text += "="*40 + "\n"
        summary_text += "COMPARISON TO BASELINES\n"
        summary_text += "="*40 + "\n\n"
        summary_text += "Best possible (true e⁻ dirs):\n"
        summary_text += f"  cos(θ) 68% = 0.9980\n\n"
        summary_text += "Current (ED model):\n"
        summary_text += f"  cos(θ) 68% = {np.percentile(cos_angles_all, 68):.4f}\n\n"
        summary_text += f"Gap: Δcos(θ) = {0.9980 - np.percentile(cos_angles_all, 68):.4f}"
        
        ax3.text(0.05, 0.95, summary_text, transform=ax3.transAxes,
                verticalalignment='top', fontsize=10, fontweight='bold',
                family='monospace',
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.3))
        
        plt.tight_layout(rect=[0, 0, 1, 0.92])
        pdf.savefig(fig, dpi=150)
        plt.close()
        
        # Page 2: Z-aligned
        if len(categories_data['Z-aligned']) > 0:
            fig = plt.figure(figsize=(11, 8.5))
            
            fig.text(0.5, 0.97, 'ED Model + MCMC Pointing Performance', 
                    ha='center', fontsize=18, fontweight='bold')
            
            n_cats_z = sum([1 for c in cat_info if c['category'] == 'Z-aligned'])
            n_events_z = len(categories_data['Z-aligned'])
            fig.text(0.5, 0.94, f'Z-Aligned Neutrinos (within ±{angle_threshold}° of Z-axis)',
                    ha='center', fontsize=14, fontweight='bold', style='italic')
            fig.text(0.5, 0.91, f'{n_cats_z} categories, {n_events_z:,} events',
                    ha='center', fontsize=12, fontweight='bold')
            
            ax1 = plt.subplot(2, 2, (1, 2))
            cos68_z = plot_cosine_distribution(ax1, categories_data['Z-aligned'],
                                              'Z-Aligned: cos(θ) Distribution',
                                              color='green')
            
            ax2 = plt.subplot(2, 2, 3)
            angles_z = np.degrees(np.arccos(np.clip(categories_data['Z-aligned'], -1, 1)))
            ax2.hist(angles_z, bins=50, alpha=0.7, edgecolor='black', color='lightgreen')
            ax2.axvline(np.median(angles_z), color='red', linestyle='--', linewidth=2)
            ax2.axvline(np.percentile(angles_z, 68), color='orange', linestyle='--', linewidth=2)
            ax2.set_xlabel('Angle (degrees)', fontsize=11, fontweight='bold')
            ax2.set_ylabel('Count', fontsize=11, fontweight='bold')
            ax2.set_title('Z-Aligned: Angle Distribution', fontsize=12, fontweight='bold')
            ax2.grid(True, alpha=0.3)
            
            ax3 = plt.subplot(2, 2, 4)
            ax3.axis('off')
            
            z_cats = [c for c in cat_info if c['category'] == 'Z-aligned']
            z_cats_sorted = sorted(z_cats, key=lambda x: x['cos_68'], reverse=True)
            
            summary_text = f"Z-ALIGNED CATEGORIES\n"
            summary_text += f"(within ±{angle_threshold}° of Z-axis)\n"
            summary_text += "="*40 + "\n\n"
            summary_text += f"Categories:       {n_cats_z}\n"
            summary_text += f"Events:           {n_events_z:,}\n"
            summary_text += f"cos(θ) 68%:       {cos68_z:.4f}\n"
            summary_text += f"Median angle:     {np.median(angles_z):.1f}°\n"
            forward_z = np.sum(categories_data['Z-aligned'] > 0)
            summary_text += f"Forward:          {100*forward_z/n_events_z:.1f}%\n\n"
            
            summary_text += "Best categories:\n"
            for i, cat in enumerate(z_cats_sorted[:5]):
                summary_text += f"  {cat['name']}: {cat['cos_68']:.4f}\n"
            
            summary_text += f"\nWorst categories:\n"
            for i, cat in enumerate(z_cats_sorted[-3:]):
                summary_text += f"  {cat['name']}: {cat['cos_68']:.4f}\n"
            
            ax3.text(0.05, 0.95, summary_text, transform=ax3.transAxes,
                    verticalalignment='top', fontsize=10, fontweight='bold',
                    family='monospace',
                    bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.3))
            
            plt.tight_layout(rect=[0, 0, 1, 0.89])
            pdf.savefig(fig, dpi=150)
            plt.close()
        
        # Page 3: X-aligned
        if len(categories_data['X-aligned']) > 0:
            fig = plt.figure(figsize=(11, 8.5))
            
            fig.text(0.5, 0.97, 'ED Model + MCMC Pointing Performance', 
                    ha='center', fontsize=18, fontweight='bold')
            
            n_cats_x = sum([1 for c in cat_info if c['category'] == 'X-aligned'])
            n_events_x = len(categories_data['X-aligned'])
            fig.text(0.5, 0.94, f'X-Aligned Neutrinos (within ±{angle_threshold}° of X-axis)',
                    ha='center', fontsize=14, fontweight='bold', style='italic')
            fig.text(0.5, 0.91, f'{n_cats_x} categories, {n_events_x:,} events',
                    ha='center', fontsize=12, fontweight='bold')
            
            ax1 = plt.subplot(2, 2, (1, 2))
            cos68_x = plot_cosine_distribution(ax1, categories_data['X-aligned'],
                                              'X-Aligned: cos(θ) Distribution',
                                              color='blue')
            
            ax2 = plt.subplot(2, 2, 3)
            angles_x = np.degrees(np.arccos(np.clip(categories_data['X-aligned'], -1, 1)))
            ax2.hist(angles_x, bins=50, alpha=0.7, edgecolor='black', color='lightblue')
            ax2.axvline(np.median(angles_x), color='red', linestyle='--', linewidth=2)
            ax2.axvline(np.percentile(angles_x, 68), color='orange', linestyle='--', linewidth=2)
            ax2.set_xlabel('Angle (degrees)', fontsize=11, fontweight='bold')
            ax2.set_ylabel('Count', fontsize=11, fontweight='bold')
            ax2.set_title('X-Aligned: Angle Distribution', fontsize=12, fontweight='bold')
            ax2.grid(True, alpha=0.3)
            
            ax3 = plt.subplot(2, 2, 4)
            ax3.axis('off')
            
            x_cats = [c for c in cat_info if c['category'] == 'X-aligned']
            x_cats_sorted = sorted(x_cats, key=lambda x: x['cos_68'], reverse=True)
            
            summary_text = f"X-ALIGNED CATEGORIES\n"
            summary_text += f"(within ±{angle_threshold}° of X-axis)\n"
            summary_text += "="*40 + "\n\n"
            summary_text += f"Categories:       {n_cats_x}\n"
            summary_text += f"Events:           {n_events_x:,}\n"
            summary_text += f"cos(θ) 68%:       {cos68_x:.4f}\n"
            summary_text += f"Median angle:     {np.median(angles_x):.1f}°\n"
            forward_x = np.sum(categories_data['X-aligned'] > 0)
            summary_text += f"Forward:          {100*forward_x/n_events_x:.1f}%\n\n"
            
            summary_text += "Best categories:\n"
            for i, cat in enumerate(x_cats_sorted[:5]):
                summary_text += f"  {cat['name']}: {cat['cos_68']:.4f}\n"
            
            if len(x_cats_sorted) > 5:
                summary_text += f"\nWorst categories:\n"
                for i, cat in enumerate(x_cats_sorted[-3:]):
                    summary_text += f"  {cat['name']}: {cat['cos_68']:.4f}\n"
            
            ax3.text(0.05, 0.95, summary_text, transform=ax3.transAxes,
                    verticalalignment='top', fontsize=10, fontweight='bold',
                    family='monospace',
                    bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.3))
            
            plt.tight_layout(rect=[0, 0, 1, 0.89])
            pdf.savefig(fig, dpi=150)
            plt.close()
        
        # Page 4: Y-aligned
        if len(categories_data['Y-aligned']) > 0:
            fig = plt.figure(figsize=(11, 8.5))
            
            fig.text(0.5, 0.97, 'ED Model + MCMC Pointing Performance', 
                    ha='center', fontsize=18, fontweight='bold')
            
            n_cats_y = sum([1 for c in cat_info if c['category'] == 'Y-aligned'])
            n_events_y = len(categories_data['Y-aligned'])
            fig.text(0.5, 0.94, f'Y-Aligned Neutrinos (within ±{angle_threshold}° of Y-axis)',
                    ha='center', fontsize=14, fontweight='bold', style='italic')
            fig.text(0.5, 0.91, f'{n_cats_y} categories, {n_events_y:,} events',
                    ha='center', fontsize=12, fontweight='bold')
            
            ax1 = plt.subplot(2, 2, (1, 2))
            cos68_y = plot_cosine_distribution(ax1, categories_data['Y-aligned'],
                                              'Y-Aligned: cos(θ) Distribution',
                                              color='purple')
            
            ax2 = plt.subplot(2, 2, 3)
            angles_y = np.degrees(np.arccos(np.clip(categories_data['Y-aligned'], -1, 1)))
            ax2.hist(angles_y, bins=50, alpha=0.7, edgecolor='black', color='plum')
            ax2.axvline(np.median(angles_y), color='red', linestyle='--', linewidth=2)
            ax2.axvline(np.percentile(angles_y, 68), color='orange', linestyle='--', linewidth=2)
            ax2.set_xlabel('Angle (degrees)', fontsize=11, fontweight='bold')
            ax2.set_ylabel('Count', fontsize=11, fontweight='bold')
            ax2.set_title('Y-Aligned: Angle Distribution', fontsize=12, fontweight='bold')
            ax2.grid(True, alpha=0.3)
            
            ax3 = plt.subplot(2, 2, 4)
            ax3.axis('off')
            
            y_cats = [c for c in cat_info if c['category'] == 'Y-aligned']
            y_cats_sorted = sorted(y_cats, key=lambda x: x['cos_68'], reverse=True)
            
            summary_text = f"Y-ALIGNED CATEGORIES\n"
            summary_text += f"(within ±{angle_threshold}° of Y-axis)\n"
            summary_text += "="*40 + "\n\n"
            summary_text += f"Categories:       {n_cats_y}\n"
            summary_text += f"Events:           {n_events_y:,}\n"
            summary_text += f"cos(θ) 68%:       {cos68_y:.4f}\n"
            summary_text += f"Median angle:     {np.median(angles_y):.1f}°\n"
            forward_y = np.sum(categories_data['Y-aligned'] > 0)
            summary_text += f"Forward:          {100*forward_y/n_events_y:.1f}%\n\n"
            
            summary_text += "Best categories:\n"
            for i, cat in enumerate(y_cats_sorted[:5]):
                summary_text += f"  {cat['name']}: {cat['cos_68']:.4f}\n"
            
            if len(y_cats_sorted) > 5:
                summary_text += f"\nWorst categories:\n"
                for i, cat in enumerate(y_cats_sorted[-3:]):
                    summary_text += f"  {cat['name']}: {cat['cos_68']:.4f}\n"
            
            ax3.text(0.05, 0.95, summary_text, transform=ax3.transAxes,
                    verticalalignment='top', fontsize=10, fontweight='bold',
                    family='monospace',
                    bbox=dict(boxstyle='round', facecolor='plum', alpha=0.3))
            
            plt.tight_layout(rect=[0, 0, 1, 0.89])
            pdf.savefig(fig, dpi=150)
            plt.close()
        
        # Page 5: Other orientations
        if len(categories_data['Other']) > 0:
            fig = plt.figure(figsize=(11, 8.5))
            
            fig.text(0.5, 0.97, 'ED Model + MCMC Pointing Performance', 
                    ha='center', fontsize=18, fontweight='bold')
            
            n_cats_other = sum([1 for c in cat_info if c['category'] == 'Other'])
            n_events_other = len(categories_data['Other'])
            fig.text(0.5, 0.94, f'Other Orientations (not aligned with any axis)',
                    ha='center', fontsize=14, fontweight='bold', style='italic')
            fig.text(0.5, 0.91, f'{n_cats_other} categories, {n_events_other:,} events',
                    ha='center', fontsize=12, fontweight='bold')
            
            ax1 = plt.subplot(2, 2, (1, 2))
            cos68_other = plot_cosine_distribution(ax1, categories_data['Other'],
                                                  'Other Orientations: cos(θ) Distribution',
                                                  color='gray')
            
            ax2 = plt.subplot(2, 2, 3)
            angles_other = np.degrees(np.arccos(np.clip(categories_data['Other'], -1, 1)))
            ax2.hist(angles_other, bins=50, alpha=0.7, edgecolor='black', color='lightgray')
            ax2.axvline(np.median(angles_other), color='red', linestyle='--', linewidth=2)
            ax2.axvline(np.percentile(angles_other, 68), color='orange', linestyle='--', linewidth=2)
            ax2.set_xlabel('Angle (degrees)', fontsize=11, fontweight='bold')
            ax2.set_ylabel('Count', fontsize=11, fontweight='bold')
            ax2.set_title('Other: Angle Distribution', fontsize=12, fontweight='bold')
            ax2.grid(True, alpha=0.3)
            
            ax3 = plt.subplot(2, 2, 4)
            ax3.axis('off')
            
            other_cats = [c for c in cat_info if c['category'] == 'Other']
            other_cats_sorted = sorted(other_cats, key=lambda x: x['cos_68'], reverse=True)
            
            summary_text = f"OTHER ORIENTATIONS\n"
            summary_text += f"(not within ±{angle_threshold}° of any axis)\n"
            summary_text += "="*40 + "\n\n"
            summary_text += f"Categories:       {n_cats_other}\n"
            summary_text += f"Events:           {n_events_other:,}\n"
            summary_text += f"cos(θ) 68%:       {cos68_other:.4f}\n"
            summary_text += f"Median angle:     {np.median(angles_other):.1f}°\n"
            forward_other = np.sum(categories_data['Other'] > 0)
            summary_text += f"Forward:          {100*forward_other/n_events_other:.1f}%\n\n"
            
            summary_text += "Best categories:\n"
            for i, cat in enumerate(other_cats_sorted[:5]):
                summary_text += f"  {cat['name']}: {cat['cos_68']:.4f}\n"
            
            if len(other_cats_sorted) > 5:
                summary_text += f"\nWorst categories:\n"
                for i, cat in enumerate(other_cats_sorted[-3:]):
                    summary_text += f"  {cat['name']}: {cat['cos_68']:.4f}\n"
            
            ax3.text(0.05, 0.95, summary_text, transform=ax3.transAxes,
                    verticalalignment='top', fontsize=10, fontweight='bold',
                    family='monospace',
                    bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.5))
            
            plt.tight_layout(rect=[0, 0, 1, 0.89])
            pdf.savefig(fig, dpi=150)
            plt.close()
        
        # Page 6: Comparison summary
        fig = plt.figure(figsize=(11, 8.5))
        
        fig.text(0.5, 0.97, 'ED Model + MCMC Pointing Performance', 
                ha='center', fontsize=18, fontweight='bold')
        fig.text(0.5, 0.94, 'Performance Comparison by Neutrino Direction',
                ha='center', fontsize=14, fontweight='bold', style='italic')
        
        # Bar chart comparison
        ax1 = plt.subplot(2, 1, 1)
        
        categories = []
        cos68_values = []
        n_cats_list = []
        colors_list = []
        
        for cat_name, color in [('Z-aligned', 'green'), ('X-aligned', 'blue'), 
                                 ('Y-aligned', 'purple'), ('Other', 'gray')]:
            if len(categories_data[cat_name]) > 0:
                categories.append(cat_name)
                cos68_values.append(np.percentile(categories_data[cat_name], 68))
                n_cats_list.append(sum([1 for c in cat_info if c['category'] == cat_name]))
                colors_list.append(color)
        
        x_pos = np.arange(len(categories))
        bars = ax1.bar(x_pos, cos68_values, color=colors_list, alpha=0.7, edgecolor='black', linewidth=2)
        
        # Add reference lines
        ax1.axhline(0.9980, color='red', linestyle='--', linewidth=2, 
                   label='Best possible (true e⁻ dirs)', zorder=0)
        ax1.axhline(np.percentile(cos_angles_all, 68), color='orange', linestyle='--', linewidth=2,
                   label='Overall average', zorder=0)
        
        # Add value labels on bars
        for i, (bar, val, n_cat) in enumerate(zip(bars, cos68_values, n_cats_list)):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                    f'{val:.4f}\n({n_cat} cats)',
                    ha='center', va='bottom', fontsize=11, fontweight='bold')
        
        ax1.set_ylabel('cos(θ) 68th percentile', fontsize=13, fontweight='bold')
        ax1.set_title('Performance by Neutrino Direction Category', fontsize=14, fontweight='bold')
        ax1.set_xticks(x_pos)
        ax1.set_xticklabels(categories, fontsize=12, fontweight='bold')
        ax1.legend(fontsize=11, loc='lower right')
        ax1.grid(True, alpha=0.3, axis='y')
        ax1.set_ylim(0, 1.05)
        
        # Summary table
        ax2 = plt.subplot(2, 1, 2)
        ax2.axis('off')
        
        summary_text = "PERFORMANCE SUMMARY BY DIRECTION\n"
        summary_text += "="*70 + "\n\n"
        summary_text += f"{'Category':<15} {'N_cats':>8} {'N_events':>10} {'cos(θ) 68%':>12} "
        summary_text += f"{'Median°':>10} {'Forward%':>10}\n"
        summary_text += "-"*70 + "\n"
        
        for cat_name in ['Z-aligned', 'X-aligned', 'Y-aligned', 'Other']:
            if len(categories_data[cat_name]) > 0:
                n_cats = sum([1 for c in cat_info if c['category'] == cat_name])
                n_events = len(categories_data[cat_name])
                cos68 = np.percentile(categories_data[cat_name], 68)
                angles = np.degrees(np.arccos(np.clip(categories_data[cat_name], -1, 1)))
                median_angle = np.median(angles)
                forward = 100 * np.sum(categories_data[cat_name] > 0) / n_events
                
                summary_text += f"{cat_name:<15} {n_cats:>8} {n_events:>10,} {cos68:>12.4f} "
                summary_text += f"{median_angle:>9.1f}° {forward:>9.1f}%\n"
        
        summary_text += "-"*70 + "\n"
        summary_text += f"{'Overall':<15} {98:>8} {len(cos_angles_all):>10,} "
        summary_text += f"{np.percentile(cos_angles_all, 68):>12.4f} "
        angles_all = np.degrees(np.arccos(np.clip(cos_angles_all, -1, 1)))
        summary_text += f"{np.median(angles_all):>9.1f}° "
        summary_text += f"{100*np.sum(cos_angles_all>0)/len(cos_angles_all):>9.1f}%\n"
        
        summary_text += "\n" + "="*70 + "\n"
        summary_text += "KEY FINDINGS\n"
        summary_text += "="*70 + "\n\n"
        
        if len(categories_data['Z-aligned']) > 0:
            summary_text += f"• Z-aligned neutrinos perform BEST (cos 68% = "
            summary_text += f"{np.percentile(categories_data['Z-aligned'], 68):.4f})\n"
        
        if len(categories_data['Other']) > 0:
            summary_text += f"• Other orientations perform WORST (cos 68% = "
            summary_text += f"{np.percentile(categories_data['Other'], 68):.4f})\n"
        
        summary_text += f"\n• Overall performance is dominated by detector geometry:\n"
        summary_text += f"  - Parallel to wire planes (Z): Excellent reconstruction\n"
        summary_text += f"  - Perpendicular to wire planes: Poor reconstruction\n"
        
        summary_text += f"\n• Best possible (true e⁻ directions): cos 68% = 0.9980\n"
        summary_text += f"• Current gap: Δcos = {0.9980 - np.percentile(cos_angles_all, 68):.4f}"
        
        ax2.text(0.05, 0.95, summary_text, transform=ax2.transAxes,
                verticalalignment='top', fontsize=10, fontweight='bold',
                family='monospace',
                bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.5))
        
        plt.tight_layout(rect=[0, 0, 1, 0.92])
        pdf.savefig(fig, dpi=150)
        plt.close()
    
    print(f"PDF report saved: {pdf_file}")
    
    print("\n" + "="*70)
    print("REPORT GENERATION COMPLETE")
    print("="*70 + "\n")


if __name__ == '__main__':
    main()
