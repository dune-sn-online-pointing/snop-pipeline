#!/usr/bin/env python3
"""Closure Monte Carlo for the purity model: does f(E) beat a global f when the model is
exactly right by construction?

Synthetic bursts are built by resampling the REAL CT-selected events of the training slice
(their reco energy, CT score, true class and their real cos to their own burst axis), then
placing each event at that polar angle around a random burst axis with a UNIFORM azimuth.
By construction the mixture model
    p(cos | E) = f(E) pdf_ES,sel(cos | E) + (1 - f(E)) / 2
is then exactly the density that generated the data, apart from the azimuthal symmetry that
the construction imposes and the cos-binning of the ES table.  The fit is the posterior mean
on an equal-area sphere grid with a uniform prior, i.e. the same estimator the pipeline's
emcee targets, and every purity model is fitted on the SAME bursts (paired).

If f(E) wins here but loses on the real bursts, the defect is not the purity model.

Usage:
  python3 python/ana/brems_closure_mc.py --collect <npz> --es-table <tbl_ereco_es.npz> \
      --n-burst 3000 --out <results.npz>
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


def theta68(cos):
    return float(np.degrees(np.arccos(np.clip(np.quantile(cos, 0.32), -1.0, 1.0))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", required=True)
    ap.add_argument("--es-table", required=True)
    ap.add_argument("--n-burst", type=int, default=3000)
    ap.add_argument("--n-per-burst", type=int, default=147)
    ap.add_argument("--grid", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--fscan", default="", help="comma list of FLAT purity values to add")
    ap.add_argument("--generate", default="resample", choices=["resample", "table"],
                    help="'resample': each event keeps its real cos to its own burst axis. "
                         "'table': cos is drawn from the mixture the table describes (ES row for "
                         "true ES, flat for CC), which allows the detector-frame modulation R(d) "
                         "to be injected on top -- the direct test of the azimuthal-symmetry "
                         "assumption.")
    ap.add_argument("--inject-anisotropy", action="store_true",
                    help="with --generate table: draw directions from g(d.n0) R(d) with R the "
                         "detector-frame density measured on the slice's selected CC events")
    ap.add_argument("--by-cat", action="store_true",
                    help="resample whole real bursts (one cat's selected events) instead of "
                         "drawing events from the pooled slice: keeps the per-burst energy "
                         "composition and the burst-to-burst spread in ES quality")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    z = np.load(args.collect, allow_pickle=True)
    A = np.asarray(z["table"], dtype=np.float64)
    C = {c: A[:, i] for i, c in enumerate(list(z["cols"]))}
    sel = (C["ct"] >= CT_MIN) & (C["e_reco"] >= E_MIN)
    E = C["e_reco"][sel]
    S = C["ct"][sel]
    ES = (C["is_es"][sel] == 1)
    COS = C["cos_burst"][sel]
    CAT = C["cat"][sel]
    cat_idx = [np.where(CAT == c)[0] for c in np.unique(CAT)]
    n_pool = len(E)
    f_glob = float(ES.mean())
    print(f"pool: {n_pool} selected events, purity {f_glob:.4f}")

    tab = load_pdf_table(args.es_table, pdf_floor=1e-4)
    cos_centers = tab["cos_centers"]

    # ---- purity models ----------------------------------------------------------------
    i_e = np.clip(np.digitize(E, ENERGY_BINS[:, 0]) - 1, 0, len(ENERGY_BINS) - 1)
    i_s = np.clip(np.digitize(S, SCORE_EDGES) - 1, 0, len(SCORE_EDGES) - 2)
    n_s = len(SCORE_EDGES) - 1
    f_E = np.array([ES[i_e == i].mean() if (i_e == i).sum() >= 20 else np.nan
                    for i in range(len(ENERGY_BINS))])
    for i in range(len(ENERGY_BINS)):          # constant extrapolation
        if not np.isfinite(f_E[i]):
            ok = np.where(np.isfinite(f_E))[0]
            f_E[i] = f_E[ok[np.argmin(np.abs(ok - i))]]
    f_S = np.array([ES[i_s == j].mean() for j in range(n_s)])
    f_ES2 = np.full((len(ENERGY_BINS), n_s), np.nan)
    for i in range(len(ENERGY_BINS)):
        for j in range(n_s):
            m = (i_e == i) & (i_s == j)
            f_ES2[i, j] = ES[m].mean() if m.sum() >= 30 else np.nan
    for i in range(len(ENERGY_BINS)):
        for j in range(n_s):
            if not np.isfinite(f_ES2[i, j]):
                f_ES2[i, j] = f_S[j]
    models = {
        "true_fE":  lambda ie, isc: f_E[ie],
        "global":   lambda ie, isc: np.full(len(ie), f_glob),
        "g080":     lambda ie, isc: np.full(len(ie), f_glob * 0.8),
        "g120":     lambda ie, isc: np.full(len(ie), min(f_glob * 1.2, 0.99)),
        "fS":       lambda ie, isc: f_S[isc],
        "fE_fS":    lambda ie, isc: f_ES2[ie, isc],
        "perfect":  None,      # f_i = 1 for true ES, 0 for true CC (oracle upper bound)
    }
    for v in [float(x) for x in args.fscan.split(",") if x.strip()]:
        models[f"flat{v:.2f}"] = (lambda vv: (lambda ie, isc: np.full(len(ie), vv)))(v)
    print("f(E) (4-18 MeV rows):", np.round(f_E[1:8], 3))
    print("f(score):", np.round(f_S, 3))

    grid = fibonacci_sphere_grid(args.grid)
    R_grid = np.ones(len(grid))
    if args.inject_anisotropy:
        mcc = ~ES
        dR = np.column_stack([C["dx"][sel][mcc], C["dy"][sel][mcc], C["dz"][sel][mcc]])
        b_vec = dR.mean(axis=0)
        Qm = (dR[:, :, None] * dR[:, None, :]).mean(axis=0) - np.eye(3) / 3.0
        R_grid = np.maximum(1.0 + 3.0 * (grid @ b_vec)
                            + 7.5 * np.einsum("gi,ij,gj->g", grid, Qm, grid), 0.02)
        R_grid /= R_grid.mean()
        print(f"injecting R(d): b={np.round(b_vec,4)} diagQ={np.round(np.diag(Qm),4)} "
              f"R range [{R_grid.min():.3f},{R_grid.max():.3f}]")
    rng = np.random.default_rng(args.seed)
    out = {k: np.empty(args.n_burst) for k in models}
    N = args.n_per_burst

    for b in range(args.n_burst):
        if args.by_cat:
            idx = cat_idx[rng.integers(0, len(cat_idx))]
        else:
            idx = rng.integers(0, n_pool, N)
        c = COS[idx]
        n0 = rng.normal(size=3); n0 /= np.linalg.norm(n0)
        # orthonormal frame around n0
        a = np.array([1.0, 0.0, 0.0])
        if abs(n0[0]) > 0.9:
            a = np.array([0.0, 1.0, 0.0])
        u = np.cross(n0, a); u /= np.linalg.norm(u)
        v = np.cross(n0, u)
        rows = pdf_rows_for_energies(tab, E[idx])                      # (N, n_cos)
        if args.generate == "table":
            # draw the direction of each event from its own model density times R(d)
            base = np.where(ES[idx][:, None], 1.0, 0.0) * eval_pdf_rows(
                rows, np.clip(grid @ n0, -1.0, 1.0)[None, :].repeat(len(idx), axis=0), cos_centers)
            base = np.where(ES[idx][:, None], base, 0.5) * R_grid[None, :]
            cdf = np.cumsum(base, axis=1)
            cdf /= cdf[:, -1:]
            pick = (cdf < rng.random((len(idx), 1))).sum(axis=1).clip(0, len(grid) - 1)
            d = grid[pick]
            c = np.clip(d @ n0, -1.0, 1.0)
        else:
            phi = rng.uniform(0, 2 * np.pi, len(idx))
            sp = np.sqrt(np.clip(1 - c ** 2, 0, None))
            d = c[:, None] * n0[None, :] + sp[:, None] * (np.cos(phi)[:, None] * u[None, :]
                                                          + np.sin(phi)[:, None] * v[None, :])
        cosg = np.clip(d @ grid.T, -1.0, 1.0)                          # (N, G)
        g = np.maximum(eval_pdf_rows(rows, cosg, cos_centers), 1e-10)  # (N, G)
        for name, fn in models.items():
            if name == "perfect":
                fv = np.where(ES[idx], 1.0, 0.0)
            else:
                fv = np.asarray(fn(i_e[idx], i_s[idx]), dtype=np.float64)
            p = fv[:, None] * g + (1.0 - fv)[:, None] * 0.5
            ll = np.log(np.maximum(p, 1e-300)).sum(axis=0)             # (G,)
            w = np.exp(ll - ll.max())
            m = (w[:, None] * grid).sum(axis=0)
            m /= np.linalg.norm(m)
            out[name][b] = float(np.clip(m @ n0, -1, 1))
        if (b + 1) % 500 == 0:
            print(f"  {b+1}/{args.n_burst}", flush=True)

    np.savez(args.out, **{f"cos_{k}": v for k, v in out.items()},
             f_E=f_E, f_S=f_S, f_ES2=f_ES2, f_global=np.float64(f_glob),
             n_per_burst=np.int64(N), n_burst=np.int64(args.n_burst))

    ref = "true_fE"
    print(f"\n{'model':10s} {'theta68':>8} {'median':>8} {'mean':>8}   "
          f"{'d(theta68) vs f(E)':>22} {'d(mean) vs f(E)':>18}")
    rngb = np.random.RandomState(11)
    bidx = [rngb.randint(0, args.n_burst, args.n_burst) for _ in range(2000)]
    summ = {}
    for name in models:
        c = out[name]
        t = np.degrees(np.arccos(np.clip(c, -1, 1)))
        tr = np.degrees(np.arccos(np.clip(out[ref], -1, 1)))
        d = theta68(c) - theta68(out[ref])
        bs = np.array([theta68(c[i]) - theta68(out[ref][i]) for i in bidx])
        dm = t.mean() - tr.mean()
        dmerr = (t - tr).std(ddof=1) / np.sqrt(len(t))
        summ[name] = {"theta68": theta68(c), "median": float(np.median(t)),
                      "mean": float(t.mean()), "d_theta68": d,
                      "d_theta68_68ci": [float(np.percentile(bs, 16)), float(np.percentile(bs, 84))],
                      "d_mean": dm, "d_mean_err": float(dmerr)}
        print(f"{name:10s} {theta68(c):8.2f} {np.median(t):8.2f} {t.mean():8.2f}   "
              f"{d:+8.2f} [{np.percentile(bs,16):+.2f},{np.percentile(bs,84):+.2f}]   "
              f"{dm:+8.3f} +- {dmerr:.3f}")
    Path(str(args.out).replace(".npz", "_summary.json")).write_text(json.dumps(summ, indent=2))


if __name__ == "__main__":
    main()
