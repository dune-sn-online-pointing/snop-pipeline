#!/usr/bin/env python3

import sys
import os
from pathlib import Path
import subprocess
import json

def count_root_events(root_file):
    """Count events in a ROOT file using rootls"""
    try:
        # Use rootls to get tree information
        result = subprocess.run(['rootls', '-t', str(root_file)],
                              capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            return 0

        # Parse the output to find event counts
        # rootls -t typically shows: "TTree    tree_name    title : event_count"
        for line in result.stdout.split('\n'):
            if 'TTree' in line and ':' in line:
                try:
                    # Extract number after the colon
                    event_count = int(line.split(':')[-1].strip())
                    return event_count
                except (ValueError, IndexError):
                    continue

        # Alternative: try using root-config if available
        result2 = subprocess.run(['root', '-l', '-b', '-q',
                                f'{root_file}', '-e', 'tree->GetEntries()'],
                               capture_output=True, text=True, timeout=10)

        return 0

    except Exception as e:
        return 0

def analyze_raw_matched_clusters():
    """Analyze raw matched cluster files for multiple cats"""

    base_path = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples")

    cats_to_analyze = [f"cat{i:06d}" for i in range(1, 51)]

    results = []

    print("Analyzing raw matched_clusters ROOT files for 50 cats...")
    print("=" * 80)

    for cat_name in cats_to_analyze:
        cat_path = base_path / cat_name

        if not cat_path.exists():
            continue

        # Find the matched_clusters directory
        matched_clusters_dirs = list(cat_path.glob("*matched_clusters*"))

        if not matched_clusters_dirs:
            continue

        matched_clusters_dir = matched_clusters_dirs[0]

        # Count ES and CC files
        es_files = list(matched_clusters_dir.glob("es_*.root"))
        cc_files = list(matched_clusters_dir.glob("cc_*.root"))

        es_total_events = 0
        cc_total_events = 0
        es_file_count = len(es_files)
        cc_file_count = len(cc_files)

        # Sample a few files to estimate event counts
        # (since counting all files would take too long)
        es_sample_count = 0
        cc_sample_count = 0

        for i, es_file in enumerate(es_files[:10]):  # Sample first 10 ES files
            events = count_root_events(es_file)
            es_total_events += events
            if events > 0:
                es_sample_count += 1

        for i, cc_file in enumerate(cc_files[:10]):  # Sample first 10 CC files
            events = count_root_events(cc_file)
            cc_total_events += events
            if events > 0:
                cc_sample_count += 1

        # Estimate total events (extrapolate from sample)
        if es_sample_count > 0:
            es_estimated_total = (es_total_events / min(10, len(es_files))) * len(es_files)
        else:
            es_estimated_total = 0

        if cc_sample_count > 0:
            cc_estimated_total = (cc_total_events / min(10, len(cc_files))) * len(cc_files)
        else:
            cc_estimated_total = 0

        results.append({
            'cat': cat_name,
            'es_files': es_file_count,
            'cc_files': cc_file_count,
            'es_sampled_events': es_total_events,
            'cc_sampled_events': cc_total_events,
            'es_estimated_total': int(es_estimated_total),
            'cc_estimated_total': int(cc_estimated_total),
            'es_sample_size': min(10, len(es_files)),
            'cc_sample_size': min(10, len(cc_files))
        })

        print(f"{cat_name}: ES files={es_file_count}, CC files={cc_file_count}")
        print(f"  Sampled events: ES={es_total_events} (from {min(10, len(es_files))} files), CC={cc_total_events} (from {min(10, len(cc_files))} files)")
        print(f"  Estimated total: ES≈{int(es_estimated_total)}, CC≈{int(cc_estimated_total)}")

    print("\n" + "=" * 80)
    print("SUMMARY OF RAW MATCHED CLUSTERS DATA:")
    print("=" * 80)

    if results:
        es_estimates = [r['es_estimated_total'] for r in results if r['es_estimated_total'] > 0]
        cc_estimates = [r['cc_estimated_total'] for r in results if r['cc_estimated_total'] > 0]
        es_file_counts = [r['es_files'] for r in results]
        cc_file_counts = [r['cc_files'] for r in results]

        print(f"Analyzed {len(results)} cats")
        print(f"\nES Event Estimates (after 3-plane matching):")
        if es_estimates:
            print(f"  Mean: {sum(es_estimates)/len(es_estimates):.0f}")
            print(f"  Min: {min(es_estimates)}")
            print(f"  Max: {max(es_estimates)}")
            print(f"  Cats with >350 ES events: {len([x for x in es_estimates if x > 350])}")
            print(f"  Cats with >300 ES events: {len([x for x in es_estimates if x > 300])}")
            print(f"  Cats with >200 ES events: {len([x for x in es_estimates if x > 200])}")

        print(f"\nFile counts:")
        print(f"  Mean ES files per cat: {sum(es_file_counts)/len(es_file_counts):.1f}")
        print(f"  Mean CC files per cat: {sum(cc_file_counts)/len(cc_file_counts):.1f}")

        # Show some high-event cats
        high_es_cats = [r for r in results if r['es_estimated_total'] > 300]
        if high_es_cats:
            print(f"\nCats with >300 estimated ES events:")
            for cat in high_es_cats[:10]:
                print(f"  {cat['cat']}: ~{cat['es_estimated_total']} ES events")

        # Save detailed results
        with open('raw_cluster_analysis.json', 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nDetailed results saved to: raw_cluster_analysis.json")

    else:
        print("No data found!")

if __name__ == "__main__":
    analyze_raw_matched_clusters()