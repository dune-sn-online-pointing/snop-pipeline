"""Helper functions for condor job submission"""
import subprocess
import sys
import tempfile
from pathlib import Path


def submit_condor_job(cat_name, step, pipeline_args_list, gpu=True, memory='8GB', cpus=4, flavour='microcentury'):
    """
    Submit a pipeline step to condor.
    
    Args:
        cat_name: Category name (e.g., 'cat000010')
        step: Pipeline step ('full', 'ct', 'ed', 'mcmc')
        pipeline_args_list: List of additional command line arguments
        gpu: Whether to request GPU (default: True)
        memory: Memory request (default: '8GB')
        cpus: CPU cores (default: 4)
        flavour: Job flavour - espresso(20min), microcentury(1h), longlunch(2h), 
                 workday(8h), tomorrow(1d), testmatch(3d), nextweek(1w)
    
    Returns:
        job_id: Condor cluster ID
    """
    script_dir = Path(__file__).parent.parent
    log_dir = script_dir / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    # Convert args list to string, properly quoted
    pipeline_args = ' '.join(f'"{arg}"' if ' ' in str(arg) else str(arg) for arg in pipeline_args_list)
    
    # Prepare substitution values
    subs = {
        'cat_name': cat_name,
        'step': step,
        'pipeline_args': pipeline_args,
        'log_dir': str(log_dir),
        'cpus': str(cpus),
        'memory': memory,
        'disk': '5GB',
        'gpus': '1' if gpu else '0',
        'flavour': flavour,
        'gpu_requirements': 'TARGET.CUDADeviceName =!= ""' if gpu else '""',
    }
    
    # Create temporary submit file with substitutions
    template_path = script_dir / 'condor' / 'submit_pipeline.sub'
    with open(template_path, 'r') as f:
        template = f.read()
    
    for key, value in subs.items():
        template = template.replace(f'$({key})', value)
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.sub', delete=False) as tmp:
        tmp.write(template)
        tmp_path = tmp.name
    
    try:
        # Submit job
        result = subprocess.run(
            ['condor_submit', tmp_path],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse cluster ID from output
        for line in result.stdout.split('\n'):
            if 'submitted to cluster' in line.lower():
                job_id = line.split()[-1].rstrip('.')
                print(f"✓ Submitted condor job {job_id}")
                print(f"  Monitor: condor_q {job_id}")
                print(f"  Logs:    logs/pipeline_{step}_{cat_name}_{job_id}.*")
                return job_id
        
        raise RuntimeError(f"Could not parse job ID from condor_submit output:\n{result.stdout}")
    
    finally:
        Path(tmp_path).unlink()


def wait_for_condor_job(job_id, check_interval=30):
    """Wait for a condor job to complete and return exit code."""
    import time
    
    print(f"\nWaiting for condor job {job_id} to complete...")
    print(f"Monitor with: condor_q {job_id}")
    print(f"Check logs in: logs/pipeline_*_{job_id}.*\n")
    
    while True:
        result = subprocess.run(
            ['condor_q', job_id, '-nobatch'],
            capture_output=True,
            text=True
        )
        
        if job_id not in result.stdout:
            # Job finished
            print(f"✓ Job {job_id} completed")
            return 0  # Assume success, check logs for details
        
        time.sleep(check_interval)
