#!/usr/bin/env python3
"""
Aggregate ED+MCMC results across multiple categories.
Computes overall performance metrics including 68% quantile of cosine(angle).
"""

import argparse
import json
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from matplotlib.backends.backend_pdf import PdfPages


def load_cat_results(results_dir):
    """Load all cat results from directory."""
    results_dir = Path(results_dir)
    all_results = []
    
    for cat_dir in sorted(results_dir.iterdir()):
        if not cat_dir.is_dir():
            continue
        
        metrics_file = cat_dir / 'metrics.json'
        if not metrics_file.exists():
            continue
        
        with open(metrics_file, 'r') as f:
            data = json.load(f)
            all_results.append(data)
    
    return all_results


def aggregate_metrics(all_results):
    """Compute aggregate statistics across all cats."""
    # Collect all event-level cosines
    all_cosines = []
    all_angles = []
    
    for cat_data in all_results:
        for event in cat_data['events']:
            all_cosines.append(event['cosine_angle'])
            all_angles.append(event['angle_deg'])
    
    all_cosines = np.array(all_cosines)
    all_angles = np.array(all_angles)
    
    metrics = {
        'n_cats': len(all_results),
        'n_events_total': len(all_cosines),
        'cosine': {
            'mean': float(np.mean(all_cosines)),
            'median': float(np.median(all_cosines)),
            'std': float(np.std(all_cosines)),
            'p68': float(np.percentile(all_cosines, 68)),
            'p90': float(np.percentile(all_cosines, 90)),
            'p50': float(np.percentile(all_cosines, 50)),
            'p32': float(np.percentile(all_cosines, 32)),
        },
        'angle_deg': {
            'mean': float(np.mean(all_angles)),
            'median': float(np.median(all_angles)),
            'std': float(np.std(all_angles)),
            'p68': float(np.percentile(all_angles, 68)),
            'p90': float(np.percentile(all_angles, 90)),
        }
    }
    
    return metrics, all_cosines, all_angles


