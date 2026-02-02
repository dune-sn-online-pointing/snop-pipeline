#!/usr/bin/env python3
"""
Generate comprehensive PDF report for ED+MCMC results using angle metric.
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
    """Categorize neutrino direction based on alignment with axes."""
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


def plot_angle_distribution(ax, cos_angles, title, color='steelblue'):
    """Plot angle distribution with 68th percentile marked."""
    angles = np.degrees(np.arccos(np.clip(cos_angles, -1, 1)))
    
    ax.hist(angles, bins=60, alpha=0.7, edgecolor='black', color=color)
    
    median_val = np.median(angles)
    percentile_68 = np.percentile(angles, 68)
    
    ax.axvline(median_val, color='red', linestyle='--', linewidth=2.5,
               label=f'Median = {median_val:.1f}°', zorder=10)
    ax.axvline(percentile_68, color='orange', linestyle='--', linewidth=2.5,
               label=f'68th %ile = {percentile_68:.1f}°', zorder=10)
    
    ax.set_xlabel('Angle (degrees) with true neutrino direction', fontsize=12, fontweight='bold')
    ax.set_ylabel('Count', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=13, fontweight='bold')
    ax.legend(fontsize=11, loc='upper right')
    ax.grid(True, alpha=0.3)
    
    # Add statistics box
    forward = np.sum(cos_angles > 0)
    backward = np.sum(cos_angles < 0)
    
    stats_text = f'Events: {len(cos_angles):,}\n'
    stats_text += f'Median: {median_val:.1f}°\n'
    stats_text += f'68th %ile: {percentile_68:.1f}°\n'
    stats_text += f'Forward: {100*forward/len(cos_angles):.1f}%\n'
    stats_text += f'Backward: {100*backward/len(cos_angles):.1f}%'
    
    ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
            verticalalignment='top', horizontalalignment='left',
            fontsize=10, fontweight='bold',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.9),
            family='monospace')
    
    return percentile_68


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--results-file', required=True)
    parser.add_argument('--output-dir', default='results/ed_mcmc_allcats')
    args = parser.parse_args()
    
    results_file = Path(args.results_file)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "="*70)
    print("GENERATING ED+MCMC PDF REPORT (ANGLE METRIC)")
    print("="*70)
    
    angle_threshold = 30
    
    # Load results
    data = np.load(results_file)
    
    cos_angles_all = data['cos_angles']
    successful_cats = data['successful_cats']
    
    n_cats = len(successful_cats)
    n_events = len(cos_angles_all)
    
    print(f"\nTotal categories: {n_cats}")
    print(f"Total events: {n_events:,}")
    
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
    
    print("\nCategorizing by neutrino direction...")
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
            'angle_68': np.percentile(np.degrees(np.arccos(np.clip(cat_cos, -1, 1))), 68)
        })
    
    # Convert to arrays
    for key in categories_data:
        categories_data[key] = np.array(categories_data[key])
    
    print(f"\nCategorization results:")
    for key in ['Z-aligned', 'X-aligned', 'Y-aligned', 'Other']:
        n_events_cat = len(categories_data[key])
        n_cats_cat = sum([1 for c in cat_info if c['category'] == key])
        if n_events_cat > 0:
            angles = np.degrees(np.arccos(np.clip(categories_data[key], -1, 1)))
            angle_68 = np.percentile(angles, 68)
            print(f"  {key:12s}: {n_cats_cat:3d} cats, {n_events_cat:5d} events, angle 68% = {angle_68:.1f}°")
        else:
            print(f"  {key:12s}: {n_cats_cat:3d} cats, {n_events_cat:5d} events")
    
    # Generate PDF
    pdf_file = output_dir / f'ed_mcmc_report_{n_cats}cats.pdf'
    
    print(f"\nGenerating PDF report: {pdf_file}")
    
    with PdfPages(pdf_file) as pdf:
        # Page 1: Overall results
        fig = plt.figure(figsize=(11, 8.5))
        
        fig.text(0.5, 0.97, 'ED Model + MCMC Pointing Performance', 
                ha='center', fontsize=18, fontweight='bold')
        fig.text(0.5, 0.94, f'Overall Results ({n_cats} categories, {n_events:,} events)',
                ha='center', fontsize=14, fontweight='bold', style='italic')
        
        ax1 = plt.subplot(2, 2, (1, 2))
        angle_68_overall = plot_angle_distribution(ax1, cos_angles_all, 
                                'Overall Angle Distribution', 
                                color='steelblue')
        
        ax2 = plt.subplot(2, 2, 3)
        ax2.hist(cos_angles_all, bins=60, alpha=0.7, edgecolor='black', color='coral')
        ax2.axvline(np.median(cos_angles_all), color='red', linestyle='--', linewidth=2)
        ax2.axvline(np.percentile(cos_angles_all, 68), color='orange', linestyle='--', linewidth=2)
        ax2.set_xlabel('cos(θ)', fontsize=11, fontweight='bold')
        ax2.set_ylabel('Count', fontsize=11, fontweight='bold')
        ax2.set_title('Cosine Distribution', fontsize=12, fontweight='bold')
        ax2.grid(True, alpha=0.3)
        
        ax3 = plt.subplot(2, 2, 4)
        ax3.axis('off')
        
        angles_all = np.degrees(np.arccos(np.clip(cos_angles_all, -1, 1)))
        
        summary_text = "SUMMARY STATISTICS\n" + "="*40 + "\n\n"
        summary_text += f"Total Events:          {n_events:,}\n"
        summary_text += f"Successful Categories: {n_cats}\n\n"
        
        summary_text += "Angle Distribution:\n"
        summary_text += f"  Median:              {np.median(angles_all):.1f}°\n"
        summary_text += f"  Mean:                {np.mean(angles_all):.1f}°\n"
        summary_text += f"  68th percentile:     {np.percentile(angles_all, 68):.1f}°\n"
        summary_text += f"  Std deviation:       {np.std(angles_all):.1f}°\n\n"
        
        forward = np.sum(cos_angles_all > 0)
        backward = np.sum(cos_angles_all < 0)
        summary_text += "Pointing Direction:\n"
        summary_text += f"  Forward (cos > 0):   {forward:,} ({100*forward/n_events:.1f}%)\n"
        summary_text += f"  Backward (cos < 0):  {backward:,} ({100*backward/n_events:.1f}%)\n\n"
        
        summary_text += "="*40 + "\n"
        summary_text += "COMPARISON TO BASELINE\n"
        summary_text += "="*40 + "\n\n"
        summary_text += "Best possible (true e⁻ dirs):\n"
        summary_text += f"  Angle 68% = 4.4°\n\n"
        summary_text += "Current (ED model):\n"
        summary_text += f"  Angle 68% = {angle_68_overall:.1f}°\n\n"
        summary_text += f"Gap: Δangle = {angle_68_overall - 4.4:.1f}°"
        
        ax3.text(0.05, 0.95, summary_text, transform=ax3.transAxes,
                verticalalignment='top', fontsize=10, fontweight='bold',
                family='monospace',
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.3))
        
        plt.tight_layout(rect=[0, 0, 1, 0.92])
        pdf.savefig(fig, dpi=150)
        plt.close()
        
        # Pages for each category
        for cat_key, color, color_light in [('Z-aligned', 'green', 'lightgreen'),
                                             ('X-aligned', 'blue', 'lightblue'),
                                             ('Y-aligned', 'purple', 'plum'),
                                             ('Other', 'gray', 'lightgray')]:
            if len(categories_data[cat_key]) == 0:
                continue
                
            fig = plt.figure(figsize=(11, 8.5))
            
            fig.text(0.5, 0.97, 'ED Model + MCMC Pointing Performance', 
                    ha='center', fontsize=18, fontweight='bold')
            
            n_cats_cat = sum([1 for c in cat_info if c['category'] == cat_key])
            n_events_cat = len(categories_data[cat_key])
            
            if cat_key == 'Other':
                subtitle = f'{cat_key} (not aligned with any axis)'
            else:
                subtitle = f'{cat_key} (within ±{angle_threshold}° of axis)'
            
            fig.text(0.5, 0.94, subtitle,
                    ha='center', fontsize=14, fontweight='bold', style='italic')
            fig.text(0.5, 0.91, f'{n_cats_cat} categories, {n_events_cat:,} events',
                    ha='center', fontsize=12, fontweight='bold')
            
            ax1 = plt.subplot(2, 2, (1, 2))
            angle_68_cat = plot_angle_distribution(ax1, categories_data[cat_key],
                                              f'{cat_key}: Angle Distribution',
                                              color=color)
            
            ax2 = plt.subplot(2, 2, 3)
            ax2.hist(categories_data[cat_key], bins=50, alpha=0.7, edgecolor='black', color=color_light)
            ax2.axvline(np.median(categories_data[cat_key]), color='red', linestyle='--', linewidth=2)
            ax2.axvline(np.percentile(categories_data[cat_key], 68), color='orange', linestyle='--', linewidth=2)
            ax2.set_xlabel('cos(θ)', fontsize=11, fontweight='bold')
            ax2.set_ylabel('Count', fontsize=11, fontweight='bold')
            ax2.set_title(f'{cat_key}: Cosine Distribution', fontsize=12, fontweight='bold')
            ax2.grid(True, alpha=0.3)
            
            ax3 = plt.subplot(2, 2, 4)
            ax3.axis('off')
            
            angles_cat = np.degrees(np.arccos(np.clip(categories_data[cat_key], -1, 1)))
            
            summary_text = f"{cat_key.upper()}\n"
            summary_text += "="*40 + "\n\n"
            summary_text += f"Categories:       {n_cats_cat}\n"
            summary_text += f"Events:           {n_events_cat:,}\n"
            summary_text += f"Angle 68%:        {angle_68_cat:.1f}°\n"
            summary_text += f"Median angle:     {np.median(angles_cat):.1f}°\n"
            forward_cat = np.sum(categories_data[cat_key] > 0)
            summary_text += f"Forward:          {100*forward_cat/n_events_cat:.1f}%\n"
            
            plt.tight_layout(rect=[0, 0, 1, 0.89])
            pdf.savefig(fig, dpi=150)
            plt.close()
        
        # Comparison page
        fig = plt.figure(figsize=(11, 8.5))
        
        fig.text(0.5, 0.97, 'ED Model + MCMC Pointing Performance', 
                ha='center', fontsize=18, fontweight='bold')
        fig.text(0.5, 0.94, 'Performance Comparison by Neutrino Direction',
                ha='center', fontsize=14, fontweight='bold', style='italic')
        
        ax1 = plt.subplot(2, 1, 1)
        
        categories = []
        angle68_values = []
        n_cats_list = []
        colors_list = []
        
        for cat_name, color in [('Z-aligned', 'green'), ('X-aligned', 'blue'), 
                                 ('Y-aligned', 'purple'), ('Other', 'gray')]:
            if len(categories_data[cat_name]) > 0:
                categories.append(cat_name)
                angles_cat = np.degrees(np.arccos(np.clip(categories_data[cat_name], -1, 1)))
                angle68_values.append(np.percentile(angles_cat, 68))
                n_cats_list.append(sum([1 for c in cat_info if c['category'] == cat_name]))
                colors_list.append(color)
        
        x_pos = np.arange(len(categories))
        bars = ax1.bar(x_pos, angle68_values, color=colors_list, alpha=0.7, edgecolor='black', linewidth=2)
        
        ax1.axhline(4.4, color='red', linestyle='--', linewidth=2, 
                   label='Best possible (true e⁻ dirs)', zorder=0)
        ax1.axhline(angle_68_overall, color='orange', linestyle='--', linewidth=2,
                   label='Overall average', zorder=0)
        
        for i, (bar, val, n_cat) in enumerate(zip(bars, angle68_values, n_cats_list)):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 2,
                    f'{val:.1f}°\n({n_cat} cats)',
                    ha='center', va='bottom', fontsize=11, fontweight='bold')
        
        ax1.set_ylabel('Angle 68th percentile (degrees)', fontsize=13, fontweight='bold')
        ax1.set_title('Performance by Neutrino Direction Category', fontsize=14, fontweight='bold')
        ax1.set_xticks(x_pos)
        ax1.set_xticklabels(categories, fontsize=12, fontweight='bold')
        ax1.legend(fontsize=11, loc='upper right')
        ax1.grid(True, alpha=0.3, axis='y')
        
        ax2 = plt.subplot(2, 1, 2)
        ax2.axis('off')
        
        summary_text = "PERFORMANCE SUMMARY BY DIRECTION\n"
        summary_text += "="*70 + "\n\n"
        summary_text += f"{'Category':<15} {'N_cats':>8} {'N_events':>10} {'Angle 68%':>12} "
        summary_text += f"{'Median°':>10} {'Forward%':>10}\n"
        summary_text += "-"*70 + "\n"
        
        for cat_name in ['Z-aligned', 'X-aligned', 'Y-aligned', 'Other']:
            if len(categories_data[cat_name]) > 0:
                n_cats_cat = sum([1 for c in cat_info if c['category'] == cat_name])
                n_events_cat = len(categories_data[cat_name])
                angles_cat = np.degrees(np.arccos(np.clip(categories_data[cat_name], -1, 1)))
                angle68 = np.percentile(angles_cat, 68)
                median_angle = np.median(angles_cat)
                forward = 100 * np.sum(categories_data[cat_name] > 0) / n_events_cat
                
                summary_text += f"{cat_name:<15} {n_cats_cat:>8} {n_events_cat:>10,} {angle68:>11.1f}° "
                summary_text += f"{median_angle:>9.1f}° {forward:>9.1f}%\n"
        
        summary_text += "-"*70 + "\n"
        summary_text += f"{'Overall':<15} {n_cats:>8} {n_events:>10,} "
        summary_text += f"{angle_68_overall:>11.1f}° "
        summary_text += f"{np.median(angles_all):>9.1f}° "
        summary_text += f"{100*np.sum(cos_angles_all>0)/n_events:>9.1f}%\n"
        
        summary_text += "\n" + "="*70 + "\n"
        summary_text += "KEY FINDINGS\n"
        summary_text += "="*70 + "\n\n"
        
        summary_text += "• Performance strongly depends on neutrino direction:\n"
        for cat_name in ['Z-aligned', 'X-aligned', 'Y-aligned', 'Other']:
            if len(categories_data[cat_name]) > 0:
                angles_cat = np.degrees(np.arccos(np.clip(categories_data[cat_name], -1, 1)))
                summary_text += f"  - {cat_name}: {np.percentile(angles_cat, 68):.1f}°\n"
        
        summary_text += f"\n• Best possible (true e⁻ directions): 4.4°\n"
        summary_text += f"• Current gap: Δangle = {angle_68_overall - 4.4:.1f}°"
        
        ax2.text(0.05, 0.95, summary_text, transform=ax2.transAxes,
                verticalalignment='top', fontsize=10, fontweight='bold',
                family='monospace',
                bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.5))
        
        plt.tight_layout(rect=[0, 0, 1, 0.92])
        pdf.savefig(fig, dpi=150)
        plt.close()
    
    print(f"PDF report saved: {pdf_file}")
    print("\n" + "="*70 + "\n")


if __name__ == '__main__':
    main()
