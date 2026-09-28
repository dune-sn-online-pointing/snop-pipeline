#!/usr/bin/env python3
"""
Summarise the mixture-ct dev run: compare scenarios on the SAME cats, report coverage of the
scenario-7 credible region, cross-check against a previous campaign on the same cats, and
check the ES pdf truth axis against the dev data (true-ES events: cos(reco, nu) vs cos(reco, e)).

Usage:
  python3 python/ana/mixture_dev_summary.py --input-root <dev base> [--campaign-root <ext1000>] \
      --pdf-es data/cosine_energy_pdf.npz --out-md <md> --out-json <json>
"""
import argparse
import json
from pathlib import Path

import numpy as np

_MIN_SELECTED = {"true-es": 200, "predicted-es": 100, "weighted-ct": 100, "mixture-ct": 100}
_MIN_DEFAULT = 100


def load_reports(root: Path):
    out = {}
    for cat_dir in sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("cat")):
        f = cat_dir / "scenario_cos_theta_report.json"
        if f.exists():
            with open(f) as fh:
                out[cat_dir.name] = {r["scenario"]: r for r in json.load(fh).get("scenarios", [])}
    return out


def aggregate(rows):
    th = np.array([float(r["single_pass_theta_deg"]) for r in rows])
    cos = np.array([float(r["cos_to_truth"]) for r in rows])
    q68 = np.array([float(r.get("q68_theta_deg", np.nan)) for r in rows])
    nsel = np.array([int(r["n_selected"]) for r in rows])
    ct = np.array([float(r["ct_accuracy"]) if r.get("ct_accuracy") is not None else np.nan for r in rows])
    agg = {
        "n_cats": int(len(rows)),
        "theta68_from_cos_deg": float(np.degrees(np.arccos(np.clip(np.quantile(cos, 0.32), -1, 1)))),
        "theta_median_deg": float(np.median(th)),
        "theta_mean_deg": float(np.mean(th)),
        "frac_gt_30deg": float(np.mean(th > 30)),
        "q68_posterior_median_deg": float(np.nanmedian(q68)),
        "n_selected_mean": float(np.mean(nsel)),
        "ct_accuracy_mean": float(np.nanmean(ct)) if np.any(np.isfinite(ct)) else float("nan"),
    }
    if all("truth_in_hpd68" in r for r in rows):
        agg["coverage68"] = float(np.mean([bool(r["truth_in_hpd68"]) for r in rows]))
        agg["hpd68_radius_median_deg"] = float(np.median([float(r["hpd68_radius_deg"]) for r in rows]))
        agg["map_theta_median_deg"] = float(np.median([float(r["map_theta_deg"]) for r in rows]))
        agg["pi_used_mean"] = float(np.mean([float(r["pi_used"]) for r in rows]))
        agg["sum_p_es_mean"] = float(np.mean([float(r["sum_p_es"]) for r in rows]))
        agg["n_true_es_used_mean"] = float(np.mean([float(r["n_true_es_used"]) for r in rows]))
        agg["mean_p_true_es"] = float(np.nanmean([float(r["mean_p_true_es"]) for r in rows]))
        agg["mean_p_true_cc"] = float(np.nanmean([float(r["mean_p_true_cc"]) for r in rows]))
    return agg


