#!/usr/bin/env python3
"""
Monitor progress of CAT processing jobs and check for completed results
"""
import subprocess
import time
import os
from pathlib import Path
import json
from collections import defaultdict

def get_job_status(cluster_id):
    """Get status of HTCondor jobs in cluster"""
    try:
        result = subprocess.run(['condor_q', str(cluster_id), '-nobatch'],
                              capture_output=True, text=True, check=True)

        lines = result.stdout.strip().split('\n')
        total_line = [line for line in lines if 'Total for query:' in line]

        if total_line:
            # Parse: "Total for query: 125 jobs; 0 completed, 0 removed, 125 idle, 0 running, 0 held, 0 suspended"
            parts = total_line[0].split(';')[1].strip()
            status_counts = {}

            for item in parts.split(', '):
                count, status = item.strip().split(' ', 1)
                status_counts[status] = int(count)

            return status_counts
        else:
            return {}
    except subprocess.CalledProcessError:
        # Jobs might be completed and no longer in queue
        return {}

def count_completed_cats(output_base):
    """Count how many cats have completed successfully"""
    output_path = Path(output_base)
    completed = 0

    for cat_dir in output_path.glob('cat*/'):
        marker = cat_dir / 'scenario_cos_theta_report.json'
        if marker.is_file() and marker.stat().st_size > 0:
            completed += 1

    return completed

def main():
    cluster_id = 8674926
    output_base = "/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples"

    print(f"Monitoring HTCondor cluster {cluster_id}")
    print(f"Output location: {output_base}")
    print("-" * 80)

    while True:
        # Check job status
        job_status = get_job_status(cluster_id)

        # Check completed cats
        completed_cats = count_completed_cats(output_base)

        if job_status:
            completed = job_status.get('completed', 0)
            running = job_status.get('running', 0)
            idle = job_status.get('idle', 0)
            held = job_status.get('held', 0)

            print(f"{time.strftime('%H:%M:%S')} - Jobs: {running} running, {idle} idle, {completed} completed, {held} held")
        else:
            print(f"{time.strftime('%H:%M:%S')} - Jobs: All jobs finished or not found in queue")

        print(f"{time.strftime('%H:%M:%S')} - CATs completed: {completed_cats}/621")

        if not job_status or (job_status.get('running', 0) == 0 and job_status.get('idle', 0) == 0):
            print("All jobs appear to be finished!")
            break

        print("-" * 40)
        time.sleep(60)  # Check every minute

if __name__ == '__main__':
    main()