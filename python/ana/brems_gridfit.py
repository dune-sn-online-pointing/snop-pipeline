#!/usr/bin/env python3
"""Deterministic grid fits of the burst direction for arbitrary PER-EVENT purity models.

Motivation: the pipeline's emcee fit is chaotic at the 0.1-0.5 deg level per burst, which is
the same size as the effect being measured between purity models.  This script replaces the
sampler by the exact posterior mean on an equal-area sphere grid with a uniform prior -- the
quantity emcee is targeting -- so a paired comparison of purity models carries no MCMC noise.
The likelihood, the ES component and the selection are unchanged:

    logL(n) = sum_i log[ f_i * pdf_ES,sel(d_i.n | E_i) + (1 - f_i) / 2 ]

Purity models supported (all measured on the training slice 673-900):
  glob, fE, fS, fE_fS, g080, g120, perfect (oracle), fE_fS_nm (adds the truth n_marley class)
Input is the per-event table from `brems_collect.py` (any cat range).

Usage:
  python3 python/ana/brems_gridfit.py --collect <eval npz> --es-table <tbl_ereco_es.npz> \
      --slice-collect <slice npz> --grid 12000 --out <npz>
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from ana.burst_direction import (eval_pdf_rows, fibonacci_sphere_grid, load_pdf_table,
                                 pdf_rows_for_energies)

ENERGY_BINS = np.array([(2, 4), (4, 6), (6, 8), (8, 10), (10, 12), (12, 14), (14, 16),
                        (16, 18), (18, 20), (20, 22), (22, 24), (24, 26), (26, 28),
                        (28, 30), (30, 35), (35, 40), (40, 50), (50, 70)], dtype=float)
SCORE_EDGES = np.array([0.80, 0.8196, 0.8383, 0.8566, 0.8746, 1.0001])
CT_MIN, E_MIN = 0.80, 5.0


def load(path):
    z = np.load(path, allow_pickle=True)
    A = np.asarray(z["table"], dtype=np.float64)
    return {c: A[:, i] for i, c in enumerate(list(z["cols"]))}


def theta68(c):
    return float(np.degrees(np.arccos(np.clip(np.quantile(c, 0.32), -1.0, 1.0))))


def bins_of(C):
    ie = np.clip(np.digitize(C["e_reco"], ENERGY_BINS[:, 0]) - 1, 0, len(ENERGY_BINS) - 1)
    isc = np.clip(np.digitize(C["ct"], SCORE_EDGES) - 1, 0, len(SCORE_EDGES) - 2)
    return ie, isc


def fit_purity_models(S):
    """Measure the purity models on the training-slice selection S (dict of arrays)."""
    es = S["is_es"] == 1
    ie, isc = bins_of(S)
    n_s = len(SCORE_EDGES) - 1
    g = float(es.mean())
    fE = np.full(len(ENERGY_BINS), np.nan)
    for i in range(len(ENERGY_BINS)):
        m = ie == i
        if m.sum() >= 20:
            fE[i] = es[m].mean()
    ok = np.where(np.isfinite(fE))[0]
    for i in range(len(ENERGY_BINS)):
        if not np.isfinite(fE[i]):
            fE[i] = fE[ok[np.argmin(np.abs(ok - i))]]
    fS = np.array([es[isc == j].mean() for j in range(n_s)])
    f2 = np.full((len(ENERGY_BINS), n_s), np.nan)
    for i in range(len(ENERGY_BINS)):
        for j in range(n_s):
            m = (ie == i) & (isc == j)
            if m.sum() >= 30:
                f2[i, j] = es[m].mean()
    for i in range(len(ENERGY_BINS)):
        for j in range(n_s):
            if not np.isfinite(f2[i, j]):
                f2[i, j] = fS[j]
    # truth-assisted: add the MARLEY-cluster multiplicity class (1 / 2 / >=3)
    f3 = None
    if "n_marley_vol" in S and np.isfinite(S["n_marley_vol"]).mean() > 0.5:
        nm = np.clip(np.nan_to_num(S["n_marley_vol"], nan=1.0), 1, 3).astype(int) - 1
        f3 = np.full((len(ENERGY_BINS), 3), np.nan)
        for i in range(len(ENERGY_BINS)):
            for j in range(3):
                m = (ie == i) & (nm == j)
                if m.sum() >= 30:
                    f3[i, j] = es[m].mean()
        for i in range(len(ENERGY_BINS)):
            for j in range(3):
                if not np.isfinite(f3[i, j]):
                    f3[i, j] = fE[i]
    return {"glob": g, "fE": fE, "fS": fS, "f2": f2, "f3": f3}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", required=True, help="per-event table of the cats to fit")
    ap.add_argument("--slice-collect", required=True, help="training-slice table (purity models)")
    ap.add_argument("--es-table", required=True)
    ap.add_argument("--grid", type=int, default=12000)
    ap.add_argument("--fscan", default="", help="comma list of FLAT purity values to add")
    ap.add_argument("--alpha-scan", default="",
                    help="comma list of exponents applied to pdf_ES (row-renormalised) "
                         "with f = f(E); alpha > 1 sharpens the ES component")
    ap.add_argument("--eras", default="2-399,901-1224")
    ap.add_argument("--acceptance-lmax", type=int, default=2,
                    help="multipole order of the acceptance expansion (2 = dipole+quadrupole, "
                         "the closed form; higher uses the empirical multipoles "
                         "R_l(n) = (2l+1)<P_l(d.n)> of the slice's reco directions)")
    ap.add_argument("--acceptance-rotate", type=int, default=0,
                    help="NULL CONTROL: rotate the reco-direction sample by a fixed random "
                         "rotation (this seed) before measuring R_l, so the acceptance term keeps "
                         "its magnitude and statistical structure but is mis-aligned with the real "
                         "detector frame. A genuine acceptance correction must lose its gain here; "
                         "a gain that survives would mean the term is acting as an informative "
                         "prior on the trial direction.")
    ap.add_argument("--acceptance", default="none", choices=["none", "cc", "all"],
                    help="add the missing detector-acceptance normalisation -log Z(n) to the "
                         "likelihood, with the reco-direction density R(d) measured on the "
                         "training slice from the selected CC events ('cc') or from all "
                         "selected events ('all'); adds one '<model>+acc' arm per model")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    Sl = load(args.slice_collect)
    m = (Sl["ct"] >= CT_MIN) & (Sl["e_reco"] >= E_MIN)
    P = fit_purity_models({k: v[m] for k, v in Sl.items()})
    print(f"purity models from the slice: global {P['glob']:.4f}")
    print("  f(E)     ", np.round(P["fE"][1:8], 3))
    print("  f(score) ", np.round(P["fS"], 3))

    C = load(args.collect)
    sel = (C["ct"] >= CT_MIN) & (C["e_reco"] >= E_MIN)
    C = {k: v[sel] for k, v in C.items()}
    tab = load_pdf_table(args.es_table, pdf_floor=1e-4)
    cos_centers = tab["cos_centers"]
    grid = fibonacci_sphere_grid(args.grid)

    ie, isc = bins_of(C)
    has_nm = P["f3"] is not None and np.isfinite(C["n_marley_vol"]).mean() > 0.5
    nm = (np.clip(np.nan_to_num(C["n_marley_vol"], nan=1.0), 1, 3).astype(int) - 1
          if has_nm else None)
    # ---- detector-acceptance moments (see the report for the derivation)
    #   R(d) = 1 + 3 b.d + (15/2) d^T Q d,  b = <d>_R,  Q = <dd^T>_R - I/3
    #   Z_i(n) = 1 + 3 <c>_i (b.n) + (15/2) <P2(c)>_i (n^T Q n)
    acc = None
    if args.acceptance != "none":
        mm = (Sl["ct"] >= CT_MIN) & (Sl["e_reco"] >= E_MIN)
        if args.acceptance == "cc":
            mm &= Sl["is_es"] != 1
        dR = np.column_stack([Sl["dx"][mm], Sl["dy"][mm], Sl["dz"][mm]])
        if args.acceptance_rotate:
            rr = np.random.RandomState(args.acceptance_rotate)
            M, _ = np.linalg.qr(rr.normal(size=(3, 3)))
            if np.linalg.det(M) < 0:
                M[:, 0] = -M[:, 0]
            dR = dR @ M.T
            print(f"NULL CONTROL: R measured on directions rotated by seed "
                  f"{args.acceptance_rotate}")
        L = int(args.acceptance_lmax)
        # R_l(n) = (2l+1) * <P_l(d.n)> over the empirical reco-direction sample; then
        # Z_i(n) = sum_l <P_l(c)>_i R_l(n)   (verified against direct integration to 1e-6)
        Rl = np.zeros((L + 1, len(grid)))
        for j0 in range(0, len(grid), 512):
            gg = grid[j0:j0 + 512]
            x = dR @ gg.T                                     # (Nev, chunk)
            pm1 = np.ones_like(x)
            p = x.copy()
            Rl[0, j0:j0 + 512] = 1.0
            if L >= 1:
                Rl[1, j0:j0 + 512] = 3.0 * p.mean(axis=0)
            for l in range(2, L + 1):
                pm1, p = p, ((2 * l - 1) * x * p - (l - 1) * pm1) / l
                Rl[l, j0:j0 + 512] = (2 * l + 1) * p.mean(axis=0)
        print(f"acceptance R from {int(mm.sum())} slice events ({args.acceptance}), lmax={L}: "
              f"rms(R_l) = {np.round(Rl.std(axis=1), 4)}")
        acc = (Rl, L)

    models = ["glob", "fE", "fS", "fE_fS", "g080", "g120", "perfect"] + \
             (["fE_nm"] if has_nm else [])
    fscan = [float(x) for x in args.fscan.split(",") if x.strip()]
    ascan = [float(x) for x in args.alpha_scan.split(",") if x.strip()]
    models += [f"flat{v:.2f}" for v in fscan] + [f"alpha{a:.2f}" for a in ascan]
    if acc is not None:
        models = models + [m + "+acc" for m in models]

    cats = np.unique(C["cat"]).astype(int)
    res = {k: np.full(len(cats), np.nan) for k in models}
    res_mode = {k: np.full(len(cats), np.nan) for k in models}
    nsel = np.zeros(len(cats), dtype=int)
    dirs = {k: np.full((len(cats), 3), np.nan) for k in models}
    bdir = np.full((len(cats), 3), np.nan)
    for k, cat in enumerate(cats):
        s = C["cat"] == cat
        d = np.column_stack([C["dx"][s], C["dy"][s], C["dz"][s]])
        n0 = np.array([C["bx"][s][0], C["by"][s][0], C["bz"][s][0]])
        n0 = n0 / np.linalg.norm(n0)
        bdir[k] = n0
        nsel[k] = int(s.sum())
        rows = pdf_rows_for_energies(tab, C["e_reco"][s])
        cosg = np.clip(d @ grid.T, -1.0, 1.0)
        g = np.maximum(eval_pdf_rows(rows, cosg, cos_centers), 1e-10)
        for name in models:
            use_acc = name.endswith("+acc")
            name_b = name[:-4] if use_acc else name
            if name_b == "glob":
                fv = np.full(int(s.sum()), P["glob"])
            elif name_b == "g080":
                fv = np.full(int(s.sum()), P["glob"] * 0.8)
            elif name_b == "g120":
                fv = np.full(int(s.sum()), min(P["glob"] * 1.2, 0.99))
            elif name_b == "fE":
                fv = P["fE"][ie[s]]
            elif name_b == "fS":
                fv = P["fS"][isc[s]]
            elif name_b == "fE_fS":
                fv = P["f2"][ie[s], isc[s]]
            elif name_b == "fE_nm":
                fv = P["f3"][ie[s], nm[s]]
            elif name_b == "perfect":
                fv = np.where(C["is_es"][s] == 1, 1.0, 0.0)
            elif name_b.startswith("flat"):
                fv = np.full(int(s.sum()), float(name_b[4:]))
            elif name_b.startswith("alpha"):
                fv = P["fE"][ie[s]]
            gg = g
            if name_b.startswith("alpha"):
                a = float(name_b[5:])
                gg = g ** a
                gg = gg / (np.sum(rows ** a, axis=1, keepdims=True)
                           * (cos_centers[1] - cos_centers[0]))
            p = fv[:, None] * gg + (1.0 - fv)[:, None] * 0.5
            ll = np.log(np.maximum(p, 1e-300)).sum(axis=0)
            if use_acc:
                ccn = cos_centers
                dc = ccn[1] - ccn[0]
                mrow = fv[:, None] * rows + (1.0 - fv)[:, None] * 0.5
                mrow = mrow / (mrow.sum(axis=1, keepdims=True) * dc)
                Rl, L = acc
                lam = np.empty((mrow.shape[0], L + 1))
                pm1 = np.ones_like(ccn)
                pl = ccn.copy()
                lam[:, 0] = 1.0
                if L >= 1:
                    lam[:, 1] = (mrow * pl[None, :]).sum(axis=1) * dc
                for l in range(2, L + 1):
                    pm1, pl = pl, ((2 * l - 1) * ccn * pl - (l - 1) * pm1) / l
                    lam[:, l] = (mrow * pl[None, :]).sum(axis=1) * dc
                Z = lam @ Rl                                   # (N_events, G)
                ll = ll - np.log(np.maximum(Z, 1e-3)).sum(axis=0)
            w = np.exp(ll - ll.max())
            mm = (w[:, None] * grid).sum(axis=0)
            mm /= np.linalg.norm(mm)
            dirs[name][k] = mm
            res[name][k] = float(np.clip(mm @ n0, -1, 1))
            res_mode[name][k] = float(np.clip(grid[int(np.argmax(ll))] @ n0, -1, 1))
        if (k + 1) % 100 == 0:
            print(f"  {k+1}/{len(cats)} cats", flush=True)

    payload = {"cats": cats, "nsel": nsel, "burst_dir": bdir,
               "models": np.asarray(json.dumps(models))}
    payload.update({f"cos_{k}": v for k, v in res.items()})
    payload.update({f"mode_{k}": v for k, v in res_mode.items()})
    payload.update({f"dir_{k}": v for k, v in dirs.items()})
    np.savez(args.out, **payload)

    rng = np.random.RandomState(23)
    bi = [rng.randint(0, len(cats), len(cats)) for _ in range(4000)]
    ref = "fE"
    print(f"\n{'model':8s} {'theta68':>8} {'median':>8} {'mean':>8}  "
          f"{'d(theta68) vs fE [68%]':>28} {'d(mean)':>16}")
    summ = {}
    for name in models:
        c = res[name]
        t = np.degrees(np.arccos(np.clip(c, -1, 1)))
        tr = np.degrees(np.arccos(np.clip(res[ref], -1, 1)))
        d = theta68(c) - theta68(res[ref])
        bs = np.array([theta68(c[i]) - theta68(res[ref][i]) for i in bi])
        dm = t.mean() - tr.mean()
        de = (t - tr).std(ddof=1) / np.sqrt(len(t)) if len(t) > 1 else np.nan
        summ[name] = {"theta68": theta68(c), "median": float(np.median(t)),
                      "mean": float(t.mean()), "d_theta68_vs_fE": d,
                      "d_theta68_68ci": [float(np.percentile(bs, 16)), float(np.percentile(bs, 84))],
                      "d_theta68_95ci": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
                      "d_mean_vs_fE": dm, "d_mean_err": float(de), "n_cats": int(len(cats))}
        print(f"{name:8s} {theta68(c):8.2f} {np.median(t):8.2f} {t.mean():8.2f}  "
              f"{d:+8.2f} [{np.percentile(bs,16):+.2f},{np.percentile(bs,84):+.2f}]  "
              f"{dm:+8.3f} +- {de:.3f}")
    print(f"\nposterior-MODE estimator (same fits):")
    print(f"{'model':10s} {'theta68':>8} {'median':>8} {'mean':>8}  {'d(theta68) vs fE':>18}")
    for name in models:
        c = res_mode[name]
        t = np.degrees(np.arccos(np.clip(c, -1, 1)))
        summ[name]["mode_theta68"] = theta68(c)
        summ[name]["mode_mean"] = float(t.mean())
        print(f"{name:10s} {theta68(c):8.2f} {np.median(t):8.2f} {t.mean():8.2f}  "
              f"{theta68(c)-theta68(res_mode[ref]):+8.2f}")

    eras = [tuple(int(x) for x in e.split("-")) for e in args.eras.split(",")]
    print(f"\nper era (posterior mean):")
    print("| model | " + " | ".join(f"{lo}-{hi}" for lo, hi in eras) + " |")
    for name in models:
        cells = []
        for lo, hi in eras:
            m = (cats >= lo) & (cats <= hi)
            cells.append(f"{theta68(res[name][m]):.2f}")
        summ[name]["per_era_theta68"] = [float(x) for x in cells]
        print(f"| {name} | " + " | ".join(cells) + " |")
    Path(str(args.out).replace(".npz", "_summary.json")).write_text(json.dumps(summ, indent=2))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
