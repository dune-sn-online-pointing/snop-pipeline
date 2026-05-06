#!/usr/bin/env python3

import numpy as np
import sys
import os
from pathlib import Path

def analyze_matched_clusters():
    """Analyze matched clusters data for 50 cats to understand ES event counts"""

    base_dir = Path("/afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/output/condor_final_mcmc_corrected")

    cats_to_check = [f"cat{i:06d}" for i in range(1, 51)]

    results = []

    print("Analyzing matched_clusters data for 50 cats...")
    print("=" * 80)

    for cat_name in cats_to_check:
        cat_dir = base_dir / cat_name

        if not cat_dir.exists():
            continue

        # Check scenario 1 (true ES selection)
        scenario_path = cat_dir / "scenario_1_true_electron_dir"
        if not scenario_path.exists():
            continue

        # Find the pipeline run directory
        pipeline_runs = list(scenario_path.glob("pipeline_run_*"))
        if not pipeline_runs:
            continue

        pipeline_run = pipeline_runs[0]
        selected_clusters_path = pipeline_run / "selected_clusters" / "selected_samples.npz"

        if selected_clusters_path.exists():
            try:
                # Load the selected samples data
                data = np.load(selected_clusters_path)

                # Get the keys to see what's available
                keys = list(data.keys())

                # Look for ES and CC event information
                es_count = 0
                cc_count = 0
                total_clusters = 0

                if 'es_clusters' in keys:
                    es_clusters = data['es_clusters']
                    es_count = len(es_clusters) if es_clusters.size > 0 else 0

                if 'cc_clusters' in keys:
                    cc_clusters = data['cc_clusters']
                    cc_count = len(cc_clusters) if cc_clusters.size > 0 else 0

                # Also try to get cluster count from other keys
                for key in keys:
                    if 'cluster' in key.lower():
                        try:
                            cluster_data = data[key]
                            if hasattr(cluster_data, '__len__'):
                                total_clusters = max(total_clusters, len(cluster_data))
                        except:
                            pass

                results.append({
                    'cat': cat_name,
                    'es_count': es_count,
                    'cc_count': cc_count,
                    'total_clusters': total_clusters,
                    'keys': keys
                })

                print(f"{cat_name}: ES={es_count}, CC={cc_count}, Total_clusters={total_clusters}")
                if len(results) <= 5:  # Show keys for first few cats
                    print(f"  Available keys: {keys}")

            except Exception as e:
                print(f"{cat_name}: Error loading data - {e}")
        else:
            print(f"{cat_name}: No selected_samples.npz found")

    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS:")
    print("=" * 80)

    if results:
        es_counts = [r['es_count'] for r in results if r['es_count'] > 0]
        cc_counts = [r['cc_count'] for r in results if r['cc_count'] > 0]
        total_counts = [r['total_clusters'] for r in results if r['total_clusters'] > 0]

        print(f"Analyzed {len(results)} cats successfully")
        print(f"ES event statistics:")
        print(f"  Mean: {np.mean(es_counts):.1f}")
        print(f"  Median: {np.median(es_counts):.1f}")
        print(f"  Min: {np.min(es_counts)}")
        print(f"  Max: {np.max(es_counts)}")
        print(f"  Range: {np.min(es_counts)} - {np.max(es_counts)}")

        print(f"\nCC event statistics:")
        print(f"  Mean: {np.mean(cc_counts):.1f}")
        print(f"  Median: {np.median(cc_counts):.1f}")
        print(f"  Min: {np.min(cc_counts)}")
        print(f"  Max: {np.max(cc_counts)}")

        print(f"\nTotal cluster statistics:")
        print(f"  Mean: {np.mean(total_counts):.1f}")
        print(f"  Median: {np.median(total_counts):.1f}")
        print(f"  Min: {np.min(total_counts)}")
        print(f"  Max: {np.max(total_counts)}")

        # Check if any cat has >300 ES events
        high_es_cats = [r for r in results if r['es_count'] > 300]
        if high_es_cats:
            print(f"\nCats with >300 ES events:")
            for cat in high_es_cats:
                print(f"  {cat['cat']}: {cat['es_count']} ES events")
        else:
            print(f"\nNo cats found with >300 ES events!")
            print(f"Highest ES count: {max(es_counts) if es_counts else 0}")

if __name__ == "__main__":
    analyze_matched_clusters()