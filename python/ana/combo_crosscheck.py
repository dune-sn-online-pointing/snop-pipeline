#!/usr/bin/env python3
"""Cross-check the `combo_gridfit` arms against the r3 re-scan's own per-cat fits.

Two jobs:

  1. GATE A: the arm that reproduces the r3 winner (hard CT >= 0.50, p_i = P(ES|score),
     detector-frame CC map, no ES acceptance) is compared PER CAT against the r3 study's
     `S6_t050_map`, both deterministic grid-mixture posterior means, so the agreement must
     be numerical (the only difference is that the combo path reads a float32 per-event
     cache instead of re-reading the slim tars).
  2. Grid vs emcee: the r3 `S0` gate (t = 0.80, global-f mixture table) was fitted with the
     DEPLOYED emcee sampler; the combined study uses the grid posterior mean throughout.
     Pairing S0 against the grid arm with the same selection and purity measures the
     estimator offset that has to be quoted with any deployed number.

Usage:
  python3 python/ana/combo_crosscheck.py --r3-results '<dir>/results/*.npz' \
      --combo-results '<dir>/results/E_*.npz' --pairs S6_t050_map:GATE_A_t050_map41k,S0:CUR_t080_gf_flat \
      --out <json>
"""
import argparse
import glob
import json
from pathlib import Path

import numpy as np

N_BOOT = 4000


def theta68(cos):
    c = np.asarray(cos, dtype=np.float64)
    c = c[np.isfinite(c)]
    return float(np.degrees(np.arccos(np.clip(np.quantile(c, 0.32), -1.0, 1.0))))


def load_set(pattern, prefix="cos_"):
    out = {}
    for p in sorted(glob.glob(pattern)):
        z = np.load(p, allow_pickle=True)
        tags = json.loads(str(z["tags"]))
        cats = np.asarray(z["cats"], dtype=int)
        for t in tags:
            d = out.setdefault(t, {"cats": [], "cos": [], "nsel": []})
            d["cats"].append(cats)
            d["cos"].append(np.asarray(z[f"{prefix}{t}"], dtype=np.float64))
            key = f"nsel_{t}"
            d["nsel"].append(np.asarray(z[key], dtype=np.float64) if key in z
                             else np.full(len(cats), np.nan))
    for t, d in out.items():
        c = np.concatenate(d["cats"])
        cs = np.concatenate(d["cos"])
        ns = np.concatenate(d["nsel"])
        # the r3 campaign resubmitted some chunks, so a cat can appear twice: keep the
        # first finite entry per cat
        keep, seen = [], set()
        for i in np.argsort(c, kind="stable"):
            if c[i] in seen or not np.isfinite(cs[i]):
                continue
            seen.add(c[i])
            keep.append(i)
        keep = np.array(keep, dtype=int)
        out[t] = {"cats": c[keep], "cos": cs[keep], "nsel": ns[keep]}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--r3-results", required=True)
    ap.add_argument("--combo-results", required=True)
    ap.add_argument("--pairs", required=True, help="comma list of r3tag:combotag")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    R3 = load_set(args.r3_results)
    CB = load_set(args.combo_results)
    rng = np.random.RandomState(23)
    res = {}
    for pair in args.pairs.split(","):
        a, b = pair.split(":")
        if a not in R3 or b not in CB:
            print(f"SKIP {pair}: missing ({a in R3}, {b in CB})")
            continue
        ca = set(R3[a]["cats"][np.isfinite(R3[a]["cos"])].tolist())
        cb = set(CB[b]["cats"][np.isfinite(CB[b]["cos"])].tolist())
        common = np.array(sorted(ca & cb))
        ia = np.isin(R3[a]["cats"], common)
        ib = np.isin(CB[b]["cats"], common)
        x, y = R3[a]["cos"][ia], CB[b]["cos"][ib]
        na, nb = R3[a]["nsel"][ia], CB[b]["nsel"][ib]
        d = np.abs(x - y)
        bi = [rng.randint(0, len(common), len(common)) for _ in range(N_BOOT)]
        dt = theta68(y) - theta68(x)
        bs = np.array([theta68(y[i]) - theta68(x[i]) for i in bi])
        tha = np.degrees(np.arccos(np.clip(x, -1, 1)))
        thb = np.degrees(np.arccos(np.clip(y, -1, 1)))
        rec = {"r3_tag": a, "combo_tag": b, "n_cats": int(len(common)),
               "theta68_r3": theta68(x), "theta68_combo": theta68(y),
               "d_theta68": dt,
               "ci68": [float(np.percentile(bs, 16)), float(np.percentile(bs, 84))],
               "per_cat_cos_median_abs_diff": float(np.median(d)),
               "per_cat_cos_max_abs_diff": float(np.max(d)),
               "n_bit_exact": int(np.sum(d == 0)),
               "mean_abs_dtheta_deg": float(np.mean(np.abs(thb - tha))),
               "d_mean_theta": float(thb.mean() - tha.mean()),
               "d_mean_theta_err": float((thb - tha).std(ddof=1) / np.sqrt(len(common))),
               "nsel_identical": int(np.sum(na == nb)) if np.isfinite(nb).all() else None}
        res[pair] = rec
        print(f"\n{a} (r3) vs {b} (combo), {len(common)} cats")
        print(f"  theta68  {rec['theta68_r3']:.2f} vs {rec['theta68_combo']:.2f}  "
              f"d = {dt:+.2f} [{rec['ci68'][0]:+.2f},{rec['ci68'][1]:+.2f}]")
        print(f"  per-cat |dcos|: median {rec['per_cat_cos_median_abs_diff']:.2e}, "
              f"max {rec['per_cat_cos_max_abs_diff']:.2e}, "
              f"{rec['n_bit_exact']}/{len(common)} bit-exact")
        print(f"  mean |dtheta| {rec['mean_abs_dtheta_deg']:.3f} deg, paired mean "
              f"{rec['d_mean_theta']:+.3f} +- {rec['d_mean_theta_err']:.3f} deg")
        if rec["nsel_identical"] is not None:
            print(f"  n_selected identical on {rec['nsel_identical']}/{len(common)} cats")
    Path(args.out).write_text(json.dumps(res, indent=2))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