def table(summary, title):
    lines = [f"**{title}**", "",
             "| scenario | Ncats | theta68 (68% cont.) [deg] | median theta [deg] | mean theta | frac > 30 deg | median posterior q68 [deg] | mean n_sel | CT acc | coverage68 | median HPD68 r [deg] |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, a in summary.items():
        cov = f"{a['coverage68']:.2f}" if "coverage68" in a else "-"
        hpd = f"{a['hpd68_radius_median_deg']:.2f}" if "hpd68_radius_median_deg" in a else "-"
        ct = f"{a['ct_accuracy_mean']:.3f}" if np.isfinite(a["ct_accuracy_mean"]) else "-"
        lines.append(f"| {name} | {a['n_cats']} | {a['theta68_from_cos_deg']:.2f} | {a['theta_median_deg']:.2f} | {a['theta_mean_deg']:.2f} | "
                     f"{a['frac_gt_30deg']:.2f} | {a['q68_posterior_median_deg']:.2f} | {a['n_selected_mean']:.0f} | {ct} | {cov} | {hpd} |")
    return "\n".join(lines)


def es_axis_check(root: Path, pdf_es_path):
    """True-ES events from the kept scenario-7 outputs: mean cos per energy bin vs the ES table."""
    ref = np.load(pdf_es_path, allow_pickle=True)
    ebins = np.asarray(ref["energy_bins"], float)
    cen = np.asarray(ref["cosine_bin_centers"], float)
    pdf = np.asarray(ref["pdf_2d"], float)
    w = cen[1] - cen[0]
    table_mean = (pdf * cen[None, :]).sum(1) * w
    cos_nu, cos_e, en = [], [], []
    for cat_dir in sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("cat")):
        runs = sorted((cat_dir / "scenario_7_mixture_ct").glob("pipeline_run_*"))
        if not runs:
            continue
        f = runs[-1] / "predictions" / "mixture_events.npz"
        if not f.exists():
            continue
        d = np.load(f, allow_pickle=True)
        m = np.asarray(d["is_es_true"], bool)
        r = np.asarray(d["reco_dirs"], float)[m]
        cos_nu.append(np.sum(r * np.asarray(d["true_nu_dirs"], float)[m], 1))
        cos_e.append(np.sum(r * np.asarray(d["true_electron_dirs"], float)[m], 1))
        en.append(np.asarray(d["energy"], float)[m])
    if not en:
        return None, "no per-event outputs found"
    cos_nu, cos_e, en = map(np.concatenate, (cos_nu, cos_e, en))
    lines = ["| E bin [MeV] | N true ES (dev) | <cos(reco,nu)> dev | <cos(reco,e_true)> dev | <cos> ES table |", "|---|---|---|---|---|"]
    rows = []
    for i, (a, b) in enumerate(ebins):
        m = (en >= a) & (en < b)
        if m.sum() < 20:
            continue
        rows.append((a, b, int(m.sum()), float(cos_nu[m].mean()), float(cos_e[m].mean()), float(table_mean[i])))
        lines.append(f"| {a:.0f}-{b:.0f} | {m.sum()} | {cos_nu[m].mean():.3f} | {cos_e[m].mean():.3f} | {table_mean[i]:.3f} |")
    d_nu = np.mean([abs(r[3] - r[5]) for r in rows]); d_e = np.mean([abs(r[4] - r[5]) for r in rows])
    verdict = (f"mean |<cos> difference| vs ES table: nu-axis {d_nu:.3f}, electron-axis {d_e:.3f} -> table matches the "
               f"{'NEUTRINO' if d_nu < d_e else 'ELECTRON'} axis better (N true ES = {len(en)})")
    return {"rows": rows, "verdict": verdict}, "\n".join(lines) + "\n\n" + verdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", required=True)
    ap.add_argument("--campaign-root", default=None)
    ap.add_argument("--pdf-es", default=None)
    ap.add_argument("--scenarios", default="scenario_1_best_case,scenario_2_perfect_ct,scenario_3_full_pipeline,scenario_7_mixture_ct",
                    help="scenarios that define the common-cat comparison set (each must pass the aggregator's min-selected threshold)")
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-json", required=True)
    args = ap.parse_args()

    root = Path(args.input_root)
    reps = load_reports(root)
    names = args.scenarios.split(",")
    # common cats: all requested scenarios present and above the aggregator's min-selected threshold
    common = []
    for cat, rows in reps.items():
        ok = True
        for n in names:
            r = rows.get(n)
            if r is None or int(r["n_selected"]) < _MIN_SELECTED.get(r.get("selection_mode", ""), _MIN_DEFAULT):
                ok = False
                break
        if ok:
            common.append(cat)
    print(f"{len(reps)} cats with reports, {len(common)} cats with all scenarios above threshold")
    summary = {}
    for n in names:
        rows = [reps[c][n] for c in common]
        if rows:
            summary[rows[0].get("label", n)] = aggregate(rows)
    # every scenario on its own passing cats (same filtering as aggregate_scenario_reports.py)
    all_names = sorted({n for rows in reps.values() for n in rows})
    per_scenario = {}
    for n in all_names:
        rows = [rows_[n] for rows_ in reps.values() if n in rows_
                and int(rows_[n]["n_selected"]) >= _MIN_SELECTED.get(rows_[n].get("selection_mode", ""), _MIN_DEFAULT)]
        if rows:
            per_scenario[rows[0].get("label", n)] = aggregate(rows)
    cats_txt = f"{len(common)} ({common[0]}..{common[-1]})" if common else "0"
    md = [f"# mixture-ct dev run summary\n", f"input: `{root}`; common cats for {names}: {cats_txt}\n",
          table(summary, "Dev run, common cats (same regenerated products, same cats for every row)"),
          "", table(per_scenario, "Dev run, every scenario on its own cats passing the aggregator threshold")]
    out = {"input_root": str(root), "common_cats": common, "dev": summary, "dev_per_scenario": per_scenario}

    if args.campaign_root:
        creps = load_reports(Path(args.campaign_root))
        csum = {}
        for n in names:
            rows = [creps[c][n] for c in common if c in creps and n in creps[c]]
            if rows:
                csum[rows[0].get("label", n)] = aggregate(rows)
        md += ["", table(csum, f"Cross-check: previous campaign `{args.campaign_root}` on the same cats (different background draws / emcee)")]
        out["campaign"] = csum

    if args.pdf_es:
        res, txt = es_axis_check(root, args.pdf_es)
        md += ["", "**ES pdf truth-axis check (true-ES events of the dev run)**", "", txt]
        out["es_axis_check"] = res

    Path(args.out_md).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_md, "w") as f:
        f.write("\n".join(md) + "\n")
    with open(args.out_json, "w") as f:
        json.dump(out, f, indent=1)
    print("\n".join(md))


if __name__ == "__main__":
    main()
