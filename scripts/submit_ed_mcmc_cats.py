#!/usr/bin/env python3
"""
Submit ED+MCMC jobs for multiple categories via condor.
"""

import argparse
import subprocess
import time
from pathlib import Path


def submit_condor_job(cat_name, cat_dir, ed_model, pdf_file, output_dir):
    """Submit a single condor job for one category."""
    
    # Create condor submit file
    submit_content = f"""
executable = /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline/condor/run_ed_mcmc_wrapper.sh
arguments = {cat_dir} {cat_name} {ed_model} {pdf_file} {output_dir}

output = {output_dir}/condor_logs/{cat_name}.out
error = {output_dir}/condor_logs/{cat_name}.err
log = {output_dir}/condor_logs/{cat_name}.log

request_gpus = 1
+GPUType = "Tesla-V100-32GB"
request_cpus = 1
request_memory = 8GB

+JobFlavour = "longlunch"

queue
"""
    
    # Create logs directory
    logs_dir = Path(output_dir) / "condor_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Write submit file
    submit_file = logs_dir / f"{cat_name}.sub"
    with open(submit_file, 'w') as f:
        f.write(submit_content)
    
    # Submit job
    result = subprocess.run(['condor_submit', str(submit_file)], 
                          capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"✗ Failed to submit {cat_name}: {result.stderr}")
        return None
    
    # Parse job ID
    for line in result.stdout.split('\n'):
        if 'submitted to cluster' in line:
            job_id = line.split()[-1].rstrip('.')
            return job_id
    
    return None


def wait_for_jobs(job_ids):
    """Wait for all condor jobs to complete."""
    print(f"\nWaiting for {len(job_ids)} jobs to complete...")
    
    while True:
        # Check job status
        result = subprocess.run(['condor_q', '-nobatch'] + job_ids,
                              capture_output=True, text=True)
        
        if result.returncode != 0:
            print("✗ Failed to query job status")
            break
        
        # Count running jobs
        lines = result.stdout.split('\n')
        running = 0
        for line in lines:
            if any(jid in line for jid in job_ids):
                running += 1
        
        if running == 0:
            print("✓ All jobs completed!")
            break
        
        print(f"  {running}/{len(job_ids)} jobs still running...")
        time.sleep(30)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cat-start', type=int, default=1, help='First category number')
    parser.add_argument('--cat-end', type=int, default=10, help='Last category number (inclusive)')
    parser.add_argument('--ed-model', required=True, help='Path to ED model')
    parser.add_argument('--energy-cosine-pdf', required=True, help='Path to energy-cosine PDF')
    parser.add_argument('--output-dir', default='results/ed_mcmc_cats', help='Output directory')
    parser.add_argument('--wait', action='store_true', help='Wait for jobs to complete')
    
    args = parser.parse_args()
    
    # Base path for categories
    base_path = Path('/eos/project-e/ep-nu/public/sn-pointing')
    
    print(f"Submitting jobs for categories {args.cat_start} to {args.cat_end}")
    
    job_ids = []
    
    for cat_num in range(args.cat_start, args.cat_end + 1):
        cat_name = f"cat{cat_num:06d}"
        cat_dir = base_path / cat_name
        
        if not cat_dir.exists():
            print(f"  Skipping {cat_name} (directory not found)")
            continue
        
        print(f"  Submitting {cat_name}...")
        job_id = submit_condor_job(cat_name, str(cat_dir), args.ed_model, 
                                   args.energy_cosine_pdf, args.output_dir)
        
        if job_id:
            print(f"    ✓ Job {job_id} submitted")
            job_ids.append(job_id)
        else:
            print(f"    ✗ Failed to submit")
    
    print(f"\n✓ Submitted {len(job_ids)} jobs")
    
    if args.wait and job_ids:
        wait_for_jobs(job_ids)


if __name__ == '__main__':
    main()
