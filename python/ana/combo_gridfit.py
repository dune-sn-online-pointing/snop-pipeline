#!/usr/bin/env python3
"""Combined-likelihood grid fits: r3's detector-frame CC map + brems' ES acceptance term.

Per-event density of the combined model (cos-density convention, uniform = 0.5):

    p_i(d | n) = p_i * m_ES(d.n | E_i) * R_ES(d) / Z_i(n)  +  (1 - p_i) * q_CC(d)
    Z_i(n)     = sum_{l<=lmax} <P_l(c)>_{m_ES,i} * R_ES,l(n)

with

  * m_ES(.|E)  the burst-axis ES pdf table of the selection (as in ct_rescan_tables.py),
  * R_ES(d)    the detector-frame density of the selection's true-ES reco directions,
               band-limited to l <= lmax, <R>_sphere = 1     (brems sections 8-9),
  * q_CC(d)    the detector-frame density of the selection's true-CC reco directions in
               the cos-density convention, independent of n  (r3 re-scan "detector-map"),
  * p_i        the per-event ES probability (CT-score calibration, global f, f(E) or truth).

Setting R_ES == 1 and q_CC = the r3 map reproduces the r3 grid-mixture fit; setting
q_CC = 0.5, acc = "mix" and R from the selection's CC events reproduces the brems
acceptance fit (whose normalisation applies to the whole mixture row instead).

Estimator: exact posterior mean on an equal-area Fibonacci grid under a uniform prior --
the quantity the deployed emcee targets, without MCMC noise.  The posterior mode and the
truth-referenced 68% posterior quantile (for the coverage ratio) are stored too.

Arms are defined in a json list; see `combo_arms.json` written by combo_setup.

Usage:
  python3 python/ana/combo_gridfit.py --arms arms.json --tags ALL --cats 2-399,901-1224 \
      --eval-collect <npz> --slice-collect <npz> --tables-dir <dir> --out <chunk.npz>
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from ana.burst_direction import (cc_map_lookup, fibonacci_sphere_grid,  # noqa: E402
                                 load_cc_direction_map, load_pdf_table, pdf_rows_for_energies)
from ana.combo_acceptance import (band_limited_density, legendre_moments_of_rows,  # noqa: E402
                                  multipole_bands, real_sh, rotate_dirs,
                                  sh_coeffs_from_dirs, vmf_density_map)

ENERGY_BINS = np.array([(2, 4), (4, 6), (6, 8), (8, 10), (10, 12), (12, 14), (14, 16),
                        (16, 18), (18, 20), (20, 22), (22, 24), (24, 26), (26, 28),
                        (28, 30), (30, 35), (35, 40), (40, 50), (50, 70)], dtype=float)
MIN_E = 5.0
PDF_FLOOR = 1e-4
R_FLOOR = 0.05
GRID_CHUNK = 2048
N_THETA_SAMPLES = 4000
RULE_THR = {"t050": 0.50, "t080": 0.80, "all": 0.0}


def load_collect(path):
    z = np.load(path, allow_pickle=True)
    a = np.asarray(z["table"], dtype=np.float64)
    cols = list(z["cols"])
    return {c: a[:, i] for i, c in enumerate(cols)}


def theta68(cos):
    c = np.asarray(cos, dtype=np.float64)
    c = c[np.isfinite(c)]
    return float(np.degrees(np.arccos(np.clip(np.quantile(c, 0.32), -1.0, 1.0))))


def selection_mask(rule, energy, ct):
    if rule == "all":
        return energy > MIN_E
    return (ct >= RULE_THR[rule]) & (energy > MIN_E)


class SliceDensities:
    """R products (SH coefficients and vMF maps) of one training slice, per rule/class."""

    def __init__(self, slice_collect, lmax, kappa=30.0, map_grid_n=4000, cat_range=None):
        S = load_collect(slice_collect)
        if cat_range:
            m = (S["cat"] >= cat_range[0]) & (S["cat"] <= cat_range[1])
            S = {k: v[m] for k, v in S.items()}
        self.cats = (int(S["cat"].min()), int(S["cat"].max()))
        self.lmax = int(lmax)
        self.kappa = float(kappa)
        self.map_grid = fibonacci_sphere_grid(int(map_grid_n))
        d = np.column_stack([S["dx"], S["dy"], S["dz"]])
        self._dirs = d / np.linalg.norm(d, axis=1, keepdims=True)
        self._E, self._ct, self._es = S["e_reco"], S["ct"], S["is_es"] == 1
        self._cache = {}

    def sample(self, rule, cls):
        sel = selection_mask(rule, self._E, self._ct)
        if cls == "es":
            sel &= self._es
        elif cls == "cc":
            sel &= ~self._es
        elif cls != "all":
            raise ValueError(cls)
        return self._dirs[sel]

    def get(self, rule, cls, rotate=0):
        key = (rule, cls, int(rotate))
        if key in self._cache:
            return self._cache[key]
        d = self.sample(rule, cls)
        if rotate:
            d = rotate_dirs(d, rotate)
        coeffs = sh_coeffs_from_dirs(d, self.lmax)
        rel = vmf_density_map(d, self.map_grid, kappa=self.kappa)
        self._cache[key] = {"coeffs": coeffs, "rel_map": rel, "n": int(len(d))}
        print(f"  R[{rule}/{cls}{'/rot%d' % rotate if rotate else ''}]: N={len(d)}, "
              f"rms(R_l)={np.round(multipole_bands(coeffs, self.map_grid[:400], self.lmax).std(axis=1), 4)}",
              flush=True)
        return self._cache[key]


def purity_vector(arm, tabz, energy, ct, is_es, calib):
    mode = arm["pi"]
    if mode == "perfect":
        return is_es.astype(np.float64)
    if mode == "gf":
        return np.full(len(energy), float(tabz["f_global"]))
    if mode == "fE":
        ie = np.clip(np.digitize(energy, ENERGY_BINS[:, 0]) - 1, 0, len(ENERGY_BINS) - 1)
        return np.asarray(tabz["f_of_E"], dtype=np.float64)[ie]
    if mode == "calib":
        s = np.asarray(calib["score_center"], dtype=np.float64)
        p = np.asarray(calib["p_es_mono"], dtype=np.float64)
        return np.clip(np.interp(np.clip(ct, 0.0, 1.0), s, p, left=p[0], right=p[-1]), 0.0, 1.0)
    if mode.startswith("flat"):
        return np.full(len(energy), float(mode[4:]))
    raise ValueError(f"unknown purity model {mode!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", required=True)
    ap.add_argument("--tags", required=True, help="comma list of arm tags, or ALL")
    ap.add_argument("--cats", required=True, help="e.g. 2-399,901-1224")
    ap.add_argument("--eval-collect", required=True)
    ap.add_argument("--slice-collect", required=True)
    ap.add_argument("--tables-dir", required=True)
    ap.add_argument("--slice-cats", default="673-900",
                    help="slice range used for the R measurement (split-half check)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    ranges = [tuple(int(x) for x in r.split("-")) for r in args.cats.split(",")]
    for lo, hi in ranges:
        assert not (hi >= 400 and lo <= 621), f"range {lo}-{hi} touches off-limits cats 400-621"
    spec = {a["tag"]: a for a in json.loads(Path(args.arms).read_text())}
    tags = sorted(spec) if args.tags == "ALL" else args.tags.split(",")
    for t in tags:
        assert t in spec, f"unknown arm {t!r}"
    arms = [spec[t] for t in tags]
    lmax_max = max(int(a.get("lmax", 6)) for a in arms)
    sl = tuple(int(x) for x in args.slice_cats.split("-"))
    dens = SliceDensities(args.slice_collect, lmax_max, cat_range=sl)
    print(f"slice for R: cats {dens.cats}", flush=True)

    tabs, calibs, r3maps = {}, {}, {}
    for a in arms:
        tp = a.get("table") or str(Path(args.tables_dir) /
                                   f"combo_slice_{a['sel']}_{a.get('table_tag', 'full')}.npz")
        a["_table"] = tp
        if tp not in tabs:
            z = np.load(tp, allow_pickle=True)
            tabs[tp] = {"tab": load_pdf_table(tp, pdf_floor=PDF_FLOOR),
                        "f_global": float(z["f_global"]),
                        "f_of_E": np.asarray(z["f_of_E"], dtype=np.float64)}
        cp = a.get("calib")
        if cp and cp not in calibs:
            z = np.load(cp, allow_pickle=True)
            calibs[cp] = {"score_center": z["score_center"], "p_es_mono": z["p_es_mono"]}
        mp = a.get("cc_map")
        if mp and mp not in r3maps:
            r3maps[mp] = load_cc_direction_map(mp)

    # ------------------------------------------------------------------ per-arm R products
    grids = {}
    for a in arms:
        gn = int(a.get("grid_n", 12000))
        if gn not in grids:
            grids[gn] = fibonacci_sphere_grid(gn)
        a["_gn"] = gn
        lm = int(a.get("lmax", 6))
        rot = int(a.get("rotate", 0))
        a["_acc_src"] = None
        if a["acc"] != "none":
            src = a.get("acc_src") or ("cc" if a["acc"] == "mix" else
                                       ("all" if a["acc"] == "common" else "es"))
            a["_acc_src"] = src
            pack = dens.get(a["sel"], src, rot)
            key = ("Rl", a["sel"], src, rot, lm, gn)
            if key not in grids:
                grids[key] = multipole_bands(pack["coeffs"], grids[gn], lm)[:lm + 1]
            a["_Rl"] = grids[key]
            a["_acc_coeffs"] = pack["coeffs"]
        cc = a["cc"]
        a["_cc_coeffs"] = None
        a["_cc_relmap"] = None
        if cc in ("ccl6", "commonl6"):
            a["_cc_coeffs"] = dens.get(a["sel"], "cc" if cc == "ccl6" else "all", rot)["coeffs"]
        elif cc == "ccmap":
            pack = dens.get(a["sel"], "cc", rot)
            a["_cc_relmap"] = (dens.map_grid, pack["rel_map"])
        elif cc == "r3map":
            mp = r3maps[a["cc_map"]]
            if rot:
                raise ValueError("rotate is not supported with the fixed r3 map; use ccmap")
            a["_cc_relmap"] = (mp["grid_dirs"], 2.0 * mp["q"])
        elif cc != "flat":
            raise ValueError(f"unknown cc mode {cc!r}")

    # ------------------------------------------------------------------ evaluation events
    C = load_collect(args.eval_collect)
    keep = np.zeros(len(C["cat"]), bool)
    for lo, hi in ranges:
        keep |= (C["cat"] >= lo) & (C["cat"] <= hi)
    C = {k: v[keep] for k, v in C.items()}
    cats = np.unique(C["cat"]).astype(int)
    print(f"{len(cats)} cats to fit, {len(C['cat'])} cached clusters", flush=True)

    res = {t: {} for t in tags}
    t0 = time.time()
    for ic, cat in enumerate(cats):
        s = C["cat"] == cat
        E_all, ct_all = C["e_reco"][s], C["ct"][s]
        es_all = C["is_es"][s] == 1
        d_all = np.column_stack([C["dx"][s], C["dy"][s], C["dz"][s]])
        d_all = d_all / np.linalg.norm(d_all, axis=1, keepdims=True)
        n0 = np.array([C["bx"][s][0], C["by"][s][0], C["bz"][s][0]])
        n0 /= np.linalg.norm(n0)

        # group arms sharing selection + ES table + grid, so the expensive
        # (N x G) cos matrix and pdf interpolation are computed once
        groups = {}
        for a in arms:
            groups.setdefault((a["sel"], bool(a.get("es_only", False)), a["_table"], a["_gn"]),
                              []).append(a)

        for (rule, es_only, tpath, gn), garms in groups.items():
            m = selection_mask(rule, E_all, ct_all)
            if es_only:
                m = m & es_all
            n_ev = int(m.sum())
            grid = grids[gn]
            if n_ev == 0:
                for a in garms:
                    res[a["tag"]][cat] = dict(cos=np.nan, cos_mode=np.nan, q68=np.nan,
                                              nsel=0, nes=0, prior_ang=np.nan, prior_span=np.nan)
                continue
            d, E = d_all[m], E_all[m]
            ct, ies = ct_all[m], es_all[m]
            T = tabs[tpath]
            rows = pdf_rows_for_energies(T["tab"], E)
            cos_centers = T["tab"]["cos_centers"]
            log_rows = np.log(np.maximum(rows, 1e-300))
            c0, clast = cos_centers[0], cos_centers[-1]
            inv_dc = 1.0 / (cos_centers[1] - cos_centers[0])
            n_c = len(cos_centers)

            # per-arm per-event constants
            state = {}
            for a in garms:
                p = purity_vector(a, T, E, ct, ies, calibs.get(a.get("calib")))
                lm = int(a.get("lmax", 6))
                a_es = np.ones(n_ev)
                n_fl = 0
                if a["acc"] == "mix":
                    mrow = p[:, None] * rows + (1.0 - p)[:, None] * 0.5
                    mrow = mrow / (mrow.sum(axis=1, keepdims=True) * (cos_centers[1] - cos_centers[0]))
                    lam = legendre_moments_of_rows(mrow, cos_centers, lm)
                elif a["acc"] != "none":
                    lam = legendre_moments_of_rows(rows, cos_centers, lm)
                    a_es, n_fl = band_limited_density(a["_acc_coeffs"], d, lm, floor=R_FLOOR)
                else:
                    lam = None
                if a["cc"] == "flat":
                    q_cc = np.full(n_ev, 0.5)
                elif a["_cc_coeffs"] is not None:
                    r, _ = band_limited_density(a["_cc_coeffs"], d, lm, floor=R_FLOOR)
                    q_cc = 0.5 * r
                else:
                    g_map, rel = a["_cc_relmap"]
                    q_cc = 0.5 * rel[np.argmax(d @ np.asarray(g_map, dtype=np.float64).T, axis=1)]
                interp = a.get("interp", "log_es")
                premix = None
                if interp == "premix_log":
                    if a["acc"] != "none":
                        raise ValueError("interp='premix_log' only makes sense with acc='none'")
                    # exactly grid_mixture_posterior: premix the row, then interpolate its log
                    mr = p[:, None] * rows + (1.0 - p)[:, None] * q_cc[:, None]
                    premix = np.log(np.maximum(mr, 1e-300))
                state[a["tag"]] = {"p": p, "lam": lam, "a_es": a_es, "q_cc": q_cc,
                                   "ll": np.zeros(grid.shape[0]), "n_floored": n_fl,
                                   "interp": interp, "premix": premix,
                                   "prior": (np.zeros(grid.shape[0]) if lam is not None else None)}

            for st in range(0, grid.shape[0], GRID_CHUNK):
                g = grid[st:st + GRID_CHUNK]
                cosg = d @ g.T
                t = (np.clip(cosg, c0, clast) - c0) * inv_dc
                idx = np.minimum(t.astype(np.int64), n_c - 2)
                frac = t - idx
                v0 = np.take_along_axis(log_rows, idx, axis=1)
                v1 = np.take_along_axis(log_rows, idx + 1, axis=1)
                g_es = np.exp(v0 + (v1 - v0) * frac)          # pdf_ES(d_i . n), log-interpolated
                g_es_lin = None
                for a in garms:
                    S = state[a["tag"]]
                    p = S["p"][:, None]
                    if S["interp"] == "premix_log":
                        w0 = np.take_along_axis(S["premix"], idx, axis=1)
                        w1 = np.take_along_axis(S["premix"], idx + 1, axis=1)
                        S["ll"][st:st + GRID_CHUNK] += (w0 + (w1 - w0) * frac).sum(axis=0)
                        continue
                    if S["interp"] == "lin_es":
                        if g_es_lin is None:
                            u0 = np.take_along_axis(rows, idx, axis=1)
                            u1 = np.take_along_axis(rows, idx + 1, axis=1)
                            g_es_lin = u0 + (u1 - u0) * frac
                        gg = g_es_lin
                    else:
                        gg = g_es
                    if a["acc"] == "none":
                        dens_i = p * gg + (1.0 - p) * S["q_cc"][:, None]
                        S["ll"][st:st + GRID_CHUNK] += np.log(np.maximum(dens_i, 1e-300)).sum(axis=0)
                        continue
                    z = np.maximum(S["lam"] @ a["_Rl"][:, st:st + GRID_CHUNK], 1e-3)
                    logz = np.log(z)
                    if a["acc"] == "mix":
                        # brems form: the WHOLE mixture row carries R/Z; log R(d_i) drops out
                        dens_i = p * gg + (1.0 - p) * 0.5
                        S["ll"][st:st + GRID_CHUNK] += (np.log(np.maximum(dens_i, 1e-300))
                                                        - logz).sum(axis=0)
                    else:
                        # combined form: only the ES component carries R_ES(d)/Z_i(n)
                        dens_i = p * gg * (S["a_es"][:, None] / z) + (1.0 - p) * S["q_cc"][:, None]
                        S["ll"][st:st + GRID_CHUNK] += np.log(np.maximum(dens_i, 1e-300)).sum(axis=0)
                    S["prior"][st:st + GRID_CHUNK] += -logz.sum(axis=0)

            ang_truth = np.degrees(np.arccos(np.clip(grid @ n0, -1.0, 1.0)))
            for a in garms:
                S = state[a["tag"]]
                ll = S["ll"]
                w = np.exp(ll - ll.max())
                post = w / w.sum()
                mean_dir = (post[:, None] * grid).sum(axis=0)
                nrm = np.linalg.norm(mean_dir)
                mean_dir = mean_dir / nrm if nrm > 0 else grid[int(np.argmax(post))]
                rng = np.random.default_rng(42)
                smp = rng.choice(post.shape[0], size=N_THETA_SAMPLES, replace=True, p=post)
                q68 = float(np.quantile(ang_truth[smp], 0.68))
                pr_ang, pr_span = np.nan, np.nan
                if S["prior"] is not None:
                    pr = S["prior"]
                    pr_ang = float(ang_truth[int(np.argmax(pr))])
                    pr_span = float(pr.max() - pr.min())
                res[a["tag"]][cat] = dict(
                    cos=float(np.clip(mean_dir @ n0, -1, 1)),
                    cos_mode=float(np.clip(grid[int(np.argmax(ll))] @ n0, -1, 1)),
                    q68=q68, nsel=n_ev, nes=int(ies.sum()),
                    prior_ang=pr_ang, prior_span=pr_span, n_floored=int(S["n_floored"]))
        if (ic + 1) % 10 == 0:
            print(f"  {ic+1}/{len(cats)} cats, {time.time()-t0:.0f}s", flush=True)

    payload = {"cats": cats, "tags": np.asarray(json.dumps(tags)),
               "arms": np.asarray(json.dumps({t: {k: v for k, v in spec[t].items()
                                                  if not k.startswith("_")} for t in tags})),
               "slice_cats": np.asarray(list(dens.cats))}
    for t in tags:
        for key in ("cos", "cos_mode", "q68", "nsel", "nes", "prior_ang", "prior_span"):
            payload[f"{key}_{t}"] = np.asarray([res[t][c][key] for c in cats], dtype=np.float64)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    np.savez(args.out, **payload)

    print(f"\n{'arm':26s} {'theta68':>8} {'median':>8} {'frac>30':>8} {'cover':>7} "
          f"{'n_sel':>8} {'purity':>7} {'prior<90':>9}")
    for t in tags:
        c = payload[f"cos_{t}"]
        ok = np.isfinite(c)
        th = np.degrees(np.arccos(np.clip(c[ok], -1, 1)))
        ns, ne = payload[f"nsel_{t}"], payload[f"nes_{t}"]
        pa = payload[f"prior_ang_{t}"]
        fr = float(np.mean(pa[np.isfinite(pa)] < 90)) if np.isfinite(pa).any() else float("nan")
        print(f"{t:26s} {theta68(c[ok]):8.2f} {np.median(th):8.2f} {np.mean(th > 30):8.3f} "
              f"{theta68(c[ok])/np.median(payload['q68_'+t][ok]):7.2f} {ns.mean():8.1f} "
              f"{ne.sum()/max(ns.sum(),1):7.3f} {fr:9.3f}")
    print(f"\nwrote {args.out} ({time.time()-t0:.0f}s, {len(cats)} cats)")


if __name__ == "__main__":
    main()
