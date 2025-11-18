#!/usr/bin/env python3
"""
Parallel SN Analysis Submission
Splits the 598 categories into batches and submits multiple GPU jobs.

Features:
- Configurable batch size (default: 5 categories per job)
- Override existing files option
- Local testing mode
- Progress tracking
"""

import argparse
import json
import subprocess
from pathlib import Path
import sys
import os

# Add the project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def find_categories(cat_dir_parent):
    """Find all category directories."""
    cat_dir_parent = Path(cat_dir_parent)
    cat_dirs = sorted([d for d in cat_dir_parent.glob('cat*') if d.is_dir()])
    return [d.name for d in cat_dirs]


def check_existing_results(output_dir, cat_names, scenarios):
    """Check which categories already have results."""
    output_dir = Path(output_dir)
    existing = {}
    
    for scenario in scenarios:
        existing[scenario] = []
        scenario_dir = output_dir / scenario
        if scenario_dir.exists():
            for cat_name in cat_names:
                metrics_file = scenario_dir / cat_name / 'metrics.json'
                if metrics_file.exists():
                    existing[scenario].append(cat_name)
    
    return existing


def create_batch_ranges(cat_names, batch_size, existing_results, override, scenarios):
    """Create category batches, excluding existing results unless override."""
    if override:
        # Use all categories
        cats_to_process = cat_names
    else:
        # Filter out categories that have ALL scenarios completed
        cats_to_process = []
        for cat_name in cat_names:
            completed_scenarios = sum(1 for scenario in scenarios 
                                    if cat_name in existing_results.get(scenario, []))
            if completed_scenarios < len(scenarios):
                cats_to_process.append(cat_name)
    
    # Split into batches
    batches = []
    for i in range(0, len(cats_to_process), batch_size):
        batch = cats_to_process[i:i + batch_size]
        batches.append(batch)
    
    return batches, cats_to_process


def create_condor_submit_file(batches, args, template_dir):
    """Create a single condor submit file for all batches."""
    template_dir = Path(template_dir)
    template_dir.mkdir(parents=True, exist_ok=True)
    
    submit_file = template_dir / 'submit_parallel_sn_analysis.sub'
    wrapper_file = template_dir / 'wrapper_parallel_sn_analysis.sh'
    
    wrapper_content = f"""#!/bin/bash
# Wrapper for SN analysis - takes batch_id as argument

BATCH_ID=$1

set -e

echo "=========================================="
echo "SN Analysis Batch $BATCH_ID"
echo "=========================================="
echo "Job start: $(date)"
echo "Hostname: $(hostname)"

# Setup LCG environment
echo "Setting up LCG environment..."
source /cvmfs/sft.cern.ch/lcg/views/LCG_106a_cuda/x86_64-el9-gcc11-opt/setup.sh

# Navigate to pipeline directory
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

# Define category batches
case $BATCH_ID in"""

    # Add case statements for each batch
    for i, batch in enumerate(batches):
        cat_range_str = ','.join(batch)
        wrapper_content += f"""
  {i})
    CAT_RANGE="{cat_range_str}"
    echo "Processing batch {i}: $CAT_RANGE"
    ;;"""
    
    wrapper_content += f"""
  *)
    echo "Unknown batch ID: $BATCH_ID"
    exit 1
    ;;
esac

# Run the systematic analysis for this batch
echo "Starting batch analysis..."
python3 scripts/run_systematic_sn_analysis.py \\
  --cat-dir-parent {args.cat_dir_parent} \\
  --energy-cosine-pdf {args.energy_cosine_pdf} \\
  --output-dir {args.output_dir} \\
  --n-es {args.n_es} \\
  --n-cc {args.n_cc} \\
  --run-all \\
  --ed-model {args.ed_model} \\
  --mt-model {args.mt_model} \\
  --ct-model {args.ct_model} \\
  --cat-range "$CAT_RANGE"

echo "Batch $BATCH_ID completed: $(date)"
"""
    
    # Write wrapper script
    with open(wrapper_file, 'w') as f:
        f.write(wrapper_content)
    
    wrapper_file.chmod(0o755)
    
    # Create submit file with queue for all batches
    submit_content = f"""# HTCondor submit file for SN analysis - all batches

executable            = {wrapper_file}
arguments             = $(Process)

output                = {template_dir}/logs/batch_$(Process)_$(ClusterId).out
error                 = {template_dir}/logs/batch_$(Process)_$(ClusterId).err
log                   = {template_dir}/logs/batch_$(Process)_$(ClusterId).log

# GPU resources
request_gpus          = 1
request_memory        = 8GB

+JobFlavour           = "longlunch"
environment           = "LCG_VIEW=/cvmfs/sft.cern.ch/lcg/views/LCG_106a_cuda/x86_64-el9-gcc11-opt"

# No file transfer needed
should_transfer_files = NO

# Notification
notify_user           = evilla@cern.ch
notification          = Error

queue {len(batches)}
"""
    
    with open(submit_file, 'w') as f:
        f.write(submit_content)
    
    return submit_file, wrapper_file


