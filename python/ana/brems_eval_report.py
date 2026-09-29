#!/usr/bin/env python3
"""Merge the brems_eval chunks and print the variant table (markdown)."""
import argparse
import glob
import json

import numpy as np

NAMES = {
    "TSg":   "TSg   mixture, global f = 0.4083 (deployed r3 choice)",
    "TSfE":  "TSfE  mixture, measured f(E)",
    "Tg08":  "Tg08  global f x 0.8 = 0.327",
    "Tg12":  "Tg12  global f x 1.2 = 0.490",
    "Tccm":  "Tccm  f(E) with the MEASURED CC density instead of flat",
    "TEpF":  "TEpF  f(E') and pdf_ES(cos|E'), E' = main + secondary MARLEY clusters",
    "TEpG":  "TEpG  global f, pdf_ES(cos|E')",
    "TTrF":  "TTrF  f(E_true) and pdf_ES(cos|E_true) (truth diagnostic)",
    "TTrG":  "TTrG  global f, pdf_ES(cos|E_true) (truth diagnostic)",
    "PctlF": "PctlF pseudo-grid control, f = f(E)",
    "PctlG": "PctlG pseudo-grid control, f = global",
    "Psc":   "Psc   pseudo-grid, f = P(ES | CT score bin)",
    "Psc2":  "Psc2  pseudo-grid, f = P(ES | E bin, CT score bin)",
}
ERAS = {"2-399": (2, 399), "901-1224": (901, 1224)}


def th68(c):
    return float(np.degrees(np.arccos(np.clip(np.quantile(c, 0.32), -1.0, 1.0))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--ref", default="TSfE")
    ap.add_argument("--out-json", default=None)
    args = ap.parse_args()
    cats, cols = [], {}
    nfile = 0
    for f in sorted(glob.glob(f"{args.dir}/s3_*.npz")):
        z = np.load(f, allow_pickle=True)
        nfile += 1
        cats.extend(list(z["cats"]))
        for k in z.files:
            if k.startswith(("cos_", "q68_")) or k in ("nsel", "gate_ok", "ref_cos", "ref_nsel"):
                cols.setdefault(k, []).extend(list(z[k]))
    cats = np.asarray(cats)
    cols = {k: np.asarray(v) for k, v in cols.items()}
    o = np.argsort(cats)
    cats = cats[o]
    cols = {k: v[o] for k, v in cols.items()}
    tags = [t for t in NAMES if f"cos_{t}" in cols]
    print(f"{nfile} chunks, {len(cats)} cats, selection gate OK on "
          f"{int(cols['gate_ok'].sum())}/{len(cats)}, {cols['nsel'].mean():.1f} events/burst\n")

    rng = np.random.RandomState(23)
    bi = [rng.randint(0, len(cats), len(cats)) for _ in range(4000)]
    ref = cols[f"cos_{args.ref}"]
    print(f"| table | theta68 | median | mean | frac>30 | coverage | dtheta68 vs {args.ref} [68%] "
          f"| dmean vs {args.ref} |")
    print("|---|---|---|---|---|---|---|---|")
    summ = {}
    for t in tags:
        c = cols[f"cos_{t}"]
        th = np.degrees(np.arccos(np.clip(c, -1, 1)))
        thr = np.degrees(np.arccos(np.clip(ref, -1, 1)))
        d = th68(c) - th68(ref)
        bs = np.array([th68(c[i]) - th68(ref[i]) for i in bi])
        dm = th.mean() - thr.mean()
        de = (th - thr).std(ddof=1) / np.sqrt(len(th))
        cov = th68(c) / np.median(cols[f"q68_{t}"])
        summ[t] = {"theta68": th68(c), "median": float(np.median(th)), "mean": float(th.mean()),
                   "frac_gt_30": float(np.mean(th > 30)), "coverage": float(cov),
                   "d_theta68": d, "d_theta68_68ci": [float(np.percentile(bs, 16)),
                                                      float(np.percentile(bs, 84))],
                   "d_mean": float(dm), "d_mean_err": float(de),
                   "per_era": {k: th68(c[(cats >= lo) & (cats <= hi)])
                               for k, (lo, hi) in ERAS.items() if ((cats >= lo) & (cats <= hi)).any()}}
        print(f"| {NAMES[t]} | {th68(c):.2f} | {np.median(th):.2f} | {th.mean():.2f} | "
              f"{np.mean(th>30):.3f} | {cov:.2f} | {d:+.2f} [{np.percentile(bs,16):+.2f},"
              f"{np.percentile(bs,84):+.2f}] | {dm:+.3f} +- {de:.3f} |")
    print(f"\n| table | " + " | ".join(ERAS) + " |")
    print("|---|" + "---|" * len(ERAS))
    for t in tags:
        print(f"| {t} | " + " | ".join(f"{summ[t]['per_era'].get(k, float('nan')):.2f}"
                                      for k in ERAS) + " |")
    if args.out_json:
        json.dump({"n_cats": int(len(cats)), "tables": summ}, open(args.out_json, "w"), indent=2)


if __name__ == "__main__":
    main()
