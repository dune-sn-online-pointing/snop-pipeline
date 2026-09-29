#!/usr/bin/env python3
"""PART 2a: re-fit the 722 evaluation cats storing the RECONSTRUCTED DIRECTION VECTORS.

The combo_study results npz only store cos(reco, truth); the signed radial bias with
respect to the nearest detector pole needs the vector, so the four arms of interest are
re-fitted here with this review's own implementation of the grid posterior mean:

  CUR_t080_gf_flat      t>=0.80, p_i = global f, flat CC, no acceptance   (deployed today)
  DEC_t050_noR          t>=0.50, p_i = P(ES|s), flat CC, no acceptance    (no correction)
  GATE_A_t050_map41k    t>=0.50, p_i = P(ES|s), r3 detector-frame CC map  (CC map only)
  CMB2_t050_accCC_ccl6  t>=0.50, p_i = P(ES|s), common R on both terms    (recommended)

R is re-measured here from the slice's selected true-CC reco directions with
`pole_common.sh_coeffs` (independent of `combo_acceptance`).  Per-cat cos(reco, truth) is
compared against the stored combo_study values as a gate.

Usage: python3 python/ana/pole_refit.py --out <dir> [--nproc 8] [--cats 2-399,901-1224]
"""
import argparse
import json
import sys
import time
from math import pi, sqrt
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from ana.pole_common import (band_density, fib_grid, legendre_moments, load_collect,  # noqa: E402
                             multipole_bands, p_es_from_calib, sh_coeffs)
from ana.burst_direction import load_pdf_table, pdf_rows_for_energies  # noqa: E402

CD = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/combo_study")
BD = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/brems_study")
CALIB = CD / "tables" / "combo_p_es_given_score_e5_full.npz"
R3MAP = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/r3_rescan/tables/"
             "cc_reco_direction_map_r3_v63.npz")
LMAX, PDF_FLOOR, R_FLOOR, CHUNK = 6, 1e-4, 0.05, 2048

ARMS = [
    dict(tag="CUR_t080_gf_flat", thr=0.80, pi="gf", acc=False, cc="flat",
         grid_n=12000, interp="log_es", table="t080"),
    dict(tag="DEC_t050_noR", thr=0.50, pi="calib", acc=False, cc="flat",
         grid_n=12000, interp="log_es", table="t050"),
    dict(tag="GATE_A_t050_map41k", thr=0.50, pi="calib", acc=False, cc="r3map",
         grid_n=41253, interp="premix_log", table="t050"),
    dict(tag="CMB2_t050_accCC_ccl6", thr=0.50, pi="calib", acc=True, cc="ccl6",
         grid_n=12000, interp="log_es", table="t050"),
]

_G = {}


def setup():
    """Tables, R coefficients, grids -- built once per process."""
    if _G:
        return _G
    S = load_collect(str(BD / "collect_673_900.npz"), 673, 900)
    sel = (S["ct"] >= 0.50) & (S["e_reco"] > 5.0) & (S["is_es"] != 1)
    _G["coeffs"] = sh_coeffs(S["dirs"][sel], LMAX)
    _G["n_cc_slice"] = int(sel.sum())
    for t in ("t050", "t080"):
        z = np.load(CD / "tables" / f"combo_slice_{t}_full.npz", allow_pickle=True)
        _G[t] = {"tab": load_pdf_table(str(CD / "tables" / f"combo_slice_{t}_full.npz"),
                                       pdf_floor=PDF_FLOOR),
                 "f_global": float(z["f_global"])}
    m = np.load(R3MAP, allow_pickle=True)
    _G["r3map"] = (np.asarray(m["grid_dirs"], dtype=np.float64),
                   np.asarray(m["q"], dtype=np.float64))
    _G["grids"] = {}
    for gn in sorted({a["grid_n"] for a in ARMS}):
        g = fib_grid(gn)
        _G["grids"][gn] = (g, multipole_bands(_G["coeffs"], g, LMAX))
    return _G


def _interp_log_rows(log_rows, centers, cosg):
    c0, dc, nc = centers[0], centers[1] - centers[0], len(centers)
    t = (np.clip(cosg, c0, centers[-1]) - c0) / dc
    idx = np.minimum(t.astype(np.int64), nc - 2)
    fr = t - idx
    v0 = np.take_along_axis(log_rows, idx, axis=1)
    v1 = np.take_along_axis(log_rows, idx + 1, axis=1)
    return v0 + (v1 - v0) * fr, idx, fr


