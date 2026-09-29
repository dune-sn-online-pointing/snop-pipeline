#!/usr/bin/env python3
"""PART 1 of the pole-dependence review: independent re-derivation and numerical gates.

Checks, all with this review's own code (`pole_common`) against (a) brute-force sphere
integration and (b) the previous agent's `combo_acceptance`:

  G1  lambda_0 = 1 for every ES table row  ->  Z = 1 when R == 1 (exact).
  G2  my own R(d) from the slice's true-CC reco directions vs theirs (coeffs_cc).
  G3  R_l(n) from the harmonic coefficients vs (2l+1) <P_l(d.n)> measured on the sample.
  G4  ring-average identity  Rbar(c; n) = sum_l R_l(n) P_l(c).
  G5  Z_i(n) = sum_l lambda_l^(i) R_l(n) vs brute-force >=100k-point sphere integration and
      vs the previous agent's implementation, for >= 10 (energy, n) pairs.
  G6  claim (b): the common-R factorisation on a real cat -- two log-likelihood surfaces
      differ by a constant.
  G7  prior-only leak test re-run from scratch on the 722 evaluation cats.
  G8  geometry of R: where it peaks, its value at the six poles, band rms.

Usage:  python3 python/ana/pole_derive.py --out <dir>
"""
import argparse
import json
import sys
import time
from math import pi, sqrt
from pathlib import Path

import numpy as np
from scipy.special import eval_legendre

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from ana.pole_common import (POLES, band_density, fib_grid, legendre_moments,  # noqa: E402
                             load_collect, multipole_bands, p_es_from_calib, pole_angle,
                             real_sh, ring_average_R, sh_coeffs)
from ana.burst_direction import load_pdf_table, pdf_rows_for_energies  # noqa: E402

# previous agent's code -- used ONLY for comparison
from ana import combo_acceptance as CA  # noqa: E402

CD = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/combo_study")
BD = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/brems_study")
NN = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/neural-networks/electron_direction/"
          "three_plane_v63_matchfix_ft58_20260921_132520")
TBL = CD / "tables" / "combo_slice_t050_full.npz"
CALIB = CD / "tables" / "combo_p_es_given_score_e5_full.npz"
ES_TABLE = NN / "cosine_energy_pdf_es_burstaxis_ct050_r3.npz"
LMAX = 6
PDF_FLOOR = 1e-4


