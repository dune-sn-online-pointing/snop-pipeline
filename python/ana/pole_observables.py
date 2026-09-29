#!/usr/bin/env python3
"""PART 2d: the real-data observables that distinguish ACCEPTANCE from MIGRATION.

An acceptance R(d) is a multiplicative thinning: the reconstruction map d_true -> d_reco is
untouched, only the number of surviving events changes.  A migration drags reconstructed
directions towards the detector axes: the same marginal pile-up, but the resolution is
degraded and the conditional density is NOT m(d.n) R(d)/Z(n).

Tests (all on the 722 EVALUATION cats, which are independent of the slice 673-900 where the
ES table and R were measured; the slice cache is used for the pile-up and its energy
dependence, as a cross-check):

  D1  pile-up: <R> vs the reco direction's angle to the nearest axis, true ES and true CC.
  D2  the acceptance model's own prediction for the burst-axis cos distribution:
        E[c|n]   = sum_l a_l^(i) R_l(n) / Z_i(n),   a_l = int c m_i(c) P_l(c) dc
        E[c^2|n] = sum_l b_l^(i) R_l(n) / Z_i(n),   b_l = int c^2 m_i(c) P_l(c) dc
      compared with the measured <cos(d_reco, n)> of TRUE ES events in bins of the burst
      direction's pole angle -- and with <cos(d_true_electron, n)>, which the detector
      cannot touch and which a migration leaves exactly flat.
  D3  class test on R: for true-ES events the density is m_i(c) R(d)/Z_i(n), so weighting by
      1/m_i(c) gives R(d) up to an n-dependent CONSTANT.  The R inferred this way must be
      the SAME for bursts pointing near an axis and far from one if the acceptance model is
      right; under migration it is not.
  D4  energy dependence of the pile-up (true CC, slice cache): a geometric acceptance should
      be roughly energy independent, a reconstruction degeneracy should weaken with energy.

Usage: python3 python/ana/pole_observables.py --out <dir>
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

from ana.pole_common import (band_density, fib_grid, legendre_moments, load_collect,  # noqa: E402
                            multipole_bands, pole_angle, sh_coeffs)
from ana.burst_direction import load_pdf_table, pdf_rows_for_energies  # noqa: E402

CD = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/combo_study")
BD = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/brems_study")
SLICE_CACHE = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/r3_rescan/"
                   "slice_cache_673_900.npz")
LMAX, PDF_FLOOR = 6, 1e-4
PA_BINS = [0, 10, 20, 30, 40, 54.8]
PROBE = 60000


def mean_R_profile(coeffs, probe, pa, bins):
    r = band_density(coeffs, probe, LMAX)[0]
    return {f"{bins[i]}-{bins[i+1]}": float(r[(pa >= bins[i]) & (pa < bins[i + 1])].mean())
            for i in range(len(bins) - 1)}


def weighted_moments(rows, centers, lmax, power):
    """int c^power m(c) P_l(c) dc for each row; shape (N, lmax+1)."""
    c = np.asarray(centers, dtype=np.float64)
    dc = c[1] - c[0]
    w = rows * (c ** power)[None, :]
    return np.stack([(w * eval_legendre(l, c)[None, :]).sum(axis=1) * dc
                     for l in range(lmax + 1)], axis=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    J = {}

    tab = load_pdf_table(str(CD / "tables" / "combo_slice_t050_full.npz"), pdf_floor=PDF_FLOOR)
    centers = tab["cos_centers"]
    probe = fib_grid(PROBE)
    pa_probe = pole_angle(probe)

    # ---------------------------------------------------------- R measured on the slice (ref)
    S = load_collect(str(BD / "collect_673_900.npz"), 673, 900)
    ssel = (S["ct"] >= 0.50) & (S["e_reco"] > 5.0)
    coeffs_R = sh_coeffs(S["dirs"][ssel & (S["is_es"] != 1)], LMAX)   # the deployed R (from CC)
    J["R_reference"] = {"n_cc_slice": int((ssel & (S["is_es"] != 1)).sum()),
                        "mean_R_vs_pole_angle": mean_R_profile(coeffs_R, probe, pa_probe,
                                                              PA_BINS)}

    # ---------------------------------------------------------------------------- evaluation
    E = load_collect(str(BD / "collect_eval_slimonly.npz"))
    sel = (E["ct"] >= 0.50) & (E["e_reco"] > 5.0)
    es = sel & (E["is_es"] == 1)
    cc = sel & (E["is_es"] != 1)
    b = np.column_stack([E["bx"], E["by"], E["bz"]])
    b = b / np.linalg.norm(b, axis=1, keepdims=True)
    pa_burst = pole_angle(b)
    print(f"eval: {sel.sum()} selected, ES {es.sum()}, CC {cc.sum()}", flush=True)

    # ============================================================ D1  pile-up, ES vs CC
    c_es = sh_coeffs(E["dirs"][es], LMAX)
    c_cc = sh_coeffs(E["dirs"][cc], LMAX)
    rl_es = multipole_bands(c_es, probe, LMAX)
    rl_cc = multipole_bands(c_cc, probe, LMAX)
    J["D1_pileup"] = {
        "n_es": int(es.sum()), "n_cc": int(cc.sum()),
        "mean_R_vs_pole_angle_ES": mean_R_profile(c_es, probe, pa_probe, PA_BINS),
        "mean_R_vs_pole_angle_CC": mean_R_profile(c_cc, probe, pa_probe, PA_BINS),
        "rms_R_l_ES": [float(v) for v in rl_es.std(axis=1)],
        "rms_R_l_CC": [float(v) for v in rl_cc.std(axis=1)],
        "noise_floor_ES": [float(sqrt(2 * l + 1) / sqrt(es.sum())) for l in range(LMAX + 1)],
        "noise_floor_CC": [float(sqrt(2 * l + 1) / sqrt(cc.sum())) for l in range(LMAX + 1)],
        "R_at_poles_CC": [float(v) for v in band_density(
            c_cc, np.eye(3), LMAX)[0]],
    }
    print("D1", json.dumps(J["D1_pileup"]["mean_R_vs_pole_angle_CC"]), flush=True)

    # ============================================================ D2  model prediction vs data
    ie = np.where(es)[0]
    rows = pdf_rows_for_energies(tab, E["e_reco"][ie])
    lam = legendre_moments(rows, centers, LMAX)
    a_l = weighted_moments(rows, centers, LMAX, 1)
    b_l = weighted_moments(rows, centers, LMAX, 2)
    rl_ev = multipole_bands(coeffs_R, b[ie], LMAX).T                 # (N, lmax+1)
    Z = np.maximum((lam * rl_ev).sum(axis=1), 1e-3)
    pred_c = (a_l * rl_ev).sum(axis=1) / Z
    pred_c2 = (b_l * rl_ev).sum(axis=1) / Z
    obs_c = E["cos_burst"][ie]
    obs_t = E["cos_true_burst"][ie]
    pa_ev = pa_burst[ie]
    rows_iso = lam[:, 0]                                             # == 1
    _ = rows_iso
    D2 = {"n_es": int(len(ie)), "bins": {}}
    for i in range(len(PA_BINS) - 1):
        m = (pa_ev >= PA_BINS[i]) & (pa_ev < PA_BINS[i + 1])
        if m.sum() < 50:
            continue
        n = int(m.sum())
        D2["bins"][f"{PA_BINS[i]}-{PA_BINS[i+1]}"] = {
            "n_events": n,
            "obs_mean_cos_reco": float(obs_c[m].mean()),
            "obs_sem_cos_reco": float(obs_c[m].std(ddof=1) / sqrt(n)),
            "pred_mean_cos_reco_acceptance": float(pred_c[m].mean()),
            "obs_var_cos_reco": float(obs_c[m].var(ddof=1)),
            "pred_var_cos_reco_acceptance": float(pred_c2[m].mean()
                                                  - pred_c[m].mean() ** 2),
            "obs_mean_cos_true_electron": float(obs_t[m].mean()),
            "obs_sem_cos_true_electron": float(obs_t[m].std(ddof=1) / sqrt(n)),
            "obs_mean_reco_minus_true": float((obs_c[m] - obs_t[m]).mean()),
            "obs_rms_reco_minus_true": float((obs_c[m] - obs_t[m]).std(ddof=1)),
        }
    # shape comparison: subtract the sample mean from data and prediction
    om, pm = obs_c.mean(), pred_c.mean()
    D2["shape"] = {"global_obs_mean": float(om), "global_pred_mean": float(pm)}
    for k, v in D2["bins"].items():
        v["obs_minus_global"] = v["obs_mean_cos_reco"] - om
        v["pred_minus_global"] = v["pred_mean_cos_reco_acceptance"] - pm
        v["residual_obs_minus_pred"] = v["obs_minus_global"] - v["pred_minus_global"]
        v["residual_in_sem"] = v["residual_obs_minus_pred"] / v["obs_sem_cos_reco"]
    J["D2_model_prediction"] = D2
    for k, v in D2["bins"].items():
        print(f"D2 {k:>10} n={v['n_events']:6d} obs={v['obs_mean_cos_reco']:.4f} "
              f"pred={v['pred_mean_cos_reco_acceptance']:.4f} "
              f"resid={v['residual_obs_minus_pred']:+.4f} ({v['residual_in_sem']:+.1f} sem) "
              f"cos_true={v['obs_mean_cos_true_electron']:.4f} "
              f"rms(reco-true)={v['obs_rms_reco_minus_true']:.4f}", flush=True)

    # ============================================================ D3  class test on R
    # w_i = 1 / m_i(cos_burst_i): the weighted density of d is R(d) / Z_i(n)  ->  same R for
    # every burst class IF the acceptance model holds.
    mi = _eval_rows(rows, centers, obs_c)
    w = 1.0 / np.maximum(mi, 0.05)
    D3 = {"m_floor": 0.05, "w_p99": float(np.quantile(w, 0.99)), "classes": {}}
    for tag, m in (("burst_pole_lt25", pa_ev < 25.0), ("burst_pole_gt35", pa_ev > 35.0),
                   ("all", np.ones(len(ie), bool))):
        cf = sh_coeffs(E["dirs"][ie][m], LMAX, weights=w[m])
        rl = multipole_bands(cf, probe, LMAX)
        D3["classes"][tag] = {"n_events": int(m.sum()),
                              "rms_R_l": [float(v) for v in rl.std(axis=1)],
                              "mean_R_vs_pole_angle": mean_R_profile(cf, probe, pa_probe,
                                                                     PA_BINS),
                              "R_range": [float(rl.sum(axis=0).min()),
                                          float(rl.sum(axis=0).max())]}
    rlo = band_density(_coeffs(D3, E, ie, w, pa_ev < 25.0, LMAX), probe, LMAX)[0]
    rhi = band_density(_coeffs(D3, E, ie, w, pa_ev > 35.0, LMAX), probe, LMAX)[0]
    rref = band_density(coeffs_R, probe, LMAX)[0]
    D3["near_minus_far_profile"] = {k: float(rlo[(pa_probe >= PA_BINS[i])
                                                 & (pa_probe < PA_BINS[i + 1])].mean()
                                    - rhi[(pa_probe >= PA_BINS[i])
                                          & (pa_probe < PA_BINS[i + 1])].mean())
                                    for i, k in enumerate(
                                        [f"{PA_BINS[i]}-{PA_BINS[i+1]}"
                                         for i in range(len(PA_BINS) - 1)])}
    D3["corr_with_R_CC"] = {"near": float(np.corrcoef(rlo, rref)[0, 1]),
                            "far": float(np.corrcoef(rhi, rref)[0, 1])}
    D3["slope_vs_R_CC"] = {"near": float(np.polyfit(rref, rlo, 1)[0]),
                           "far": float(np.polyfit(rref, rhi, 1)[0])}
    J["D3_class_test"] = D3
    print("D3 near:", json.dumps(D3["classes"]["burst_pole_lt25"]["mean_R_vs_pole_angle"]),
          flush=True)
    print("D3 far :", json.dumps(D3["classes"]["burst_pole_gt35"]["mean_R_vs_pole_angle"]),
          flush=True)

    # ============================================================ D4  energy dependence
    Z2 = np.load(SLICE_CACHE, allow_pickle=True)
    dq = np.asarray(Z2["dirs"], dtype=np.float64)
    dq /= np.linalg.norm(dq, axis=1, keepdims=True)
    eq, pq, esq = (np.asarray(Z2["energy"], dtype=np.float64),
                   np.asarray(Z2["proba"], dtype=np.float64),
                   np.asarray(Z2["is_es"]).astype(bool))
    selq = (pq >= 0.50) & (eq > 5.0)
    D4 = {"source": str(SLICE_CACHE), "n_selected": int(selq.sum()), "bins": {}}
    for lo, hi in [(5, 6), (6, 8), (8, 10), (10, 12), (12, 25), (5, 25)]:
        m = selq & (~esq) & (eq >= lo) & (eq < hi)
        if m.sum() < 500:
            continue
        cf = sh_coeffs(dq[m], LMAX)
        rl = multipole_bands(cf, probe, LMAX)
        D4["bins"][f"{lo}-{hi}"] = {
            "n_cc": int(m.sum()),
            "rms_R_l": [float(v) for v in rl.std(axis=1)],
            "noise_floor": [float(sqrt(2 * l + 1) / sqrt(m.sum())) for l in range(LMAX + 1)],
            "mean_R_vs_pole_angle": mean_R_profile(cf, probe, pa_probe, PA_BINS)}
        r = rl.sum(axis=0)
        D4["bins"][f"{lo}-{hi}"]["contrast_R_near_over_far"] = float(
            r[pa_probe < 10].mean() / r[pa_probe > 40].mean())
    # same for true ES, for the record
    D4["ES"] = {}
    for lo, hi in [(5, 6), (6, 8), (8, 10), (10, 25), (5, 25)]:
        m = selq & esq & (eq >= lo) & (eq < hi)
        if m.sum() < 500:
            continue
        cf = sh_coeffs(dq[m], LMAX)
        r = band_density(cf, probe, LMAX)[0]
        D4["ES"][f"{lo}-{hi}"] = {"n_es": int(m.sum()),
                                  "contrast_R_near_over_far":
                                      float(r[pa_probe < 10].mean() / r[pa_probe > 40].mean())}
    J["D4_energy"] = D4
    for k, v in D4["bins"].items():
        print(f"D4 CC {k:>6} n={v['n_cc']:6d} contrast(near/far)="
              f"{v['contrast_R_near_over_far']:.3f} rms_R4={v['rms_R_l'][4]:.3f} "
              f"(floor {v['noise_floor'][4]:.3f})", flush=True)

    # ---------------------------------------------------- D5 resolution vs reco pole angle
    # For bursts far from any axis, split TRUE ES by where the RECO direction landed.
    far = pa_ev > 35.0
    pa_reco = pole_angle(E["dirs"][ie])
    D5 = {"burst_pole_angle_gt": 35.0, "bins": {}}
    for i in range(len(PA_BINS) - 1):
        m = far & (pa_reco >= PA_BINS[i]) & (pa_reco < PA_BINS[i + 1])
        if m.sum() < 200:
            continue
        D5["bins"][f"{PA_BINS[i]}-{PA_BINS[i+1]}"] = {
            "n_events": int(m.sum()),
            "mean_cos_reco": float(obs_c[m].mean()),
            "mean_cos_true_electron": float(obs_t[m].mean()),
            "mean_reco_minus_true": float((obs_c[m] - obs_t[m]).mean()),
            "rms_reco_minus_true": float((obs_c[m] - obs_t[m]).std(ddof=1)),
            "corr_reco_true": float(np.corrcoef(obs_c[m], obs_t[m])[0, 1])}
    J["D5_resolution_vs_reco_pole"] = D5
    for k, v in D5["bins"].items():
        print(f"D5 {k:>10} n={v['n_events']:6d} <cos_reco>={v['mean_cos_reco']:.4f} "
              f"<cos_true>={v['mean_cos_true_electron']:.4f} "
              f"rms(r-t)={v['rms_reco_minus_true']:.4f} corr={v['corr_reco_true']:.3f}",
              flush=True)

    J["_meta"] = {"seconds": time.time() - t0, "lmax": LMAX, "pa_bins": PA_BINS,
                  "n_probe": PROBE}
    (out / "pole_observables.json").write_text(json.dumps(J, indent=1))
    np.savez(out / "pole_observables.npz", coeffs_R=coeffs_R, coeffs_es=c_es, coeffs_cc=c_cc,
             pa_probe=pa_probe, probe=probe)
    print(f"\nwrote {out/'pole_observables.json'} ({time.time()-t0:.0f}s)")


def _eval_rows(rows, centers, cvals):
    c0, dc, nc = centers[0], centers[1] - centers[0], len(centers)
    t = (np.clip(cvals, c0, centers[-1]) - c0) / dc
    idx = np.clip(t.astype(np.int64), 0, nc - 2)
    fr = t - idx
    return (np.take_along_axis(rows, idx[:, None], 1)[:, 0] * (1 - fr)
            + np.take_along_axis(rows, (idx + 1)[:, None], 1)[:, 0] * fr)


def _coeffs(D3, E, ie, w, mask, lmax):
    return sh_coeffs(E["dirs"][ie][mask], lmax, weights=w[mask])


if __name__ == "__main__":
    main()