def fit_cat(payload):
    cat, d, E, ct, ies, n0 = payload
    G = setup()
    out = {"cat": int(cat), "truth": n0.tolist()}
    for arm in ARMS:
        m = (ct >= arm["thr"]) & (E > 5.0)
        n_ev = int(m.sum())
        if n_ev == 0:
            out[arm["tag"]] = dict(nsel=0)
            continue
        dd, ee, cc, es = d[m], E[m], ct[m], ies[m]
        T = G[arm["table"]]
        tab = T["tab"]
        centers = tab["cos_centers"]
        rows = pdf_rows_for_energies(tab, ee)
        log_rows = np.log(np.maximum(rows, 1e-300))
        p = (np.full(n_ev, T["f_global"]) if arm["pi"] == "gf"
             else p_es_from_calib(str(CALIB), cc))
        grid, rl_full = G["grids"][arm["grid_n"]]
        rl = rl_full[:LMAX + 1]
        # CC component in the cos-density convention (isotropic = 0.5)
        if arm["cc"] == "flat":
            q_cc = np.full(n_ev, 0.5)
        elif arm["cc"] == "ccl6":
            q_cc = 0.5 * band_density(G["coeffs"], dd, LMAX, floor=R_FLOOR)[0]
        else:
            gm, q = G["r3map"]
            q_cc = q[np.argmax(dd @ gm.T, axis=1)]
        lam = legendre_moments(rows, centers, LMAX) if arm["acc"] else None
        r_es = band_density(G["coeffs"], dd, LMAX, floor=R_FLOOR)[0] if arm["acc"] else None
        premix = None
        if arm["interp"] == "premix_log":
            premix = np.log(np.maximum(p[:, None] * rows + (1 - p)[:, None] * q_cc[:, None],
                                       1e-300))
        ll = np.zeros(grid.shape[0])
        prior = np.zeros(grid.shape[0]) if arm["acc"] else None
        for st in range(0, grid.shape[0], CHUNK):
            g = grid[st:st + CHUNK]
            cosg = dd @ g.T
            if premix is not None:
                v, _, _ = _interp_log_rows(premix, centers, cosg)
                ll[st:st + CHUNK] = v.sum(axis=0)
                continue
            v, _, _ = _interp_log_rows(log_rows, centers, cosg)
            g_es = np.exp(v)
            if not arm["acc"]:
                dens = p[:, None] * g_es + (1 - p)[:, None] * q_cc[:, None]
            else:
                z = np.maximum(lam @ rl[:, st:st + CHUNK], 1e-3)
                dens = (p[:, None] * g_es * (r_es[:, None] / z)
                        + (1 - p)[:, None] * q_cc[:, None])
                prior[st:st + CHUNK] = -np.log(z).sum(axis=0)
            ll[st:st + CHUNK] = np.log(np.maximum(dens, 1e-300)).sum(axis=0)
        w = np.exp(ll - ll.max())
        post = w / w.sum()
        v = (post[:, None] * grid).sum(axis=0)
        nv = np.linalg.norm(v)
        reco = v / nv if nv > 0 else grid[int(np.argmax(post))]
        mode = grid[int(np.argmax(ll))]
        rng = np.random.default_rng(42)
        ang_truth = np.degrees(np.arccos(np.clip(grid @ n0, -1.0, 1.0)))
        smp = rng.choice(post.shape[0], size=4000, replace=True, p=post)
        out[arm["tag"]] = dict(
            nsel=n_ev, nes=int(es.sum()), reco=reco.tolist(), mode=mode.tolist(),
            cos=float(np.clip(reco @ n0, -1, 1)), cos_mode=float(np.clip(mode @ n0, -1, 1)),
            q68=float(np.quantile(ang_truth[smp], 0.68)),
            prior_ang=(float(ang_truth[int(np.argmax(prior))]) if prior is not None
                       else float("nan")))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--nproc", type=int, default=8)
    ap.add_argument("--cats", default="2-399,901-1224")
    args = ap.parse_args()
    ranges = [tuple(int(x) for x in r.split("-")) for r in args.cats.split(",")]
    for lo, hi in ranges:
        assert not (hi >= 400 and lo <= 621), "range touches off-limits cats 400-621"
    t0 = time.time()
    E = load_collect(str(BD / "collect_eval_slimonly.npz"))
    keep = np.zeros(len(E["cat"]), bool)
    for lo, hi in ranges:
        keep |= (E["cat"] >= lo) & (E["cat"] <= hi)
    E = {k: v[keep] for k, v in E.items()}
    cats = np.unique(E["cat"]).astype(int)
    print(f"{len(cats)} cats, {len(E['cat'])} cached clusters", flush=True)
    jobs = []
    for cat in cats:
        s = E["cat"] == cat
        n0 = np.array([E["bx"][s][0], E["by"][s][0], E["bz"][s][0]])
        jobs.append((cat, E["dirs"][s], E["e_reco"][s], E["ct"][s], E["is_es"][s] == 1,
                     n0 / np.linalg.norm(n0)))
    setup()
    import multiprocessing as mp
    with mp.Pool(args.nproc) as pool:
        res = []
        for i, r in enumerate(pool.imap(fit_cat, jobs, chunksize=2)):
            res.append(r)
            if (i + 1) % 50 == 0:
                print(f"  {i+1}/{len(jobs)} cats, {time.time()-t0:.0f}s", flush=True)
    res.sort(key=lambda r: r["cat"])
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pay = {"cats": np.array([r["cat"] for r in res]),
           "truth": np.array([r["truth"] for r in res]),
           "n_cc_slice": np.array(setup()["n_cc_slice"]),
           "coeffs": setup()["coeffs"]}
    for arm in ARMS:
        t = arm["tag"]
        for k, dflt, shp in (("reco", [np.nan] * 3, 3), ("mode", [np.nan] * 3, 3),
                             ("cos", np.nan, 0), ("cos_mode", np.nan, 0), ("q68", np.nan, 0),
                             ("nsel", 0, 0), ("nes", 0, 0), ("prior_ang", np.nan, 0)):
            pay[f"{k}_{t}"] = np.array([r[t].get(k, dflt) for r in res], dtype=np.float64)
    np.savez(out / "pole_refit.npz", **pay)

    # ------------------------------------------------------------------ gate vs combo_study
    stored = load_stored(CD / "results")
    gate = {}
    for arm in ARMS:
        t = arm["tag"]
        if t not in stored:
            continue
        c_new = pay[f"cos_{t}"]
        c_old = np.array([stored[t].get(int(c), np.nan) for c in pay["cats"]])
        ok = np.isfinite(c_new) & np.isfinite(c_old)
        th_new = np.degrees(np.arccos(np.clip(c_new[ok], -1, 1)))
        th_old = np.degrees(np.arccos(np.clip(c_old[ok], -1, 1)))
        gate[t] = {"n": int(ok.sum()),
                   "theta68_mine": float(np.degrees(np.arccos(np.quantile(c_new[ok], 0.32)))),
                   "theta68_stored": float(np.degrees(np.arccos(np.quantile(c_old[ok], 0.32)))),
                   "median_mine": float(np.median(th_new)),
                   "median_stored": float(np.median(th_old)),
                   "mean_abs_dtheta_deg": float(np.mean(np.abs(th_new - th_old))),
                   "max_abs_dtheta_deg": float(np.max(np.abs(th_new - th_old))),
                   "median_abs_dcos": float(np.median(np.abs(c_new[ok] - c_old[ok])))}
        print(t, json.dumps(gate[t]), flush=True)
    (out / "pole_refit_gate.json").write_text(json.dumps(gate, indent=1))
    print(f"wrote {out/'pole_refit.npz'} ({time.time()-t0:.0f}s)")


def load_stored(rdir):
    """cos(reco, truth) per cat per arm from the combo_study result chunks."""
    store = {}
    for f in sorted(Path(rdir).glob("[EFH]_*.npz")):
        z = np.load(f, allow_pickle=True)
        tags = json.loads(str(z["tags"]))
        cats = z["cats"].astype(int)
        for t in tags:
            store.setdefault(t, {}).update(dict(zip(cats.tolist(),
                                                    z[f"cos_{t}"].tolist())))
    return store


if __name__ == "__main__":
    main()
