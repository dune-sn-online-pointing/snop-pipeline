#!/usr/bin/env python3
"""
Systematic SN Analysis Wrapper
Runs all three scenarios across all categories with 325 ES + 3300 CC samples.

Scenarios:
1. Best case: True electron directions
2. ED network: Perfect channel tagging
3. Full pipeline: MT → CT → ED (realistic)

Tracks skipped categories and aggregates results.
"""

import argparse
import subprocess
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from python.sn_sample_utils import validate_cat_samples


def find_categories(cat_dir_parent):
    """Find all category directories."""
    cat_dir_parent = Path(cat_dir_parent)
    cat_dirs = sorted([d for d in cat_dir_parent.glob('cat*') if d.is_dir()])
    return cat_dirs


def run_scenario(scenario_name, script_path, cat_dir, cat_name, args, extra_args=None):
    """
    Run one scenario for one category.
    
    Returns:
        bool: True if successful, False if failed
    """
    cmd = [
        'python3', str(script_path),
        '--cat-dir', str(cat_dir),
        '--cat-name', cat_name,
        '--energy-cosine-pdf', args.energy_cosine_pdf,
        '--output-dir', args.output_dir,
        '--n-es', str(args.n_es),
        '--n-cc', str(args.n_cc),
        '--seed', str(args.seed),
    ]
    
    if extra_args:
        cmd.extend(extra_args)
    
    print(f"\nRunning {scenario_name} for {cat_name}...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: {scenario_name} failed for {cat_name}")
        print(f"Return code: {e.returncode}")
        return False


