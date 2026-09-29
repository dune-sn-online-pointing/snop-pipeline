#!/usr/bin/env python3
"""Calibrates the PART 2d observables: what does each mechanism actually predict?

`pole_observables.py` measures, on the real 722 evaluation cats, the burst-axis cos
distribution of true-ES events as a function of the burst direction's angle to the nearest
detector axis, and compares it with the multiplicative-acceptance model's own prediction.
A residual is only evidence if the two mechanisms predict measurably different residuals,
so this script runs the WHOLE measurement chain on synthetic data generated under each
mechanism, with the real burst directions, the real event counts and the real (E, CT, truth)
pool:

  1. generate reco directions -- "accept" (thinning by R) or "migrate" (drag towards the
     nearest axis by the transport map of pole_mc.py);
  2. MEASURE the ES table from the true-ES events of the synthetic slice, exactly as
     combo_tables does (so the double counting of R inside the measured table is emulated);
  3. MEASURE R from the true-CC reco directions of the synthetic slice;
  4. apply the same estimators as pole_observables: <cos> and Var(cos) vs the burst pole
     angle, observed against the acceptance-model prediction, and the class test on R.

A gate first checks that step 2 reproduces the real deployed ES table when run on the real
slice events.

Usage: python3 python/ana/pole_discrim.py --out <dir>
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
from ana.pole_mc import build_migration, migrate, sample_cos_from_rows, frame  # noqa: E402
from ana.pole_observables import weighted_moments, _eval_rows  # noqa: E402

CD = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/combo_study")
BD = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/brems_study")
ENERGY_BINS = np.array([(2, 4), (4, 6), (6, 8), (8, 10), (10, 12), (12, 14), (14, 16),
                        (16, 18), (18, 20), (20, 22), (22, 24), (24, 26), (26, 28),
                        (28, 30), (30, 35), (35, 40), (40, 50), (50, 70)], dtype=float)
LMAX, PDF_FLOOR, MIN_ROW = 6, 1e-4, 50
PA_BINS = [0, 10, 20, 30, 40, 54.8]
COS_EDGES = np.linspace(-1.0, 1.0, 101)
COS_CENTERS = 0.5 * (COS_EDGES[1:] + COS_EDGES[:-1])


def build_table(energy, cosv):
    """The combo_tables recipe: per-energy-bin histogram of cos, unit integral over cos,
    rows with < MIN_ROW events filled from the nearest measured row, then floor 1e-4 and
    renormalise (load_pdf_table)."""
    w = np.diff(COS_EDGES)
    pdf = np.zeros((len(ENERGY_BINS), len(COS_CENTERS)))
    meas = np.zeros(len(ENERGY_BINS), bool)
    for i, (lo, hi) in enumerate(ENERGY_BINS):
        m = (energy >= lo) & (energy < hi)
        if m.sum() >= MIN_ROW:
            h, _ = np.histogram(np.clip(cosv[m], -1, 1), bins=COS_EDGES)
            pdf[i] = h / (h.sum() * w)
            meas[i] = True
    idx = np.where(meas)[0]
    for i in range(len(ENERGY_BINS)):
        if not meas[i]:
            pdf[i] = pdf[idx[np.argmin(np.abs(idx - i))]]
    pdf = np.maximum(pdf, PDF_FLOOR)
    pdf = pdf / np.sum(pdf * w[None, :], axis=1, keepdims=True)
    return {"pdf": pdf, "energy_bins": ENERGY_BINS, "energy_centers": ENERGY_BINS.mean(axis=1),
            "cos_centers": COS_CENTERS, "cos_edges": COS_EDGES, "n_measured": int(meas.sum())}


def estimators(dirs, energy, cosv, is_es, burst, tab, coeffs, probe, pa_probe):
    """The pole_observables D1/D2/D3 estimators, given a measured table and a measured R."""
    es = is_es
    rows = pdf_rows_for_energies(tab, energy[es])
    lam = legendre_moments(rows, tab["cos_centers"], LMAX)
    a_l = weighted_moments(rows, tab["cos_centers"], LMAX, 1)
    b_l = weighted_moments(rows, tab["cos_centers"], LMAX, 2)
    rl = multipole_bands(coeffs, burst[es], LMAX).T
    Z = np.maximum((lam * rl).sum(axis=1), 1e-3)
    pred_c = (a_l * rl).sum(axis=1) / Z
    pred_c2 = (b_l * rl).sum(axis=1) / Z
    obs = cosv[es]
    pa = pole_angle(burst[es])
    out = {"bins": {}, "global_obs_mean": float(obs.mean()),
           "global_pred_mean": float(pred_c.mean())}
    for i in range(len(PA_BINS) - 1):
        m = (pa >= PA_BINS[i]) & (pa < PA_BINS[i + 1])
        if m.sum() < 50:
            continue
        n = int(m.sum())
        out["bins"][f"{PA_BINS[i]}-{PA_BINS[i+1]}"] = {
            "n_events": n,
            "obs_mean": float(obs[m].mean()),
            "obs_sem": float(obs[m].std(ddof=1) / sqrt(n)),
            "pred_mean": float(pred_c[m].mean()),
            "obs_std": float(obs[m].std(ddof=1)),
            "pred_std": float(sqrt(max(pred_c2[m].mean() - pred_c[m].mean() ** 2, 0.0))),
            "obs_minus_global": float(obs[m].mean() - obs.mean()),
            "pred_minus_global": float(pred_c[m].mean() - pred_c.mean())}
    for v in out["bins"].values():
        v["residual"] = v["obs_minus_global"] - v["pred_minus_global"]
        v["residual_in_sem"] = v["residual"] / v["obs_sem"]
    # D3 class test on R
    mi = _eval_rows(rows, tab["cos_centers"], obs)
    w = 1.0 / np.maximum(mi, 0.05)
    out["class_test"] = {}
    prof = {}
    for tag, m in (("near", pa < 25.0), ("far", pa > 35.0)):
        cf = sh_coeffs(dirs[es][m], LMAX, weights=w[m])
        r = band_density(cf, probe, LMAX)[0]
        prof[tag] = r
        out["class_test"][tag] = {
            "n_events": int(m.sum()),
            "mean_R_vs_pole_angle": {f"{PA_BINS[i]}-{PA_BINS[i+1]}":
                                     float(r[(pa_probe >= PA_BINS[i])
                                             & (pa_probe < PA_BINS[i + 1])].mean())
                                     for i in range(len(PA_BINS) - 1)},
            "contrast_near_over_far_poles": float(r[pa_probe < 10].mean()
                                                  / r[pa_probe > 40].mean())}
    out["class_test"]["near_minus_far_at_lt10deg"] = float(
        prof["near"][pa_probe < 10].mean() - prof["far"][pa_probe < 10].mean())
    out["R_measured_profile"] = {f"{PA_BINS[i]}-{PA_BINS[i+1]}":
                                 float(band_density(coeffs, probe, LMAX)[0][
                                     (pa_probe >= PA_BINS[i])
                                     & (pa_probe < PA_BINS[i + 1])].mean())
                                 for i in range(len(PA_BINS) - 1)}
    return out


def generate(mode, bursts, nsel, pool, kernel, coeffs, mig, Rmax, seed):
    rng = np.random.default_rng(seed)
    D, C, E_, S_, B_ = [], [], [], [], []
    for ib, n0 in enumerate(bursts):
        n_ev = int(nsel[ib])
        k = rng.integers(0, len(pool["E"]), size=n_ev)
        E, es = pool["E"][k], pool["es"][k]
        rows = pdf_rows_for_energies(kernel, E)
        e1, e2 = frame(n0)
        out = np.empty((n_ev, 3))
        todo = np.arange(n_ev)
        while len(todo):
            d = np.empty((len(todo), 3))
            isses = es[todo]
            if isses.any():
                ii = np.where(isses)[0]
                c = sample_cos_from_rows(rows[todo[ii]], kernel["cos_edges"], rng)
                ph = rng.random(len(ii)) * 2 * pi
                s = np.sqrt(np.maximum(0.0, 1 - c * c))
                d[ii] = (c[:, None] * n0[None, :]
                         + s[:, None] * (np.cos(ph)[:, None] * e1[None, :]
                                         + np.sin(ph)[:, None] * e2[None, :]))
            if (~isses).any():
                jj = np.where(~isses)[0]
                v = rng.normal(size=(len(jj), 3))
                d[jj] = v / np.linalg.norm(v, axis=1, keepdims=True)
            if mode == "accept":
                keep = rng.random(len(todo)) < (band_density(coeffs, d, LMAX)[0] / Rmax)
            else:
                d = migrate(d, mig)
                keep = np.ones(len(todo), bool)
            out[todo[keep]] = d[keep]
            todo = todo[~keep]
        D.append(out)
        C.append(np.clip(out @ n0, -1, 1))
        E_.append(E)
        S_.append(es)
        B_.append(np.repeat(n0[None, :], n_ev, 0))
    return (np.vstack(D), np.concatenate(C), np.concatenate(E_), np.concatenate(S_),
            np.vstack(B_))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    J = {}
    probe = fib_grid(60000)
    pa_probe = pole_angle(probe)

    # ------------------------------------------------------------- real slice: pool, R, table
    S = load_collect(str(BD / "collect_673_900.npz"), 673, 900)
    ssel = (S["ct"] >= 0.50) & (S["e_reco"] > 5.0)
    pool = {"E": S["e_reco"][ssel], "es": (S["is_es"][ssel] == 1)}
    coeffs_R = sh_coeffs(S["dirs"][ssel & (S["is_es"] != 1)], LMAX)
    Rmax = float(band_density(coeffs_R, fib_grid(400000), LMAX)[0].max()) * 1.02
    mig = build_migration(coeffs_R)

    # gate: my table builder on the real slice vs the deployed table
    tab_real = build_table(S["e_reco"][ssel & (S["is_es"] == 1)],
                           S["cos_burst"][ssel & (S["is_es"] == 1)])
    tab_dep = load_pdf_table(str(CD / "tables" / "combo_slice_t050_full.npz"),
                             pdf_floor=PDF_FLOOR)
    J["table_builder_gate"] = {
        "max_abs_dpdf": float(np.max(np.abs(tab_real["pdf"] - tab_dep["pdf"]))),
        "max_rel_dpdf": float(np.max(np.abs(tab_real["pdf"] - tab_dep["pdf"])
                                     / np.maximum(tab_dep["pdf"], 1e-6))),
        "n_rows_measured": tab_real["n_measured"]}
    print("table gate:", J["table_builder_gate"], flush=True)

    # ------------------------------------------------------------- real evaluation estimators
    E = load_collect(str(BD / "collect_eval_slimonly.npz"))
    sel = (E["ct"] >= 0.50) & (E["e_reco"] > 5.0)
    b = np.column_stack([E["bx"], E["by"], E["bz"]])
    b = b / np.linalg.norm(b, axis=1, keepdims=True)
    J["real"] = estimators(E["dirs"][sel], E["e_reco"][sel], E["cos_burst"][sel],
                           E["is_es"][sel] == 1, b[sel], tab_dep, coeffs_R, probe, pa_probe)
    # the real bursts and event counts, for the synthetic ensembles
    cats = np.unique(E["cat"][sel]).astype(int)
    bursts, nsel = [], []
    for c in cats:
        m = sel & (E["cat"] == c)
        bursts.append(b[m][0])
        nsel.append(int(m.sum()))
    bursts = np.array(bursts)
    nsel = np.array(nsel)
    print(f"real: {sel.sum()} selected in {len(cats)} cats", flush=True)

    # ------------------------------------------------------------------------ synthetic modes
    for mode, seed in (("accept", 21), ("migrate", 22)):
        d, cv, en, es, bu = generate(mode, bursts, nsel, pool, tab_dep, coeffs_R, mig,
                                     Rmax, seed)
        tab_m = build_table(en[es], cv[es])
        coeffs_m = sh_coeffs(d[~es], LMAX)
        J[mode] = estimators(d, en, cv, es, bu, tab_m, coeffs_m, probe, pa_probe)
        J[mode]["n_events"] = int(len(cv))
        J[mode]["measured_table_vs_generation_kernel_max_abs_dpdf"] = float(
            np.max(np.abs(tab_m["pdf"] - tab_dep["pdf"])))
        print(f"{mode}: {len(cv)} events, {time.time()-t0:.0f}s", flush=True)

    # -------------------------------------------------------------------------------- summary
    print(f"\n{'bin':>10} " + " ".join(f"{k:>26}" for k in ("real", "accept", "migrate")))
    print(f"{'':>10} " + " ".join(f"{'obs    pred   resid':>26}" for _ in range(3)))
    for k in J["real"]["bins"]:
        line = f"{k:>10} "
        for tag in ("real", "accept", "migrate"):
            v = J[tag]["bins"][k]
            line += f" {v['obs_mean']:6.4f} {v['pred_mean']:6.4f} {v['residual']:+7.4f}  "
        print(line)
    print(f"\n{'bin':>10} " + " ".join(f"{k:>24}" for k in ("real", "accept", "migrate")))
    print(f"{'':>10} " + " ".join(f"{'obs_std   pred_std':>24}" for _ in range(3)))
    for k in J["real"]["bins"]:
        line = f"{k:>10} "
        for tag in ("real", "accept", "migrate"):
            v = J[tag]["bins"][k]
            line += f" {v['obs_std']:8.4f} {v['pred_std']:8.4f}   "
        print(line)
    print("\nclass test: <R_eff> at pole angle < 10 deg, near-pointing minus far-pointing")
    for tag in ("real", "accept", "migrate"):
        print(f"  {tag:>8}: {J[tag]['class_test']['near_minus_far_at_lt10deg']:+.4f} "
              f"(near {J[tag]['class_test']['near']['contrast_near_over_far_poles']:.3f}, "
              f"far {J[tag]['class_test']['far']['contrast_near_over_far_poles']:.3f})")
    (out / "pole_discrim.json").write_text(json.dumps(J, indent=1))
    print(f"\nwrote {out/'pole_discrim.json'} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
