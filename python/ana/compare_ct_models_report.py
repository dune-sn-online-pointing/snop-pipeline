#!/usr/bin/env python3
"""
Compare two CT-model scenario campaigns cat-by-cat (paired bursts).

Reads scenario_cos_theta_report.json from two campaign trees (e.g. the v52
production campaign and a v80 rerun) for the cats present in BOTH, and
compares the CT-dependent scenarios: pointing resolution (q68_theta_deg),
in-pipeline CT accuracy, and selection counts. Writes a PDF + JSON summary.

Usage:
    python3 python/ana/compare_ct_models_report.py \
        --baseline /eos/user/e/evilla/dune/sn-tps/condor_scenarios_v4 \
        --candidate /eos/user/e/evilla/dune/sn-tps/condor_scenarios_v80ct \
        --baseline-label v52 --candidate-label v80 \
        -o /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_v52_vs_v80_pipeline_comparison.pdf
"""

import os
import json
import glob
import argparse

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

SCENARIOS = ['scenario_3_full_pipeline', 'scenario_4_weighted_ct']
METRICS = ['q68_theta_deg', 'ct_accuracy', 'n_selected', 'cos_to_truth']


def load_campaign(root):
    """Return {cat: {scenario: {metric: value}}}."""
    out = {}
    for rep in sorted(glob.glob(os.path.join(root, 'cat*', 'scenario_cos_theta_report.json'))):
        cat = os.path.basename(os.path.dirname(rep))
        try:
            with open(rep) as f:
                data = json.load(f)
        except Exception:
            continue
        per_scen = {}
        for s in data.get('scenarios', []):
            if s.get('scenario') in SCENARIOS:
                per_scen[s['scenario']] = {m: s.get(m) for m in METRICS}
        if per_scen:
            out[cat] = per_scen
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--baseline', required=True)
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--baseline-label', default='baseline')
    ap.add_argument('--candidate-label', default='candidate')
    ap.add_argument('-o', '--output', required=True)
    args = ap.parse_args()

    base = load_campaign(args.baseline)
    cand = load_campaign(args.candidate)
    common = sorted(set(base) & set(cand))
    print(f'{args.baseline_label}: {len(base)} cats | {args.candidate_label}: '
          f'{len(cand)} cats | paired: {len(common)}')
    if not common:
        raise SystemExit('No overlapping cats with reports yet.')

    summary = {'n_paired_cats': len(common), 'scenarios': {}}

    with PdfPages(args.output) as pdf:
        for scen in SCENARIOS:
            vals = {m: {'b': [], 'c': []} for m in METRICS}
            for cat in common:
                sb = base[cat].get(scen)
                sc = cand[cat].get(scen)
                if not sb or not sc:
                    continue
                for m in METRICS:
                    if sb.get(m) is not None and sc.get(m) is not None:
                        vals[m]['b'].append(float(sb[m]))
                        vals[m]['c'].append(float(sc[m]))

            q68_b = np.array(vals['q68_theta_deg']['b'])
            q68_c = np.array(vals['q68_theta_deg']['c'])
            acc_b = np.array(vals['ct_accuracy']['b'])
            acc_c = np.array(vals['ct_accuracy']['c'])
            dq = q68_c - q68_b

            scen_summary = {
                'n_pairs': int(len(q68_b)),
                'q68_median': {args.baseline_label: float(np.median(q68_b)),
                               args.candidate_label: float(np.median(q68_c))},
                'q68_mean': {args.baseline_label: float(np.mean(q68_b)),
                             args.candidate_label: float(np.mean(q68_c))},
                'q68_paired_diff_median': float(np.median(dq)),
                'frac_cats_improved': float(np.mean(dq < 0)),
                'ct_accuracy_mean': {args.baseline_label: float(np.mean(acc_b)),
                                     args.candidate_label: float(np.mean(acc_c))},
                'n_selected_mean': {args.baseline_label: float(np.mean(vals['n_selected']['b'])),
                                    args.candidate_label: float(np.mean(vals['n_selected']['c']))},
            }
            summary['scenarios'][scen] = scen_summary
            print(f'\n== {scen} ({scen_summary["n_pairs"]} paired cats) ==')
            print(f'  q68 median: {args.baseline_label}={scen_summary["q68_median"][args.baseline_label]:.1f}° '
                  f'{args.candidate_label}={scen_summary["q68_median"][args.candidate_label]:.1f}° '
                  f'(paired diff median {scen_summary["q68_paired_diff_median"]:+.1f}°, '
                  f'{100*scen_summary["frac_cats_improved"]:.0f}% cats improved)')
            print(f'  CT acc mean: {args.baseline_label}={scen_summary["ct_accuracy_mean"][args.baseline_label]:.3f} '
                  f'{args.candidate_label}={scen_summary["ct_accuracy_mean"][args.candidate_label]:.3f}')

            fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
            ax = axes[0, 0]
            bins = np.linspace(0, max(q68_b.max(), q68_c.max()) * 1.05, 30)
            ax.hist(q68_b, bins=bins, alpha=0.55, label=args.baseline_label)
            ax.hist(q68_c, bins=bins, alpha=0.55, label=args.candidate_label)
            ax.set_xlabel('q68 theta [deg]'); ax.set_ylabel('cats'); ax.legend()
            ax.set_title('Pointing resolution per burst')

            ax = axes[0, 1]
            lim = max(q68_b.max(), q68_c.max()) * 1.05
            ax.plot([0, lim], [0, lim], 'k--', lw=1)
            ax.scatter(q68_b, q68_c, s=12, alpha=0.6)
            ax.set_xlabel(f'q68 {args.baseline_label} [deg]')
            ax.set_ylabel(f'q68 {args.candidate_label} [deg]')
            ax.set_title(f'Paired per-cat (below diagonal = {args.candidate_label} better)')

            ax = axes[1, 0]
            ax.hist(dq, bins=30, color='#2266aa', alpha=0.8)
            ax.axvline(0, color='k', lw=1)
            ax.axvline(np.median(dq), color='r', lw=1.5,
                       label=f'median {np.median(dq):+.1f}°')
            ax.set_xlabel(f'q68({args.candidate_label}) - q68({args.baseline_label}) [deg]')
            ax.set_ylabel('cats'); ax.legend()
            ax.set_title('Paired difference (negative = improvement)')

            ax = axes[1, 1]
            ax.hist(acc_b, bins=25, alpha=0.55, label=args.baseline_label)
            ax.hist(acc_c, bins=25, alpha=0.55, label=args.candidate_label)
            ax.set_xlabel('in-pipeline CT accuracy'); ax.set_ylabel('cats'); ax.legend()
            ax.set_title('CT accuracy on realistic (CC-dominated) mix')

            fig.suptitle(f'{scen}: {args.baseline_label} vs {args.candidate_label} '
                         f'({scen_summary["n_pairs"]} paired cats)', fontsize=13, weight='bold')
            fig.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)

    json_out = os.path.splitext(args.output)[0] + '.json'
    with open(json_out, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f'\nSaved {args.output} and {json_out}')


if __name__ == '__main__':
    main()