def main():
    parser = argparse.ArgumentParser(description='Run systematic SN analysis across all categories')
    parser.add_argument('--cat-dir-parent', required=True, help='Parent directory containing all cat directories')
    parser.add_argument('--energy-cosine-pdf', required=True, help='Path to energy-cosine PDF .npz')
    parser.add_argument('--output-dir', required=True, help='Output directory for all results')
    parser.add_argument('--n-es', type=int, default=325, help='Number of ES samples (default: 325)')
    parser.add_argument('--n-cc', type=int, default=3300, help='Number of CC samples (default: 3300)')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    
    # Scenario selection
    parser.add_argument('--run-best-case', action='store_true', help='Run scenario 1: best case')
    parser.add_argument('--run-ed-network', action='store_true', help='Run scenario 2: ED network')
    parser.add_argument('--run-full-pipeline', action='store_true', help='Run scenario 3: full pipeline')
    parser.add_argument('--run-all', action='store_true', help='Run all scenarios')
    
    # Model paths for scenarios 2 & 3
    parser.add_argument('--ed-model', help='Path to ED model (required for scenarios 2 & 3)')
    parser.add_argument('--mt-model', help='Path to MT model (required for scenario 3)')
    parser.add_argument('--ct-model', help='Path to CT model (required for scenario 3)')
    
    # Pipeline parameters
    parser.add_argument('--mt-threshold', type=float, default=0.5, help='MT threshold (scenario 3)')
    parser.add_argument('--ct-threshold', type=float, default=0.5, help='CT threshold (scenario 3)')
    parser.add_argument('--batch-size', type=int, default=512, help='Inference batch size')
    
    # Execution control
    parser.add_argument('--max-cats', type=int, help='Maximum number of categories to process')
    parser.add_argument('--cat-range', help='Category range to process (e.g., "1-100" or "cat000001,cat000005,cat000010")')
    
    args = parser.parse_args()
    
    # Determine which scenarios to run
    run_scenarios = {
        'best_case': args.run_best_case or args.run_all,
        'ed_network': args.run_ed_network or args.run_all,
        'full_pipeline': args.run_full_pipeline or args.run_all,
    }
    
    if not any(run_scenarios.values()):
        print("ERROR: No scenarios selected. Use --run-best-case, --run-ed-network, --run-full-pipeline, or --run-all")
        return 1
    
    # Validate model paths
    if run_scenarios['ed_network'] or run_scenarios['full_pipeline']:
        if not args.ed_model:
            print("ERROR: --ed-model required for scenarios 2 and 3")
            return 1
    
    if run_scenarios['full_pipeline']:
        if not args.mt_model or not args.ct_model:
            print("ERROR: --mt-model and --ct-model required for scenario 3")
            return 1
    
    # Find script paths
    script_dir = Path(__file__).parent
    scripts = {
        'best_case': script_dir / 'run_best_case_sn_analysis.py',
        'ed_network': script_dir / 'run_ed_network_sn_analysis.py',
        'full_pipeline': script_dir / 'run_full_pipeline_sn_analysis.py',
    }
    
    # Validate scripts exist
    for scenario, script_path in scripts.items():
        if run_scenarios[scenario] and not script_path.exists():
            print(f"ERROR: Script not found: {script_path}")
            return 1
    
    # Find all categories
    print(f"\n{'='*70}")
    print("SYSTEMATIC SN ANALYSIS")
    print(f"{'='*70}\n")
    
    cat_dirs = find_categories(args.cat_dir_parent)
    print(f"Found {len(cat_dirs)} category directories in {args.cat_dir_parent}")
    
    # Apply cat range filter if specified
    if args.cat_range:
        if '-' in args.cat_range and ',' not in args.cat_range:
            # Range format: "1-100"
            start, end = map(int, args.cat_range.split('-'))
            cat_dirs = [d for d in cat_dirs if start <= int(d.name.replace('cat', '')) <= end]
            print(f"Filtered to {len(cat_dirs)} categories in range {args.cat_range}")
        else:
            # List format: "cat000001,cat000005,cat000010"
            cat_names = [name.strip() for name in args.cat_range.split(',')]
            cat_dirs = [d for d in cat_dirs if d.name in cat_names]
            print(f"Filtered to {len(cat_dirs)} specific categories: {[d.name for d in cat_dirs]}")
    
    # Apply max cats limit
    if args.max_cats:
        cat_dirs = cat_dirs[:args.max_cats]
        print(f"Limited to first {args.max_cats} categories")
    
    print(f"\nScenarios to run:")
    for scenario, enabled in run_scenarios.items():
        if enabled:
            print(f"  ✓ {scenario}")
    
    print(f"\nSample requirements: {args.n_es} ES + {args.n_cc} CC per category")
    print(f"Output directory: {args.output_dir}\n")
    
    # Create output directory
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    
    # Track results
    results_summary = {
        'total_cats': len(cat_dirs),
        'skipped_cats': [],
        'processed_cats': [],
        'failed_cats': {},
        'scenarios': list(k for k, v in run_scenarios.items() if v),
    }
    
    # Process each category
    for i, cat_dir in enumerate(cat_dirs):
        cat_name = cat_dir.name
        
        print(f"\n{'='*70}")
        print(f"CATEGORY {i+1}/{len(cat_dirs)}: {cat_name}")
        print(f"{'='*70}")
        
        # Validate samples
        is_valid, actual_es, actual_cc = validate_cat_samples(
            cat_dir, cat_name, args.n_es, args.n_cc
        )
        
        print(f"Sample validation:")
        print(f"  Required: {args.n_es} ES, {args.n_cc} CC")
        print(f"  Available: {actual_es} ES, {actual_cc} CC")
        print(f"  Status: {'PASS' if is_valid else 'FAIL'}")
        
        if not is_valid:
            print(f"SKIPPING {cat_name}: Insufficient samples")
            results_summary['skipped_cats'].append({
                'cat_name': cat_name,
                'actual_es': actual_es,
                'actual_cc': actual_cc,
            })
            continue
        
        # Run each enabled scenario
        cat_results = {'cat_name': cat_name}
        cat_failed = False
        
        if run_scenarios['best_case']:
            success = run_scenario(
                'Best Case',
                scripts['best_case'],
                cat_dir,
                cat_name,
                args
            )
            cat_results['best_case'] = 'success' if success else 'failed'
            if not success:
                cat_failed = True
                if cat_name not in results_summary['failed_cats']:
                    results_summary['failed_cats'][cat_name] = []
                results_summary['failed_cats'][cat_name].append('best_case')
        
        if run_scenarios['ed_network']:
            extra_args = [
                '--ed-model', args.ed_model,
                '--batch-size', str(args.batch_size),
            ]
            success = run_scenario(
                'ED Network',
                scripts['ed_network'],
                cat_dir,
                cat_name,
                args,
                extra_args
            )
            cat_results['ed_network'] = 'success' if success else 'failed'
            if not success:
                cat_failed = True
                if cat_name not in results_summary['failed_cats']:
                    results_summary['failed_cats'][cat_name] = []
                results_summary['failed_cats'][cat_name].append('ed_network')
        
        if run_scenarios['full_pipeline']:
            extra_args = [
                '--mt-model', args.mt_model,
                '--ct-model', args.ct_model,
                '--ed-model', args.ed_model,
                '--mt-threshold', str(args.mt_threshold),
                '--ct-threshold', str(args.ct_threshold),
                '--batch-size', str(args.batch_size),
            ]
            success = run_scenario(
                'Full Pipeline',
                scripts['full_pipeline'],
                cat_dir,
                cat_name,
                args,
                extra_args
            )
            cat_results['full_pipeline'] = 'success' if success else 'failed'
            if not success:
                cat_failed = True
                if cat_name not in results_summary['failed_cats']:
                    results_summary['failed_cats'][cat_name] = []
                results_summary['failed_cats'][cat_name].append('full_pipeline')
        
        results_summary['processed_cats'].append(cat_results)
    
    # Save summary
    summary_path = Path(args.output_dir) / 'analysis_summary.json'
    with open(summary_path, 'w') as f:
        json.dump(results_summary, f, indent=2)
    
    # Print final summary
    print(f"\n{'='*70}")
    print("SYSTEMATIC ANALYSIS COMPLETE")
    print(f"{'='*70}")
    print(f"Total categories found: {results_summary['total_cats']}")
    print(f"Categories processed: {len(results_summary['processed_cats'])}")
    print(f"Categories skipped (insufficient samples): {len(results_summary['skipped_cats'])}")
    print(f"Categories with failures: {len(results_summary['failed_cats'])}")
    
    if results_summary['skipped_cats']:
        print(f"\nSkipped categories:")
        for skip in results_summary['skipped_cats']:
            print(f"  {skip['cat_name']}: {skip['actual_es']} ES, {skip['actual_cc']} CC")
    
    if results_summary['failed_cats']:
        print(f"\nFailed scenarios:")
        for cat_name, failed_scenarios in results_summary['failed_cats'].items():
            print(f"  {cat_name}: {', '.join(failed_scenarios)}")
    
    print(f"\nSummary saved to: {summary_path}")
    print(f"Results directory: {args.output_dir}")
    print(f"{'='*70}\n")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
