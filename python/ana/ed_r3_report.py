#!/usr/bin/env python3
"""Merge the ed_r3_eval chunks and print the variant tables (per era and combined)."""
import argparse
import glob
import json
from pathlib import Path

import numpy as np

ERAS = {"1-399 (old era)": (1, 399), "623-672 (dev)": (623, 672),
        "673-900 (table slice)": (673, 900), "901-1224 (new era)": (901, 1224)}


def theta68(c):
    return float(np.degrees(np.arccos(np.clip(np.quantile(np.asarray(c), 0.32), -1.0, 1.0))))


def merge(pattern):
    cats, cols = [], {}
    for f in sorted(glob.glob(pattern)):
        z = np.load(f, allow_pickle=True)
        cats.extend(list(z["cats"]))
        for k in z.files:
            if k.startswith(("cos_", "q68_")) or k in ("nsel", "ref_cos", "ref_nsel", "ref_q68"):
                cols.setdefault(k, []).extend(list(z[k]))
    cats = np.asarray(cats)
    cols = {k: np.asarray(v) for k, v in cols.items()}
    order = np.argsort(cats)
    return cats[order], {k: v[order] for k, v in cols.items()}


def block(cats, cols, tags, ref_tag, title, names):
    m_all = np.ones(len(cats), bool)
    rng = np.random.RandomState(23)
    print(f"\n### {title}")
    print(f"| selection | Ncats | " + " | ".join(names[t] for t in tags) + " |")
    print("|---|---|" + "---|" * len(tags))
    for label, mask in [("ALL", m_all)] + [(e, (cats >= lo) & (cats <= hi)) for e, (lo, hi) in ERAS.items()]:
        if mask.sum() == 0:
            continue
        cells = [f"{theta68(cols['cos_' + t][mask]):.2f}" for t in tags]
        print(f"| {label} | {int(mask.sum())} | " + " | ".join(cells) + " |")
    print(f"\n| selection | Ncats | " + " | ".join(f"{names[t]} d vs {ref_tag} [68%]"
                                                   for t in tags if t != ref_tag) + " |")
    print("|---|---|" + "---|" * (len(tags) - 1))
    for label, mask in [("ALL", m_all)] + [(e, (cats >= lo) & (cats <= hi)) for e, (lo, hi) in ERAS.items()]:
        if mask.sum() == 0:
            continue
        a = cols["cos_" + ref_tag][mask]
        cells = []
        for t in tags:
            if t == ref_tag:
                continue
            b = cols["cos_" + t][mask]
            d = theta68(b) - theta68(a)
            bs = [theta68(b[i]) - theta68(a[i])
                  for i in (rng.randint(0, len(a), len(a)) for _ in range(2000))]
            cells.append(f"{d:+.2f} [{np.percentile(bs, 16):+.2f}, {np.percentile(bs, 84):+.2f}]")
        print(f"| {label} | {int(mask.sum())} | " + " | ".join(cells) + " |")
    print(f"\n| table | theta68 | median | frac>30 | coverage | mean n_sel | gate max\\|cos-ref\\| |")
    print("|---|---|---|---|---|---|---|")
    out = {}
    for t in tags:
        c = cols["cos_" + t]
        th = np.degrees(np.arccos(np.clip(c, -1, 1)))
        gate = float(np.nanmax(np.abs(c - cols["ref_cos"])))
        out[t] = {"theta68": theta68(c), "median": float(np.median(th)),
                  "frac_gt_30": float(np.mean(th > 30)),
                  "coverage": float(theta68(c) / np.median(cols["q68_" + t])),
                  "mean_n_sel": float(np.mean(cols["nsel"])), "gate_max_abs_diff": gate}
        o = out[t]
        print(f"| {names[t]} | {o['theta68']:.2f} | {o['median']:.2f} | {o['frac_gt_30']:.2f} | "
              f"{o['coverage']:.2f} | {o['mean_n_sel']:.0f} | {gate:.1e} |")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out-json", default=None)
    args = ap.parse_args()
    summary = {}

    s3names = {"T0": "T0 deployed v58 table", "TG": "TG r3 mixture (v63-ES, global f)",
               "TSg": "TSg mixture (pdf_ES,sel, global f)", "TSfE": "TSfE mixture (pdf_ES,sel, f(E))"}
    cats, cols = merge(f"{args.dir}/s3_*.npz")
    if len(cats):
        summary["scenario_3"] = block(cats, cols, ["T0", "TG", "TSg", "TSfE"], "TG",
                                      "SCENARIO 3 (full pipeline): theta68 [deg]", s3names)
        summary["scenario_3_ncats"] = int(len(cats))

    s1names = {"T0": "T0 deployed v58 table", "Tv63": "Tv63 v63 resolution table (r3 default)",
               "Tkin": "Tkin kinematic table"}
    cats, cols = merge(f"{args.dir}/s1_*.npz")
    if len(cats):
        summary["scenario_1"] = block(cats, cols, ["T0", "Tv63", "Tkin"], "Tv63",
                                      "SCENARIO 1 (best case, TRUE directions): theta68 [deg]", s1names)
        summary["scenario_1_ncats"] = int(len(cats))

    if args.out_json:
        Path(args.out_json).write_text(json.dumps(summary, indent=2))
        print(f"\nwrote {args.out_json}")


if __name__ == "__main__":
    main()
