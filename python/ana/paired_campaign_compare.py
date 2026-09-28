#!/usr/bin/env python3
"""Paired per-cat comparison of two scenario-report campaigns on the same cats.

Usage:
  python3 python/ana/paired_campaign_compare.py --a <root A> --b <root B> \
      [--label-a old --label-b new] [--scenarios s1,s2,...] --out-md <md> [--out-json <json>]

For every scenario present in both roots it reports, on the common cats only,
theta68 (arccos of the 0.32 quantile of cos_to_truth, i.e. the 68% containment of the
single-pass reconstructed direction), the median angle, the fraction above 30 deg, the
mean number of selected events, and the paired per-cat difference (B - A) with a
bootstrap 68% interval on the theta68 difference.
"""
import argparse
import json
from pathlib import Path

import numpy as np


def load_root(root, cat_min=None, cat_max=None):
    out = {}
    for rep in sorted(Path(root).glob("cat*/scenario_cos_theta_report.json")):
        cat = rep.parent.name
        if cat_min is not None or cat_max is not None:
            try:
                n = int(cat[3:])
            except ValueError:
                continue
            if cat_min is not None and n < cat_min:
                continue
            if cat_max is not None and n > cat_max:
                continue
        try:
            r = json.loads(rep.read_text())
        except Exception:
            continue
        for s in r.get("scenarios", []):
            name = s.get("scenario")
            cos = s.get("cos_to_truth")
            if name is None or cos is None or not np.isfinite(cos):
                continue
            out.setdefault(name, {})[cat] = {
                "cos": float(cos),
                "theta": float(np.degrees(np.arccos(np.clip(cos, -1, 1)))),
                "n_selected": int(s.get("n_selected") or 0),
                "label": s.get("label", name),
            }
    return out


def theta68(cos):
    return float(np.degrees(np.arccos(np.clip(np.quantile(cos, 0.32), -1, 1))))


def summarise(rows):
    cos = np.array([r["cos"] for r in rows])
    th = np.array([r["theta"] for r in rows])
    return {
        "n_cats": int(len(rows)),
        "theta68": theta68(cos),
        "median_theta": float(np.median(th)),
        "mean_theta": float(np.mean(th)),
        "frac_gt_30": float(np.mean(th > 30)),
        "mean_n_selected": float(np.mean([r["n_selected"] for r in rows])),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--label-a", default="A")
    ap.add_argument("--label-b", default="B")
    ap.add_argument("--scenarios", default="")
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-json", default=None)
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--cat-min", type=int, default=None,
                    help="only cats with number >= this (e.g. 623 for the new era)")
    ap.add_argument("--cat-max", type=int, default=None,
                    help="only cats with number <= this (e.g. 399 for the old era)")
    args = ap.parse_args()

    A = load_root(args.a, args.cat_min, args.cat_max)
    B = load_root(args.b, args.cat_min, args.cat_max)
    names = [s for s in args.scenarios.split(",") if s] or sorted(set(A) & set(B))
    rng = np.random.default_rng(7)
    lines = [
        f"A = `{args.a}` ({args.label_a}); B = `{args.b}` ({args.label_b}); common cats only."
        + (f"  Cat range: {args.cat_min or 0}-{args.cat_max or 'inf'}."
           if (args.cat_min is not None or args.cat_max is not None) else ""),
        "",
        "| scenario | Ncats | theta68 A | theta68 B | d theta68 (B-A) [68% boot] | median A | median B | median paired d | frac>30 A | frac>30 B | mean n_sel A/B |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    out = {}
    for name in names:
        if name not in A or name not in B:
            continue
        cats = sorted(set(A[name]) & set(B[name]))
        if not cats:
            continue
        ra = [A[name][c] for c in cats]
        rb = [B[name][c] for c in cats]
        sa, sb = summarise(ra), summarise(rb)
        ca = np.array([r["cos"] for r in ra]); cb = np.array([r["cos"] for r in rb])
        d = []
        for _ in range(args.n_boot):
            idx = rng.integers(0, len(cats), len(cats))
            d.append(theta68(cb[idx]) - theta68(ca[idx]))
        lo, hi = np.quantile(d, [0.16, 0.84])
        paired = np.array([r["theta"] for r in rb]) - np.array([r["theta"] for r in ra])
        label = rb[0]["label"]
        out[name] = {"label": label, "cats": cats, "A": sa, "B": sb,
                     "d_theta68": sb["theta68"] - sa["theta68"], "d_theta68_boot68": [float(lo), float(hi)],
                     "median_paired_dtheta": float(np.median(paired))}
        lines.append(
            f"| {label} | {len(cats)} | {sa['theta68']:.2f} | {sb['theta68']:.2f} | "
            f"{sb['theta68'] - sa['theta68']:+.2f} [{lo:+.2f}, {hi:+.2f}] | {sa['median_theta']:.2f} | {sb['median_theta']:.2f} | "
            f"{np.median(paired):+.2f} | {sa['frac_gt_30']:.2f} | {sb['frac_gt_30']:.2f} | {sa['mean_n_selected']:.0f}/{sb['mean_n_selected']:.0f} |"
        )
    Path(args.out_md).write_text("\n".join(lines) + "\n")
    if args.out_json:
        Path(args.out_json).write_text(json.dumps(out, indent=1))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
