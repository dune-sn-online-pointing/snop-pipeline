#!/usr/bin/env python3
"""
Submit ED+MCMC jobs using TRUE main tracks (no MT identification).
Parallel processing across multiple categories via condor.
"""

import argparse
import subprocess
from pathlib import Path

CONDOR_TEMPLATE = """
executable              = {script}
arguments               = --cat-dir {cat_dir} --cat-name {cat_name} --ed-model {ed_model} --energy-cosine-pdf {pdf} --output-dir {output_dir}
output                  = {log_dir}/{cat_name}.out
error                   = {log_dir}/{cat_name}.err
log                     = {log_dir}/{cat_name}.log
request_cpus            = 1
request_memory          = 8GB
+JobFlavour             = "workday"
queue
"""

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--categories', nargs='+', required=True, help='List of category names (e.g., cat000020 cat000021)')
    parser.add_argument('--data-dir', default='/eos/home-e/evilla/DUNE/v3/data/3x1x1/simulation')
    parser.add_argument('--ed-model', default='/eos/home-e/evilla/DUNE/v3/models/ed/three_plane_three_plane_v50_100k_20251115_232348')
    parser.add_argument('--energy-cosine-pdf', default='/eos/home-e/evilla/DUNE/v3/energy-distributions/cosine_energy_pdf.npz')
    parser.add_argument('--output-dir', default='/eos/home-e/evilla/DUNE/v3/results/ed_mcmc_true_tracks')
    parser.add_argument('--log-dir', default='/afs/cern.ch/work/e/evilla/logs/ed_mcmc_true_tracks')
    
    args = parser.parse_args()
    
    script_path = Path(__file__).parent / 'run_ed_mcmc_true_tracks.py'
    script_path = script_path.resolve()
    
    log_dir = Path(args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Submitting {len(args.categories)} jobs using TRUE main tracks (no MT identifier)...")
    
    for cat_name in args.categories:
        cat_dir = f"{args.data_dir}/{cat_name}"
        
        condor_script = CONDOR_TEMPLATE.format(
            script=script_path,
            cat_dir=cat_dir,
            cat_name=cat_name,
            ed_model=args.ed_model,
            pdf=args.energy_cosine_pdf,
            output_dir=args.output_dir,
            log_dir=args.log_dir
        )
        
        submit_file = log_dir / f'{cat_name}.submit'
        with open(submit_file, 'w') as f:
            f.write(condor_script)
        
        result = subprocess.run(['condor_submit', str(submit_file)], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"  ✓ Submitted {cat_name}")
        else:
            print(f"  ✗ Failed {cat_name}: {result.stderr}")
    
    print(f"\n✓ Submitted {len(args.categories)} categories")
    print(f"  Monitor: condor_q")
    print(f"  Logs: {log_dir}")
    print(f"  Results: {output_dir}")


if __name__ == '__main__':
    main()
