#!/usr/bin/env python3
"""Merge `combo_gridfit.py` chunks and summarise the combined-likelihood study.

Produces theta68 / median / mean / frac>30 / coverage per arm, paired bootstrap intervals
against any number of reference arms, the per-era split, and the leak-test diagnostics
(the prior-only surface's own maximum relative to the true burst direction).

Usage:
  python3 python/ana/combo_report.py --results '<dir>/chunk_*.npz' --out <summary.json> \
      [--refs CUR_t080_gf_flat,REF_t050_map] [--eras 2-399,901-1224] [--label eval722]
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
    if c.size == 0:
        return float("nan")
    return float(np.degrees(np.arccos(np.clip(np.quantile(c, 0.32), -1.0, 1.0))))


def merge(paths):
    cats, per_tag = [], {}
    meta = {}
    for p in sorted(paths):
        z = np.load(p, allow_pickle=True)
        tags = json.loads(str(z["tags"]))
        meta.update(json.loads(str(z["arms"])))
        cats.append(np.asarray(z["cats"], dtype=int))
        for t in tags:
            d = per_tag.setdefault(t, {})
            for k in ("cos", "cos_mode", "q68", "nsel", "nes", "prior_ang", "prior_span"):
                d.setdefault(k, []).append(np.asarray(z[f"{k}_{t}"], dtype=np.float64))
            d.setdefault("cats", []).append(np.asarray(z["cats"], dtype=int))
    out = {}
    for t, d in per_tag.items():
        c = np.concatenate(d["cats"])
        order = np.argsort(c)
        o = {"cats": c[order]}
        for k in ("cos", "cos_mode", "q68", "nsel", "nes", "prior_ang", "prior_span"):
            o[k] = np.concatenate(d[k])[order]
        out[t] = o
    return out, meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, help="glob of chunk npz files")
    ap.add_argument("--out", required=True)
    ap.add_argument("--refs", default="")
    ap.add_argument("--eras", default="2-399,901-1224")
    ap.add_argument("--label", default="eval")
    ap.add_argument("--burst-dirs", default=None,
                    help="per-event collect npz, to split theta68 by where the burst points "
                         "in the detector frame (the signature of the directional misspecification)")
    args = ap.parse_args()

    paths = sorted(glob.glob(args.results))
    assert paths, f"no results matched {args.results}"
    R, meta = merge(paths)
    tags = list(R)
    common = None
    for t in tags:
        s = set(R[t]["cats"][np.isfinite(R[t]["cos"])].tolist())
        common = s if common is None else (common & s)
    common = np.array(sorted(common))
    print(f"{len(paths)} chunks, {len(tags)} arms, {len(common)} cats common to all arms")

    def sub(t, key, cats=None):
        m = np.isin(R[t]["cats"], common if cats is None else cats)
        return R[t][key][m]

    refs = [r for r in args.refs.split(",") if r.strip()]
    rng = np.random.RandomState(23)
    bi = [rng.randint(0, len(common), len(common)) for _ in range(N_BOOT)]
    eras = [tuple(int(x) for x in e.split("-")) for e in args.eras.split(",")]

    summ = {"label": args.label, "n_cats": int(len(common)), "n_chunks": len(paths),
            "cats": common.tolist(), "arms": {}}
    for t in tags:
        c = sub(t, "cos")
        th = np.degrees(np.arccos(np.clip(c, -1, 1)))
        q68 = sub(t, "q68")
        ns, ne = sub(t, "nsel"), sub(t, "nes")
        pa = sub(t, "prior_ang")
        rec = {"label": meta.get(t, {}).get("label", ""),
               "spec": {k: v for k, v in meta.get(t, {}).items() if k != "label"},
               "theta68": theta68(c), "median": float(np.median(th)), "mean": float(th.mean()),
               "theta90": float(np.percentile(th, 90)), "frac_gt30": float(np.mean(th > 30)),
               "coverage": float(theta68(c) / np.median(q68)),
               "mean_nsel": float(ns.mean()), "purity": float(ne.sum() / max(ns.sum(), 1)),
               "mode_theta68": theta68(sub(t, "cos_mode")),
               "per_era_theta68": {}, "vs": {}}
        for lo, hi in eras:
            m = (common >= lo) & (common <= hi)
            rec["per_era_theta68"][f"{lo}-{hi}"] = theta68(c[m])
        if np.isfinite(pa).any():
            f = pa[np.isfinite(pa)]
            rec["prior_only"] = {"mean_angle_deg": float(f.mean()),
                                 "median_angle_deg": float(np.median(f)),
                                 "frac_lt_90": float(np.mean(f < 90)),
                                 "frac_lt_90_err": float(np.sqrt(0.25 / len(f))),
                                 "mean_span_loglike": float(np.nanmean(sub(t, "prior_span")))}
        for r in refs:
            if r not in R or r == t:
                continue
            cr = sub(r, "cos")
            thr = np.degrees(np.arccos(np.clip(cr, -1, 1)))
            d = theta68(c) - theta68(cr)
            bs = np.array([theta68(c[i]) - theta68(cr[i]) for i in bi])
            dm = float(th.mean() - thr.mean())
            de = float((th - thr).std(ddof=1) / np.sqrt(len(th)))
            dmed = float(np.median(th) - np.median(thr))
            bsm = np.array([np.median(th[i]) - np.median(thr[i]) for i in bi])
            rec["vs"][r] = {"d_theta68": d,
                            "ci68": [float(np.percentile(bs, 16)), float(np.percentile(bs, 84))],
                            "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
                            "d_mean": dm, "d_mean_err": de, "d_median": dmed,
                            "d_median_ci68": [float(np.percentile(bsm, 16)),
                                              float(np.percentile(bsm, 84))],
                            "frac_cats_improved": float(np.mean(th < thr))}
        summ["arms"][t] = rec

    order = sorted(tags, key=lambda t: summ["arms"][t]["theta68"])
    hdr = f"{'arm':26s} {'th68':>7} {'med':>7} {'mean':>7} {'>30':>6} {'cov':>5} {'nsel':>7} {'pur':>6}"
    for r in refs:
        hdr += f" {'d vs ' + r[:12]:>26}"
    print("\n" + hdr)
    for t in order:
        a = summ["arms"][t]
        line = (f"{t:26s} {a['theta68']:7.2f} {a['median']:7.2f} {a['mean']:7.2f} "
                f"{a['frac_gt30']:6.3f} {a['coverage']:5.2f} {a['mean_nsel']:7.0f} "
                f"{a['purity']:6.3f}")
        for r in refs:
            v = a["vs"].get(r)
            line += (f" {v['d_theta68']:+7.2f} [{v['ci68'][0]:+.2f},{v['ci68'][1]:+.2f}]"
                     if v else " " * 26)
        print(line)

    print("\nprior-only leak test (angle of argmax of -sum log Z_i(n) to the truth):")
    print(f"{'arm':26s} {'mean':>7} {'median':>7} {'frac<90':>9} {'span[LL]':>9}")
    for t in order:
        p = summ["arms"][t].get("prior_only")
        if p:
            print(f"{t:26s} {p['mean_angle_deg']:7.1f} {p['median_angle_deg']:7.1f} "
                  f"{p['frac_lt_90']:.3f}+-{p['frac_lt_90_err']:.3f} {p['mean_span_loglike']:9.1f}")

    print("\nper era:")
    print(f"{'arm':26s} " + " ".join(f"{lo}-{hi:>8}" for lo, hi in eras))
    for t in order:
        a = summ["arms"][t]
        print(f"{t:26s} " + " ".join(f"{a['per_era_theta68'][f'{lo}-{hi}']:13.2f}" for lo, hi in eras))

    if args.burst_dirs:
        z = np.load(args.burst_dirs, allow_pickle=True)
        A = np.asarray(z["table"], dtype=np.float64)
        cols = list(z["cols"])
        cc = A[:, cols.index("cat")].astype(int)
        b = A[:, [cols.index("bx"), cols.index("by"), cols.index("bz")]]
        bd = {}
        for k, c0 in enumerate(cc):
            if c0 not in bd:
                bd[c0] = b[k]
        B = np.array([bd[c] for c in common])
        B /= np.linalg.norm(B, axis=1, keepdims=True)
        bins = {}
        for ax, i in (("b_y", 1), ("b_z", 2)):
            a = np.abs(B[:, i])
            bins[f"|{ax}|<0.33"] = a < 0.33
            bins[f"|{ax}|0.33-0.66"] = (a >= 0.33) & (a < 0.66)
            bins[f"|{ax}|>0.66"] = a >= 0.66
        summ["burst_direction_bins"] = {k: int(v.sum()) for k, v in bins.items()}
        print("\ntheta68 by where the burst points (detector frame):")
        print(f"{'arm':26s} " + " ".join(f"{k:>16s}" for k in bins))
        for t in order:
            c = sub(t, "cos")
            row = {k: theta68(c[m]) for k, m in bins.items()}
            summ["arms"][t]["burst_dir_theta68"] = row
            print(f"{t:26s} " + " ".join(f"{row[k]:16.2f}" for k in bins))

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(summ, indent=2))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