def test_local_batch(cat_batch, args):
    """Test a batch locally (first category only, best-case scenario only)."""
    print(f"Testing batch locally with category: {cat_batch[0]}")
    
    # Test command - just best case scenario with minimal samples
    cmd = [
        'python3', 'scripts/run_systematic_sn_analysis.py',
        '--cat-dir-parent', args.cat_dir_parent,
        '--energy-cosine-pdf', args.energy_cosine_pdf,
        '--output-dir', f"{args.output_dir}_test",
        '--n-es', '1',  # Minimal for testing
        '--n-cc', '1',  # Minimal for testing
        '--run-best-case',
        '--cat-range', cat_batch[0]  # Just first category
    ]
    
    print(f"Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)  # 10 min timeout
        if result.returncode == 0:
            print("✓ Local test successful")
            return True
        else:
            print(f"✗ Local test failed:")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("✗ Local test timed out (>10 minutes)")
        return False
    except Exception as e:
        print(f"✗ Local test error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Submit parallel SN analysis jobs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test locally first
  python submit_parallel_sn_analysis.py --test-local --batch-size 3

  # Submit all batches (no override)
  python submit_parallel_sn_analysis.py --submit

  # Override existing files and submit
  python submit_parallel_sn_analysis.py --submit --override

  # Just create submit files, don't submit
  python submit_parallel_sn_analysis.py --create-only
        """
    )
    
    # Input/output
    parser.add_argument('--cat-dir-parent', default='/eos/project-e/ep-nu/public/sn-pointing',
                       help='Parent directory containing all cat directories')
    parser.add_argument('--energy-cosine-pdf', 
                       default='/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/_archive_superseded/three_plane_three_plane_v18_200k_aug_20251112_114654/cosine_energy_pdf.npz',
                       help='Path to energy-cosine PDF')
    parser.add_argument('--output-dir', default='results/parallel_598_cats',
                       help='Output directory for results')
    
    # Model paths
    parser.add_argument('--ed-model',
                       default='/eos/user/e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_v14_10k_hyperopt_20251111_175141/checkpoints/model_epoch_62_val_loss_1.1463.keras',
                       help='ED model path')
    parser.add_argument('--mt-model',
                       default='/eos/user/e/evilla/dune/sn-tps/neural_networks/mt_identifier/v26_200k/mt_fixed_20251117_150514/model_best.keras',
                       help='MT model path')
    parser.add_argument('--ct-model',
                       default='/eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras',
                       help='CT model path')
    
    # Analysis parameters
    parser.add_argument('--n-es', type=int, default=8, help='Number of ES samples')
    parser.add_argument('--n-cc', type=int, default=80, help='Number of CC samples')
    parser.add_argument('--batch-size', type=int, default=5, help='Categories per batch')
    
    # Execution modes
    parser.add_argument('--test-local', action='store_true', help='Test first batch locally')
    parser.add_argument('--create-only', action='store_true', help='Create submit files only')
    parser.add_argument('--submit', action='store_true', help='Create and submit jobs')
    parser.add_argument('--override', action='store_true', help='Override existing results')
    
    # Working directory
    parser.add_argument('--work-dir', default='condor/parallel_jobs', help='Directory for submit files')
    
    args = parser.parse_args()
    
    # Check that we have an action
    if not any([args.test_local, args.create_only, args.submit]):
        parser.error("Must specify one of: --test-local, --create-only, --submit")
    
    # Find categories
    print("Finding categories...")
    cat_names = find_categories(args.cat_dir_parent)
    print(f"Found {len(cat_names)} categories: {cat_names[:5]}...{cat_names[-5:]}")
    
    scenarios = ['best_case', 'ed_network', 'full_pipeline']
    
    # Check existing results
    print("Checking existing results...")
    existing_results = check_existing_results(args.output_dir, cat_names, scenarios)
    for scenario, existing_cats in existing_results.items():
        print(f"  {scenario}: {len(existing_cats)} categories completed")
    
    # Create batches
    batches, cats_to_process = create_batch_ranges(
        cat_names, args.batch_size, existing_results, args.override, scenarios
    )
    
    print(f"\\nProcessing {len(cats_to_process)} categories in {len(batches)} batches")
    if not args.override:
        skipped = len(cat_names) - len(cats_to_process)
        print(f"Skipping {skipped} categories with existing results")
    
    if len(batches) == 0:
        print("No work to do!")
        return
    
    # Test mode
    if args.test_local:
        print("\\n=== LOCAL TEST ===")
        success = test_local_batch(batches[0], args)
        if success:
            print("Local test passed! Ready for submission.")
        else:
            print("Local test failed. Fix issues before submitting.")
        return
    
    # Create submit files
    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / 'logs').mkdir(exist_ok=True)
    
    print(f"\\nCreating submit file for {len(batches)} batches...")
    submit_file, wrapper_file = create_condor_submit_file(batches, args, work_dir)
    print(f"  Submit file: {submit_file.name}")
    print(f"  Wrapper script: {wrapper_file.name}")
    print(f"  Will queue {len(batches)} jobs")
    
    # Submit if requested
    if args.submit:
        print(f"\\nSubmitting {len(batches)} jobs...")
        
        try:
            result = subprocess.run(['condor_submit', str(submit_file)], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                # Extract cluster ID
                for line in result.stdout.split('\\n'):
                    if 'submitted to cluster' in line:
                        cluster_id = line.split()[-1].rstrip('.')
                        break
                print(f"  ✓ {len(batches)} jobs submitted to cluster {cluster_id}")
                print("Monitor with:")
                print(f"    condor_q {cluster_id}")
                print(f"    tail -f {work_dir}/logs/batch_*_{cluster_id}.out")
            else:
                print(f"  ✗ Failed to submit jobs")
                print(f"    Error: {result.stderr}")
        except Exception as e:
            print(f"  ✗ Error submitting jobs: {e}")
    
    elif args.create_only:
        print("\\nSubmit file created. Submit manually with:")
        print(f"  condor_submit {submit_file}")
        print(f"  This will queue {len(batches)} jobs in a single cluster")


if __name__ == '__main__':
    main()