def generate_pdf_report(all_results, metrics, all_cosines, all_angles, output_pdf):
    """Generate comprehensive PDF report."""
    
    with PdfPages(output_pdf) as pdf:
        # Page 1: Overall metrics
        fig = plt.figure(figsize=(11, 8.5))
        fig.suptitle(f'ED + MCMC Direction Reconstruction\n{metrics["n_cats"]} Categories, {metrics["n_events_total"]} Events', 
                     fontsize=16, fontweight='bold')
        
        ax = fig.add_subplot(111)
        ax.axis('off')
        
        text = f"""
PERFORMANCE SUMMARY
{'='*60}

Cosine of Angle (True vs Reconstructed Direction)
  Mean:           {metrics['cosine']['mean']:.4f}
  Median (p50):   {metrics['cosine']['median']:.4f}
  68th percentile: {metrics['cosine']['p68']:.4f} ← PRIMARY METRIC
  90th percentile: {metrics['cosine']['p90']:.4f}
  Std deviation:  {metrics['cosine']['std']:.4f}

Angular Error (degrees)
  Mean:           {metrics['angle_deg']['mean']:.2f}°
  Median:         {metrics['angle_deg']['median']:.2f}°
  68th percentile: {metrics['angle_deg']['p68']:.2f}°
  90th percentile: {metrics['angle_deg']['p90']:.2f}°

INTERPRETATION
{'='*60}

68% of events have cos(angle) ≥ {metrics['cosine']['p68']:.4f}
  → 68% of events within {np.degrees(np.arccos(metrics['cosine']['p68'])):.2f}° angular resolution

Perfect pointing: cos(angle) = 1.0 (0°)
Random pointing: cos(angle) ~ 0.0 (90°)

Dataset: {metrics['n_cats']} categories × ~{metrics['n_events_total']//metrics['n_cats']} events/cat
"""
        ax.text(0.1, 0.5, text, fontsize=12, family='monospace', va='center')
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        # Page 2: Cosine distribution
        fig, axes = plt.subplots(2, 1, figsize=(11, 8.5))
        fig.suptitle('Distribution of cos(angle) Between True and Reconstructed', fontsize=14, fontweight='bold')
        
        # Histogram
        ax = axes[0]
        ax.hist(all_cosines, bins=50, alpha=0.7, edgecolor='black')
        ax.axvline(metrics['cosine']['p68'], color='r', linestyle='--', linewidth=2, label=f"68th %ile: {metrics['cosine']['p68']:.4f}")
        ax.axvline(metrics['cosine']['median'], color='g', linestyle='--', linewidth=2, label=f"Median: {metrics['cosine']['median']:.4f}")
        ax.axvline(metrics['cosine']['mean'], color='b', linestyle='--', linewidth=2, label=f"Mean: {metrics['cosine']['mean']:.4f}")
        ax.set_xlabel('cos(angle)', fontsize=12)
        ax.set_ylabel('Number of Events', fontsize=12)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        
        # CDF
        ax = axes[1]
        sorted_cosines = np.sort(all_cosines)
        cdf = np.arange(1, len(sorted_cosines) + 1) / len(sorted_cosines) * 100
        ax.plot(sorted_cosines, cdf, linewidth=2)
        ax.axvline(metrics['cosine']['p68'], color='r', linestyle='--', linewidth=2, label='68th %ile')
        ax.axhline(68, color='r', linestyle='--', linewidth=1, alpha=0.5)
        ax.set_xlabel('cos(angle)', fontsize=12)
        ax.set_ylabel('Cumulative Percentage (%)', fontsize=12)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        # Page 3: Angular error distribution
        fig, axes = plt.subplots(2, 1, figsize=(11, 8.5))
        fig.suptitle('Angular Error Distribution (degrees)', fontsize=14, fontweight='bold')
        
        # Histogram
        ax = axes[0]
        ax.hist(all_angles, bins=50, alpha=0.7, edgecolor='black', color='orange')
        ax.axvline(metrics['angle_deg']['p68'], color='r', linestyle='--', linewidth=2, label=f"68th %ile: {metrics['angle_deg']['p68']:.2f}°")
        ax.axvline(metrics['angle_deg']['median'], color='g', linestyle='--', linewidth=2, label=f"Median: {metrics['angle_deg']['median']:.2f}°")
        ax.set_xlabel('Angular Error (degrees)', fontsize=12)
        ax.set_ylabel('Number of Events', fontsize=12)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        
        # CDF
        ax = axes[1]
        sorted_angles = np.sort(all_angles)
        cdf = np.arange(1, len(sorted_angles) + 1) / len(sorted_angles) * 100
        ax.plot(sorted_angles, cdf, linewidth=2, color='orange')
        ax.axvline(metrics['angle_deg']['p68'], color='r', linestyle='--', linewidth=2, label='68th %ile')
        ax.axhline(68, color='r', linestyle='--', linewidth=1, alpha=0.5)
        ax.set_xlabel('Angular Error (degrees)', fontsize=12)
        ax.set_ylabel('Cumulative Percentage (%)', fontsize=12)
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        # Page 4: Per-category breakdown
        fig, ax = plt.subplots(figsize=(11, 8.5))
        fig.suptitle('Performance by Category', fontsize=14, fontweight='bold')
        
        cat_names = [r['cat_name'] for r in all_results]
        cat_p68 = [r['summary']['p68_cosine'] for r in all_results]
        cat_median = [r['summary']['median_cosine'] for r in all_results]
        
        x = np.arange(len(cat_names))
        width = 0.35
        
        ax.bar(x - width/2, cat_p68, width, label='68th %ile', alpha=0.8)
        ax.bar(x + width/2, cat_median, width, label='Median', alpha=0.8)
        ax.axhline(metrics['cosine']['p68'], color='r', linestyle='--', linewidth=2, alpha=0.5, label='Overall 68th %ile')
        
        ax.set_xlabel('Category', fontsize=12)
        ax.set_ylabel('cos(angle)', fontsize=12)
        ax.set_xticks(x)
        ax.set_xticklabels(cat_names, rotation=45, ha='right')
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
    
    print(f"✓ PDF report saved to: {output_pdf}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results-dir', default='results/ed_mcmc_cats', help='Directory with per-cat results')
    parser.add_argument('--output', default='results/ed_mcmc_aggregate_report.pdf', help='Output PDF file')
    parser.add_argument('--json-output', default='results/ed_mcmc_aggregate_metrics.json', help='Output JSON file')
    
    args = parser.parse_args()
    
    print(f"Loading results from: {args.results_dir}")
    all_results = load_cat_results(args.results_dir)
    
    if not all_results:
        print("✗ No results found!")
        return
    
    print(f"  Found {len(all_results)} categories")
    
    # Aggregate metrics
    print("Computing aggregate metrics...")
    metrics, all_cosines, all_angles = aggregate_metrics(all_results)
    
    print(f"\n{'='*60}")
    print("AGGREGATE RESULTS")
    print(f"{'='*60}")
    print(f"Categories:      {metrics['n_cats']}")
    print(f"Total events:    {metrics['n_events_total']}")
    print(f"\n68th percentile cos(angle): {metrics['cosine']['p68']:.4f}")
    print(f"  → 68% within {np.degrees(np.arccos(metrics['cosine']['p68'])):.2f}° angular resolution")
    print(f"\nMean cos(angle): {metrics['cosine']['mean']:.4f}")
    print(f"Median cos(angle): {metrics['cosine']['median']:.4f}")
    
    # Save JSON
    output_json = Path(args.json_output)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(f"\n✓ Metrics saved to: {output_json}")
    
    # Generate PDF
    print("\nGenerating PDF report...")
    output_pdf = Path(args.output)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    generate_pdf_report(all_results, metrics, all_cosines, all_angles, output_pdf)


if __name__ == '__main__':
    main()
