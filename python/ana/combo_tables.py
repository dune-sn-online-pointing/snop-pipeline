#!/usr/bin/env python3
"""Training-slice products for the combined (CC-map + ES-acceptance) likelihood study.

Builds, per selection rule and from a TRAINING-SLICE per-event table only:

  * pdf_ES,rule(cos | E)   burst-axis ES component, exactly the construction of
                           `ct_rescan_tables.py` (raw histogram, nearest-row fill)
  * f(E) and the global f  of that selection
  * P(ES | CT score)       isotonic calibration on E > cut (as ct_rescan_tables.py)
  * R_ES, R_CC, R_all      detector-frame reco-direction densities of the selection's
                           true-ES / true-CC / all events, as real spherical-harmonic
                           coefficients up to l = lmax (49 numbers at lmax = 6) AND as
                           von Mises-Fisher kernel maps (kappa 30, the `build_cc_direction_map`
                           representation), so both the r3 CC-map path and the brems
                           acceptance-normalisation path can be driven from one file.

Cats are asserted to lie inside the training slice 673-900.  `--cat-min/--cat-max` cut the
slice for the split-half over-fitting check.

Usage:
  python3 python/ana/combo_tables.py --collect <slice collect npz> --out-dir <dir> --tag full
  python3 python/ana/combo_tables.py --collect <...> --out-dir <dir> --tag h1 --cat-max 786
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from ana.burst_direction import fibonacci_sphere_grid, load_pdf_table  # noqa: E402
from ana.combo_acceptance import (check_addition_theorem, sh_coeffs_from_dirs,  # noqa: E402
                                  vmf_density_map)

ENERGY_BINS = np.array([(2, 4), (4, 6), (6, 8), (8, 10), (10, 12), (12, 14), (14, 16),
                        (16, 18), (18, 20), (20, 22), (22, 24), (24, 26), (26, 28),
                        (28, 30), (30, 35), (35, 40), (40, 50), (50, 70)], dtype=float)
N_COS = 100
COS_EDGES = np.linspace(-1.0, 1.0, N_COS + 1)
COS_CENTERS = 0.5 * (COS_EDGES[:-1] + COS_EDGES[1:])
WIDTHS = COS_EDGES[1:] - COS_EDGES[:-1]
MIN_E = 5.0
LMAX = 6
KAPPA = 30.0
MAP_GRID_N = 4000
RULES = {"t050": 0.50, "t080": 0.80, "all": 0.0}
AXES = {"+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0), "-y": (0, -1, 0),
        "+z": (0, 0, 1), "-z": (0, 0, -1)}


def load_collect(path):
    z = np.load(path, allow_pickle=True)
    a = np.asarray(z["table"], dtype=np.float64)
    cols = list(z["cols"])
    return {c: a[:, i] for i, c in enumerate(cols)}


def hist_table(cos, energy):
    pdf = np.zeros((len(ENERGY_BINS), N_COS))
    n_per = np.zeros(len(ENERGY_BINS), dtype=np.int64)
    for i, (lo, hi) in enumerate(ENERGY_BINS):
        m = (energy >= lo) & (energy < hi)
        n_per[i] = int(m.sum())
        if n_per[i] > 0:
            c, _ = np.histogram(cos[m], bins=COS_EDGES)
            pdf[i] = c / (c.sum() * WIDTHS[0])
    return pdf, n_per


def fill_rows(pdf, n_per, min_count=50):
    pdf = np.array(pdf, dtype=np.float64, copy=True)
    good = np.asarray(n_per) >= min_count
    idx = np.arange(len(n_per))
    gi = idx[good]
    for i in idx:
        if not good[i]:
            pdf[i] = pdf[gi[np.argmin(np.abs(gi - i))]]
    return pdf, good


def fill_f(f_raw, n_tot, min_count=20):
    f = np.asarray(f_raw, dtype=np.float64).copy()
    meas = (n_tot >= min_count) & np.isfinite(f)
    idx = np.arange(len(f))
    gi = idx[meas]
    for i in idx:
        if not meas[i]:
            f[i] = f[gi[np.argmin(np.abs(gi - i))]]
    return f, meas


def pava(y, w):
    """Weighted isotonic (non-decreasing) regression, pool-adjacent-violators."""
    y = list(map(float, y))
    w = list(map(float, w))
    blocks = [[y[i], w[i], 1] for i in range(len(y))]
    i = 0
    while i < len(blocks) - 1:
        if blocks[i][0] <= blocks[i + 1][0] + 1e-15:
            i += 1
            continue
        a, b = blocks[i], blocks.pop(i + 1)
        tw = a[1] + b[1]
        a[0] = (a[0] * a[1] + b[0] * b[1]) / tw if tw > 0 else a[0]
        a[1], a[2] = tw, a[2] + b[2]
        if i > 0:
            i -= 1
    out = []
    for v, _, n in blocks:
        out.extend([v] * n)
    return np.asarray(out)


def density_products(dirs, grid, lmax, kappa, label):
    """SH coefficients (lmax), vMF relative-density map and diagnostics for one sample."""
    coeffs = sh_coeffs_from_dirs(dirs, lmax)
    rel_map = vmf_density_map(dirs, grid, kappa=kappa)
    err, rl_sh, _ = check_addition_theorem(dirs[:min(len(dirs), 40000)], grid[:400], lmax)
    inertia = np.linalg.eigvalsh((dirs.T @ dirs) / len(dirs))
    diag = {"label": label, "n_events": int(len(dirs)),
            "rms_R_l": [float(v) for v in rl_sh.std(axis=1)],
            "noise_floor_R_l": [float(np.sqrt(2 * l + 1) / np.sqrt(len(dirs)))
                                for l in range(lmax + 1)],
            "addition_theorem_max_abs_diff": err,
            "inertia_eigenvalues": [float(v) for v in inertia],
            "vmf_rel_density_range": [float(rel_map.min()), float(rel_map.max())],
            "vmf_rel_at_axes": {k: float(rel_map[int(np.argmax(grid @ np.asarray(v, float)))])
                                for k, v in AXES.items()}}
    return coeffs, rel_map, diag


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", required=True, help="training-slice per-event table (brems_collect)")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--tag", required=True, help="full | h1 | h2 ... (file name suffix)")
    ap.add_argument("--cat-min", type=int, default=673)
    ap.add_argument("--cat-max", type=int, default=900)
    ap.add_argument("--lmax", type=int, default=LMAX)
    ap.add_argument("--kappa", type=float, default=KAPPA)
    ap.add_argument("--map-grid-n", type=int, default=MAP_GRID_N)
    ap.add_argument("--n-score-bins", type=int, default=50)
    ap.add_argument("--gate-dir", default=None,
                    help="r3_rescan/tables dir: gate the rebuilt ES tables / calibration against it")
    args = ap.parse_args()
    assert 673 <= args.cat_min and args.cat_max <= 900, "tables must come from the slice 673-900"

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    C = load_collect(args.collect)
    keep = (C["cat"] >= args.cat_min) & (C["cat"] <= args.cat_max)
    C = {k: v[keep] for k, v in C.items()}
    cats = np.unique(C["cat"]).astype(int)
    ncat = len(cats)
    E, P, ES = C["e_reco"], C["ct"], C["is_es"] == 1
    COS = C["cos_burst"]
    D = np.column_stack([C["dx"], C["dy"], C["dz"]])
    D = D / np.linalg.norm(D, axis=1, keepdims=True)
    print(f"slice {args.cat_min}-{args.cat_max}: {ncat} cats, {len(E)} clusters, "
          f"{ES.mean()*100:.2f}% true ES")

    grid = fibonacci_sphere_grid(args.map_grid_n)
    prov = {"tag": args.tag, "collect": str(args.collect), "cats": [args.cat_min, args.cat_max],
            "n_cats": ncat, "n_clusters": int(len(E)), "lmax": args.lmax, "kappa": args.kappa,
            "map_grid_n": args.map_grid_n, "min_energy": MIN_E, "rules": {}, "gates": {}}

    for rule, thr in RULES.items():
        sel = (E > MIN_E) if rule == "all" else ((P >= thr) & (E > MIN_E))
        n = int(sel.sum())
        es_sel, cc_sel = sel & ES, sel & ~ES
        raw, n_es = hist_table(COS[es_sel], E[es_sel])
        pdf_es, rows_meas = fill_rows(raw, n_es)

        n_tot = np.zeros(len(ENERGY_BINS))
        n_esb = np.zeros(len(ENERGY_BINS))
        for i, (elo, ehi) in enumerate(ENERGY_BINS):
            inb = (E >= elo) & (E < ehi) & sel
            n_tot[i] = int(inb.sum())
            n_esb[i] = int((inb & ES).sum())
        f_raw = np.divide(n_esb, n_tot, out=np.full(len(n_tot), np.nan), where=n_tot > 0)
        f_fill, f_meas = fill_f(f_raw, n_tot)
        f_global = float(n_esb.sum() / n_tot.sum())

        cf_es, map_es, d_es = density_products(D[es_sel], grid, args.lmax, args.kappa, f"{rule}/ES")
        cf_cc, map_cc, d_cc = density_products(D[cc_sel], grid, args.lmax, args.kappa, f"{rule}/CC")
        cf_all, map_all, d_all = density_products(D[sel], grid, args.lmax, args.kappa, f"{rule}/all")

        path = out / f"combo_slice_{rule}_{args.tag}.npz"
        np.savez(path,
                 pdf_2d=pdf_es, pdf_2d_raw=raw, row_measured=rows_meas,
                 cosine_bin_edges=COS_EDGES, cosine_bin_centers=COS_CENTERS,
                 energy_bins=ENERGY_BINS.astype(np.int64), n_events_per_bin=n_es,
                 smoothing_method=np.asarray("Raw histogram (no smoothing)"),
                 table_note=np.asarray(f"burst-axis pdf_ES for rule {rule}, slice "
                                       f"{args.cat_min}-{args.cat_max}"),
                 f_of_E=f_fill, f_of_E_raw=f_raw, f_measured=f_meas, f_global=np.float64(f_global),
                 n_tot_per_bin=n_tot, n_es_per_bin=n_esb,
                 coeffs_es=cf_es, coeffs_cc=cf_cc, coeffs_all=cf_all,
                 map_grid_dirs=grid.astype(np.float32),
                 rel_es=map_es.astype(np.float32), rel_cc=map_cc.astype(np.float32),
                 rel_all=map_all.astype(np.float32),
                 lmax=np.int64(args.lmax), kappa=np.float64(args.kappa),
                 rule=np.asarray(rule), threshold=np.float64(thr),
                 cats=np.asarray([args.cat_min, args.cat_max]), n_cats=np.int64(ncat),
                 n_selected=np.int64(n), n_es_selected=np.int64(int(es_sel.sum())))
        prov["rules"][rule] = {
            "threshold": thr, "n_selected": n, "n_per_burst": n / ncat,
            "purity_global": f_global, "f_of_E_raw": f_raw.tolist(),
            "f_of_E_filled": f_fill.tolist(), "rows_measured": int(rows_meas.sum()),
            "R_ES": d_es, "R_CC": d_cc, "R_all": d_all, "path": str(path)}
        print(f"\n{rule}: {n/ncat:.1f}/burst, f = {f_global:.4f}, "
              f"{int(rows_meas.sum())}/{len(rows_meas)} rows measured")
        for nm, dd in (("ES", d_es), ("CC", d_cc), ("all", d_all)):
            print(f"  R_{nm:3s} N={dd['n_events']:7d} rms(R_l)="
                  f"{np.round(dd['rms_R_l'], 3)} floor={np.round(dd['noise_floor_R_l'], 3)} "
                  f"vMF rel {dd['vmf_rel_density_range'][0]:.2f}-{dd['vmf_rel_density_range'][1]:.2f} "
                  f"addthm {dd['addition_theorem_max_abs_diff']:.2e}")

    # ------------------------------------------------------------------ P(ES | score)
    for cut, tg in ((5.0, "e5"),):
        m = E > cut
        s, y = P[m], ES[m].astype(np.float64)
        q = np.unique(np.quantile(s, np.linspace(0, 1, args.n_score_bins + 1)))
        q[0], q[-1] = -1e-9, 1.0 + 1e-9
        idx = np.clip(np.searchsorted(q, s, side="right") - 1, 0, len(q) - 2)
        nb = len(q) - 1
        cnt = np.bincount(idx, minlength=nb).astype(np.float64)
        nes = np.bincount(idx, weights=y, minlength=nb)
        smean = np.bincount(idx, weights=s, minlength=nb) / np.maximum(cnt, 1)
        p_raw = np.divide(nes, cnt, out=np.zeros(nb), where=cnt > 0)
        p_mono = pava(p_raw, cnt)
        cpath = out / f"combo_p_es_given_score_{tg}_{args.tag}.npz"
        np.savez(cpath, score_edges=q, score_center=smean, p_es_raw=p_raw, p_es_mono=p_mono,
                 n=cnt, n_es=nes, energy_cut=np.float64(cut),
                 cats=np.asarray([args.cat_min, args.cat_max]))
        prov[f"calibration_{tg}"] = {"path": str(cpath), "n_bins": int(nb),
                                     "n_events": int(cnt.sum()),
                                     "p_range": [float(p_mono.min()), float(p_mono.max())]}
        print(f"\nP(ES|score) {tg}: {nb} bins, {int(cnt.sum())} events, "
              f"p {p_mono.min():.4f}-{p_mono.max():.4f}")

    # ------------------------------------------------------------------ gates vs the r3 products
    if args.gate_dir:
        g = Path(args.gate_dir)
        for rule in ("t050", "t080"):
            ref = g / f"pdf_es_burstaxis_{rule}.npz"
            if not ref.exists():
                continue
            a = load_pdf_table(str(ref))["pdf"]
            b = load_pdf_table(str(out / f"combo_slice_{rule}_{args.tag}.npz"))["pdf"]
            prov["gates"][f"pdf_es_{rule}_max_abs_diff"] = float(np.max(np.abs(a - b)))
            print(f"GATE pdf_ES {rule}: max|d| = {np.max(np.abs(a - b)):.3e}")
        cref = g / "p_es_given_score_e5.npz"
        if cref.exists():
            zr = np.load(cref, allow_pickle=True)
            zn = np.load(out / f"combo_p_es_given_score_e5_{args.tag}.npz", allow_pickle=True)
            if zr["p_es_mono"].shape == zn["p_es_mono"].shape:
                dd = float(np.max(np.abs(zr["p_es_mono"] - zn["p_es_mono"])))
                ds = float(np.max(np.abs(zr["score_center"] - zn["score_center"])))
                prov["gates"]["calib_e5_max_abs_diff"] = dd
                prov["gates"]["calib_e5_score_center_max_abs_diff"] = ds
                print(f"GATE P(ES|score) e5: max|dp| = {dd:.3e}, max|ds| = {ds:.3e}")
        pref = g / "ct_rescan_tables_provenance.json"
        if pref.exists():
            pj = json.loads(pref.read_text())
            for rule in ("t050", "t080"):
                if rule in pj.get("rules", {}):
                    prov["gates"][f"purity_{rule}_ref_vs_new"] = [
                        pj["rules"][rule]["purity_global"], prov["rules"][rule]["purity_global"]]
                    print(f"GATE purity {rule}: r3 {pj['rules'][rule]['purity_global']:.5f} "
                          f"vs new {prov['rules'][rule]['purity_global']:.5f}")

    ppath = out / f"combo_tables_provenance_{args.tag}.json"
    ppath.write_text(json.dumps(prov, indent=2))
    print(f"\nwrote {ppath}")


if __name__ == "__main__":
    main()
