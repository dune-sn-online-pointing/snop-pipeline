#!/usr/bin/env python3

import sys
import os
from pathlib import Path

def analyze_raw_cluster_files():
    """Analyze raw matched cluster files by size and count for multiple cats"""

    base_path = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples")

    cats_to_analyze = [f"cat{i:06d}" for i in range(1, 51)]

    results = []

    print("Analyzing raw matched_clusters files for 50 cats...")
    print("=" * 80)

    for cat_name in cats_to_analyze:
        cat_path = base_path / cat_name

        if not cat_path.exists():
            print(f"{cat_name}: Directory not found")
            continue

        # Find the matched_clusters directory
        matched_clusters_dirs = list(cat_path.glob("*matched_clusters*"))

        if not matched_clusters_dirs:
            print(f"{cat_name}: No matched_clusters directory found")
            continue

        matched_clusters_dir = matched_clusters_dirs[0]

        # Count ES and CC files
        es_files = list(matched_clusters_dir.glob("es_*.root"))
        cc_files = list(matched_clusters_dir.glob("cc_*.root"))

        # Analyze file sizes (as proxy for event counts)
        es_sizes = []
        cc_sizes = []
        es_substantial_files = 0  # Files > 100KB (likely have events)
        cc_substantial_files = 0

        for es_file in es_files:
            try:
                size = es_file.stat().st_size
                es_sizes.append(size)
                if size > 100000:  # > 100KB
                    es_substantial_files += 1
            except:
                pass

        for cc_file in cc_files:
            try:
                size = cc_file.stat().st_size
                cc_sizes.append(size)
                if size > 100000:  # > 100KB
                    cc_substantial_files += 1
            except:
                pass

        # Estimate based on file sizes
        # Roughly: 300KB file ≈ 100-150 events, 20KB file ≈ 0-5 events
        es_estimated_events = 0
        cc_estimated_events = 0

        for size in es_sizes:
            if size > 100000:  # Substantial file
                es_estimated_events += int(size / 2000)  # ~2KB per event estimate
            elif size > 20000:  # Medium file
                es_estimated_events += int(size / 4000)  # Lower density

        for size in cc_sizes:
            if size > 100000:  # Substantial file
                cc_estimated_events += int(size / 2000)  # ~2KB per event estimate
            elif size > 20000:  # Medium file
                cc_estimated_events += int(size / 4000)

        results.append({
            'cat': cat_name,
            'es_files': len(es_files),
            'cc_files': len(cc_files),
            'es_substantial_files': es_substantial_files,
            'cc_substantial_files': cc_substantial_files,
            'es_total_size': sum(es_sizes),
            'cc_total_size': sum(cc_sizes),
            'es_estimated_events': es_estimated_events,
            'cc_estimated_events': cc_estimated_events
        })

        print(f"{cat_name}: ES={len(es_files)} files ({es_substantial_files} substantial), CC={len(cc_files)} files ({cc_substantial_files} substantial)")
        print(f"  Total sizes: ES={sum(es_sizes)/1024:.1f}KB, CC={sum(cc_sizes)/1024:.1f}KB")
        print(f"  Estimated events: ES≈{es_estimated_events}, CC≈{cc_estimated_events}")

    print("\n" + "=" * 80)
    print("SUMMARY OF RAW MATCHED CLUSTERS DATA:")
    print("=" * 80)

    if results:
        es_estimates = [r['es_estimated_events'] for r in results if r['es_estimated_events'] > 0]
        cc_estimates = [r['cc_estimated_events'] for r in results if r['cc_estimated_events'] > 0]
        es_file_counts = [r['es_files'] for r in results]
        es_substantial_counts = [r['es_substantial_files'] for r in results]

        print(f"Analyzed {len(results)} cats")
        print(f"\nES Event Estimates (raw matched clusters):")
        if es_estimates:
            import statistics
            print(f"  Mean: {statistics.mean(es_estimates):.0f}")
            print(f"  Median: {statistics.median(es_estimates):.0f}")
            print(f"  Min: {min(es_estimates)}")
            print(f"  Max: {max(es_estimates)}")
            print(f"  Cats with >350 ES events: {len([x for x in es_estimates if x > 350])}")
            print(f"  Cats with >300 ES events: {len([x for x in es_estimates if x > 300])}")
            print(f"  Cats with >200 ES events: {len([x for x in es_estimates if x > 200])}")
            print(f"  Cats with >100 ES events: {len([x for x in es_estimates if x > 100])}")

        print(f"\nFile statistics:")
        if es_file_counts:
            print(f"  Mean ES files per cat: {statistics.mean(es_file_counts):.1f}")
            print(f"  Mean substantial ES files per cat: {statistics.mean(es_substantial_counts):.1f}")

        # Show high-event cats
        high_es_cats = sorted([r for r in results if r['es_estimated_events'] > 300],
                             key=lambda x: x['es_estimated_events'], reverse=True)
        if high_es_cats:
            print(f"\nTop cats with >300 estimated ES events:")
            for cat in high_es_cats[:15]:
                print(f"  {cat['cat']}: ~{cat['es_estimated_events']} ES events ({cat['es_substantial_files']} substantial files)")
        else:
            print(f"\nNo cats found with >300 ES events!")
            if es_estimates:
                print(f"Highest ES estimate: {max(es_estimates)} events")

        # Show the distribution
        if es_estimates:
            bins = [0, 50, 100, 200, 300, 500, 1000, 10000]
            print(f"\nES Event Distribution:")
            for i in range(len(bins)-1):
                count = len([x for x in es_estimates if bins[i] <= x < bins[i+1]])
                print(f"  {bins[i]}-{bins[i+1]}: {count} cats")

    else:
        print("No data found!")

if __name__ == "__main__":
    analyze_raw_cluster_files()