def int_legendre_over_bins(edges, lmax):
    """Exact integral of P_l over each cos bin: int P_l = (P_{l+1} - P_{l-1})/(2l+1)."""
    e = np.asarray(edges, dtype=np.float64)
    out = np.empty((lmax + 1, len(e) - 1))
    out[0] = np.diff(e)
    for l in range(1, lmax + 1):
        F = (eval_legendre(l + 1, e) - eval_legendre(l - 1, e)) / (2 * l + 1)
        out[l] = np.diff(F)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--nbrute", type=int, default=200000)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    J = {}
    t0 = time.time()

    # ---------------------------------------------------------------- tables and slice sample
    tab = load_pdf_table(str(ES_TABLE), pdf_floor=PDF_FLOOR)
    cc_centers = tab["cos_centers"]
    cc_edges = tab["cos_edges"]
    zt = np.load(TBL, allow_pickle=True)
    coeffs_prev = np.asarray(zt["coeffs_cc"], dtype=np.float64)

    S = load_collect(str(BD / "collect_673_900.npz"))
    sel = (S["ct"] >= 0.50) & (S["e_reco"] > 5.0)
    cc = sel & (S["is_es"] != 1)
    d_cc = S["dirs"][cc]
    print(f"slice: {len(S['cat'])} events, t050&E>5 = {sel.sum()}, true CC = {cc.sum()}",
          flush=True)
    J["slice"] = {"n_events": int(len(S["cat"])), "n_selected": int(sel.sum()),
                  "n_cc_selected": int(cc.sum()),
                  "cats": [int(S["cat"].min()), int(S["cat"].max())]}

    # =============================================== G1  lambda_0 == 1  ->  Z == 1 for R == 1
    lam_all = legendre_moments(tab["pdf"], cc_centers, LMAX)
    iso = np.zeros((LMAX + 1) ** 2)
    iso[0] = sqrt(4.0 * pi)
    probe = fib_grid(97)
    z_iso = lam_all @ multipole_bands(iso, probe, LMAX)
    J["G1_lambda0"] = {"max_abs_dev_lambda0_from_1": float(np.max(np.abs(lam_all[:, 0] - 1.0))),
                       "max_abs_dev_Z_from_1_when_R_is_1": float(np.max(np.abs(z_iso - 1.0))),
                       "lambda_l_of_7MeV_row": [float(x) for x in
                                                legendre_moments(pdf_rows_for_energies(tab, [7.0]),
                                                                 cc_centers, LMAX)[0]]}
    print("G1", J["G1_lambda0"], flush=True)

    # =============================================== G2  my R(d) vs the previous agent's R(d)
    coeffs_mine = sh_coeffs(d_cc, LMAX)
    gtest = fib_grid(20000)
    r_mine = band_density(coeffs_mine, gtest, LMAX)[0]
    r_prev = CA.band_limited_density(coeffs_prev, gtest, LMAX, floor=-1e9)[0]
    J["G2_R_of_d"] = {"n_cc": int(len(d_cc)),
                      "max_abs_diff": float(np.max(np.abs(r_mine - r_prev))),
                      "max_rel_diff": float(np.max(np.abs(r_mine - r_prev)) /
                                            np.max(np.abs(r_prev))),
                      "R_range_mine": [float(r_mine.min()), float(r_mine.max())],
                      "R_mean_mine": float(r_mine.mean())}
    print("G2", J["G2_R_of_d"], flush=True)

    # =============================================== G3  R_l from coeffs vs direct <P_l(d.n)>
    probe = fib_grid(500)
    rl_sh = multipole_bands(coeffs_mine, probe, LMAX)
    x = d_cc @ probe.T
    rl_dir = np.array([(2 * l + 1) * eval_legendre(l, x).mean(axis=0) for l in range(LMAX + 1)])
    J["G3_addition_theorem"] = {"max_abs_diff": float(np.max(np.abs(rl_sh - rl_dir))),
                                "rms_R_l": [float(v) for v in rl_sh.std(axis=1)],
                                "noise_floor_sqrt2l1_over_sqrtN":
                                    [float(sqrt(2 * l + 1) / sqrt(len(d_cc)))
                                     for l in range(LMAX + 1)]}
    print("G3", J["G3_addition_theorem"], flush=True)

    # =============================================== G4  ring-average identity
    rng = np.random.default_rng(7)
    nvec = rng.normal(size=(6, 3))
    nvec /= np.linalg.norm(nvec, axis=1, keepdims=True)
    worst = 0.0
    nphi = 720
    phi = (np.arange(nphi) + 0.5) * 2 * pi / nphi
    for n in nvec:
        e1 = np.cross(n, [0.0, 0.0, 1.0] if abs(n[2]) < 0.9 else [1.0, 0.0, 0.0])
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(n, e1)
        for c in (-0.9, -0.3, 0.0, 0.45, 0.8, 0.99):
            s = sqrt(1 - c * c)
            ring = c * n[None, :] + s * (np.cos(phi)[:, None] * e1[None, :]
                                         + np.sin(phi)[:, None] * e2[None, :])
            direct = band_density(coeffs_mine, ring, LMAX)[0].mean()
            ident = float(ring_average_R(coeffs_mine, n, [c], LMAX)[0])
            worst = max(worst, abs(direct - ident))
    J["G4_ring_average"] = {"max_abs_diff": float(worst), "n_phi": nphi}
    print("G4", J["G4_ring_average"], flush=True)

    # =============================================== G5  Z_i(n): Funk-Hecke vs brute force
    gb = fib_grid(args.nbrute)
    rb = band_density(coeffs_mine, gb, LMAX)[0]
    rb_prev = CA.band_limited_density(coeffs_prev, gb, LMAX, floor=-1e9)[0]
    ilp = int_legendre_over_bins(cc_edges, LMAX)                    # (lmax+1, nbins) exact
    rows_all = tab["pdf"]
    energies = [5.5, 6.3, 7.0, 8.4, 9.9, 11.5, 13.0, 16.0, 21.0, 30.0, 45.0, 60.0]
    rng = np.random.default_rng(11)
    ndirs = rng.normal(size=(len(energies), 3))
    ndirs /= np.linalg.norm(ndirs, axis=1, keepdims=True)
    ndirs[0] = POLES[0]
    ndirs[1] = POLES[4]
    ndirs[2] = np.array([1.0, 1.0, 1.0]) / sqrt(3.0)
    rows = pdf_rows_for_energies(tab, energies)
    lam_mine = legendre_moments(rows, cc_centers, LMAX)
    lam_prev = CA.legendre_moments_of_rows(rows, cc_centers, LMAX)
    rl_mine = multipole_bands(coeffs_mine, ndirs, LMAX)
    rl_prev = CA.multipole_bands(coeffs_prev, ndirs, LMAX)
    z_mine = np.einsum("il,li->i", lam_mine, rl_mine)
    z_prev = np.einsum("il,li->i", lam_prev, rl_prev)
    # exact-bin-integral version of lambda (removes the midpoint quadrature error)
    lam_exact = rows @ ilp.T
    z_exact = np.einsum("il,li->i", lam_exact, rl_mine)
    # brute force: step-function row on the cos bins, equal-area sphere average
    idx_bin = lambda c: np.clip(np.searchsorted(cc_edges, c, side="right") - 1, 0,   # noqa: E731
                                len(cc_centers) - 1)
    # Z_i(n) = int [m(d.n|E_i)/(2 pi)] R(d) dOmega = (4 pi / 2 pi) <m R>_sphere = 2 <m R>.
    # The factor 2 is the whole cos-density-vs-solid-angle convention: m is a pdf per unit
    # cos (isotropic = 1/2), its solid-angle density is m/(2 pi).
    CONV = 2.0
    z_bf = np.empty(len(energies))
    z_bf_prevR = np.empty(len(energies))
    for i, n in enumerate(ndirs):
        c = np.clip(gb @ n, -1.0, 1.0)
        mstep = rows[i][idx_bin(c)]
        z_bf[i] = CONV * float(np.mean(mstep * rb))
        z_bf_prevR[i] = CONV * float(np.mean(mstep * rb_prev))
    rel = np.abs(z_mine - z_bf) / z_bf
    J["G5_Z"] = {"n_brute": int(args.nbrute), "energies": energies,
                 "n_dirs": ndirs.tolist(),
                 "Z_funkhecke_mine": z_mine.tolist(), "Z_brute_force": z_bf.tolist(),
                 "Z_prev_agent": z_prev.tolist(), "Z_exact_bin_lambda": z_exact.tolist(),
                 "max_rel_mine_vs_brute": float(rel.max()),
                 "max_rel_exactlambda_vs_brute":
                     float(np.max(np.abs(z_exact - z_bf) / z_bf)),
                 "max_rel_mine_vs_prev": float(np.max(np.abs(z_mine - z_prev) / z_prev)),
                 "max_rel_midpoint_vs_exact_lambda":
                     float(np.max(np.abs(z_mine - z_exact) / z_exact)),
                 "max_rel_brute_mineR_vs_prevR":
                     float(np.max(np.abs(z_bf - z_bf_prevR) / z_bf_prevR))}
    print("G5", {k: v for k, v in J["G5_Z"].items() if k.startswith("max") or k == "n_brute"},
          flush=True)

    # =============================================== G8  geometry of R
    gg = fib_grid(200000)
    rg = band_density(coeffs_mine, gg, LMAX)[0]
    pa = pole_angle(gg)
    order = np.argsort(rg)
    J["G8_R_geometry"] = {
        "R_min": float(rg.min()), "R_max": float(rg.max()), "R_mean": float(rg.mean()),
        "argmax_dir": gg[order[-1]].tolist(), "argmin_dir": gg[order[0]].tolist(),
        "pole_angle_of_argmax_deg": float(pole_angle(gg[order[-1]:order[-1] + 1])[0]),
        "pole_angle_of_argmin_deg": float(pole_angle(gg[order[0]:order[0] + 1])[0]),
        "R_at_poles": {"+x": float(band_density(coeffs_mine, POLES[0:1], LMAX)[0][0]),
                       "-x": float(band_density(coeffs_mine, POLES[1:2], LMAX)[0][0]),
                       "+y": float(band_density(coeffs_mine, POLES[2:3], LMAX)[0][0]),
                       "-y": float(band_density(coeffs_mine, POLES[3:4], LMAX)[0][0]),
                       "+z": float(band_density(coeffs_mine, POLES[4:5], LMAX)[0][0]),
                       "-z": float(band_density(coeffs_mine, POLES[5:6], LMAX)[0][0])},
        "R_at_111": float(band_density(coeffs_mine, (np.ones((1, 3)) / sqrt(3)), LMAX)[0][0]),
        "mean_R_vs_pole_angle": {},
        "frac_below_floor_0p05": float(np.mean(rg < 0.05)),
    }
    for lo, hi in [(0, 10), (10, 20), (20, 30), (30, 40), (40, 54.8)]:
        m = (pa >= lo) & (pa < hi)
        J["G8_R_geometry"]["mean_R_vs_pole_angle"][f"{lo}-{hi}"] = float(rg[m].mean())
    print("G8", json.dumps(J["G8_R_geometry"], indent=1)[:900], flush=True)

    # =============================================== G6  common-R factorisation on a real cat
    E = load_collect(str(BD / "collect_eval_slimonly.npz"))
    grid = fib_grid(12000)
    rl_grid = multipole_bands(coeffs_mine, grid, LMAX)
    J["G6_factorisation"] = {}
    for cat in (5, 317, 1044):
        s = E["cat"] == cat
        m = s & (E["ct"] >= 0.50) & (E["e_reco"] > 5.0)
        d, en, ct = E["dirs"][m], E["e_reco"][m], E["ct"][m]
        p = p_es_from_calib(str(CALIB), ct)
        rows_i = pdf_rows_for_energies(tab, en)
        lam = legendre_moments(rows_i, cc_centers, LMAX)
        rd, nfl = band_density(coeffs_mine, d, LMAX, floor=0.05)
        cosg = d @ grid.T
        g_es = np.exp(_interp_log(rows_i, cc_centers, cosg))
        z = np.maximum(lam @ rl_grid, 1e-3)
        ll_withR = np.log(np.maximum(p[:, None] * g_es * (rd[:, None] / z)
                                     + (1 - p)[:, None] * 0.5 * rd[:, None], 1e-300)).sum(axis=0)
        ll_noR = np.log(np.maximum(p[:, None] * g_es / z + (1 - p)[:, None] * 0.5,
                                   1e-300)).sum(axis=0)
        dl = ll_withR - ll_noR
        J["G6_factorisation"][str(cat)] = {
            "n_selected": int(m.sum()), "n_R_floored": int(nfl),
            "sum_log_R": float(np.sum(np.log(rd))),
            "mean_dlogL": float(dl.mean()),
            "max_abs_dlogL_minus_const": float(np.max(np.abs(dl - dl.mean()))),
            "logL_span": float(ll_noR.max() - ll_noR.min()),
            "posterior_mean_angle_diff_deg": float(_pm_angle_diff(grid, ll_withR, ll_noR))}
        print("G6", cat, J["G6_factorisation"][str(cat)], flush=True)

    # =============================================== G7  prior-only leak test, 722 cats
    cats = np.unique(E["cat"]).astype(int)
    ang, span, frac = [], [], []
    for cat in cats:
        s = (E["cat"] == cat) & (E["ct"] >= 0.50) & (E["e_reco"] > 5.0)
        if s.sum() == 0:
            continue
        en = E["e_reco"][s]
        n0 = np.array([E["bx"][s][0], E["by"][s][0], E["bz"][s][0]])
        n0 /= np.linalg.norm(n0)
        lam = legendre_moments(pdf_rows_for_energies(tab, en), cc_centers, LMAX)
        pr = -np.log(np.maximum(lam @ rl_grid, 1e-3)).sum(axis=0)
        k = int(np.argmax(pr))
        ang.append(float(np.degrees(np.arccos(np.clip(grid[k] @ n0, -1, 1)))))
        span.append(float(pr.max() - pr.min()))
    ang = np.asarray(ang)
    span = np.asarray(span)
    J["G7_prior_only"] = {"n_cats": int(len(ang)), "mean_angle_deg": float(ang.mean()),
                          "median_angle_deg": float(np.median(ang)),
                          "frac_lt_90": float(np.mean(ang < 90)),
                          "frac_lt_90_err": float(sqrt(0.25 / len(ang))),
                          "mean_span_loglike": float(span.mean()),
                          "angle_quartiles": [float(q) for q in
                                              np.quantile(ang, [0.25, 0.5, 0.75])]}
    print("G7", J["G7_prior_only"], flush=True)

    J["_meta"] = {"lmax": LMAX, "pdf_floor": PDF_FLOOR, "seconds": time.time() - t0,
                  "es_table": str(ES_TABLE), "acceptance_table": str(TBL)}
    (out / "pole_derive.json").write_text(json.dumps(J, indent=1))
    np.savez(out / "pole_derive.npz", coeffs_mine=coeffs_mine, coeffs_prev=coeffs_prev,
             prior_angle=ang, prior_span=span)
    print(f"\nwrote {out/'pole_derive.json'} ({time.time()-t0:.0f}s)")


def _interp_log(rows, centers, cosg):
    c0, dc, nc = centers[0], centers[1] - centers[0], len(centers)
    lr = np.log(np.maximum(rows, 1e-300))
    t = (np.clip(cosg, c0, centers[-1]) - c0) / dc
    idx = np.minimum(t.astype(np.int64), nc - 2)
    fr = t - idx
    v0 = np.take_along_axis(lr, idx, axis=1)
    v1 = np.take_along_axis(lr, idx + 1, axis=1)
    return v0 + (v1 - v0) * fr


def _pm_angle_diff(grid, ll1, ll2):
    def pm(ll):
        w = np.exp(ll - ll.max())
        v = (w[:, None] * grid).sum(axis=0)
        return v / np.linalg.norm(v)
    a, b = pm(ll1), pm(ll2)
    return np.degrees(np.arccos(np.clip(a @ b, -1, 1)))


if __name__ == "__main__":
    main()
