#!/usr/bin/env python3
"""PART 2a + figures + the merged pole_dependence.json.

Bins the 722 evaluation cats by the angle between the TRUE burst direction and the nearest
of the six detector axes (0-54.74 deg) and, per bin and per arm, reports theta68 (with a
paired-bootstrap CI), the median, the SIGNED RADIAL BIAS with respect to that same axis
(positive = pushed away from the axis) against the geometric expectation of an unbiased
estimator with the same error size, and the fraction of cats that improved.

Reads   pole_refit.npz, pole_mc.json, pole_observables.json, pole_derive.json
Writes  pole_dependence.json, pole_*.png

Usage: python3 python/ana/pole_analysis.py --out <dir>
"""
import argparse
import json
import sys
from math import sqrt
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from ana.pole_common import POLES, band_density, fib_grid, pole_angle  # noqa: E402

ARMS = ["CUR_t080_gf_flat", "DEC_t050_noR", "GATE_A_t050_map41k", "CMB2_t050_accCC_ccl6"]
LABEL = {"CUR_t080_gf_flat": "CUR (deployed, t=0.80, flat CC)",
         "DEC_t050_noR": "DEC (t=0.50, no correction)",
         "GATE_A_t050_map41k": "GATE_A (CC map only)",
         "CMB2_t050_accCC_ccl6": "CMB2 (recommended, -log Z)"}
COL = {"CUR_t080_gf_flat": "#777777", "DEC_t050_noR": "#1f77b4",
       "GATE_A_t050_map41k": "#ff7f0e", "CMB2_t050_accCC_ccl6": "#d62728"}
BINS_MAIN = [0.0, 18.0, 28.0, 38.0, 54.8]
BINS_FINE = [0.0, 10.0, 20.0, 30.0, 40.0, 54.8]
LMAX = 6


def theta68(cos):
    return float(np.degrees(np.arccos(np.clip(np.quantile(cos, 0.32), -1.0, 1.0))))


def boot_ci(cos, n=2000, seed=5):
    rng = np.random.default_rng(seed)
    v = [theta68(cos[rng.integers(0, len(cos), len(cos))]) for _ in range(n)]
    return [float(np.quantile(v, 0.16)), float(np.quantile(v, 0.84))]


def signed_radial(truth, reco):
    k = np.argmax(truth @ POLES.T, axis=1)
    p = POLES[k]
    at = np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", truth, p), -1, 1)))
    ar = np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", reco, p), -1, 1)))
    return ar - at


def geometric_bias(truth, theta_deg, rng, nrep=200):
    """Radial bias of an UNBIASED estimator with the same per-burst error size."""
    out = np.empty(truth.shape[0])
    for i in range(truth.shape[0]):
        t = truth[i]
        a0 = np.array([0.0, 0.0, 1.0]) if abs(t[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        e1 = np.cross(t, a0)
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(t, e1)
        a = np.radians(theta_deg[i])
        ph = rng.random(nrep) * 2 * np.pi
        r = (np.cos(a) * t[None, :]
             + np.sin(a) * (np.cos(ph)[:, None] * e1[None, :]
                            + np.sin(ph)[:, None] * e2[None, :]))
        out[i] = signed_radial(np.repeat(t[None, :], nrep, 0), r).mean()
    return out


def bin_table(Z, bins, rng):
    truth = Z["truth"]
    pa = pole_angle(truth)
    T = {"bin_edges": bins, "bins": {}}
    for i in range(len(bins) - 1):
        m = (pa >= bins[i]) & (pa < bins[i + 1])
        key = f"{bins[i]:g}-{bins[i+1]:g}"
        row = {"n_cats": int(m.sum()),
               "mean_pole_angle": float(pa[m].mean()) if m.any() else float("nan")}
        if m.sum() < 5:
            T["bins"][key] = row
            continue
        for arm in ARMS:
            c = Z[f"cos_{arm}"][m]
            rc = Z[f"reco_{arm}"][m]
            ok = np.isfinite(c)
            th = np.degrees(np.arccos(np.clip(c[ok], -1, 1)))
            sr = signed_radial(truth[m][ok], rc[ok])
            gb = geometric_bias(truth[m][ok], th, rng)
            row[arm] = {
                "theta68": theta68(c[ok]), "theta68_ci68": boot_ci(c[ok]),
                "median": float(np.median(th)), "mean": float(th.mean()),
                "mean_sem": float(th.std(ddof=1) / sqrt(ok.sum())),
                "frac_gt30": float(np.mean(th > 30)),
                "radial_bias_mean": float(sr.mean()),
                "radial_bias_sem": float(sr.std(ddof=1) / sqrt(ok.sum())),
                "radial_bias_geom_expected": float(gb.mean()),
                "radial_bias_excess": float(sr.mean() - gb.mean()),
                "radial_bias_excess_sem": float(sr.std(ddof=1) / sqrt(ok.sum())),
                "mean_nsel": float(Z[f"nsel_{arm}"][m].mean()),
                "coverage": float(theta68(c[ok]) / np.median(Z[f"q68_{arm}"][m][ok])),
            }
        for ref in ("DEC_t050_noR", "GATE_A_t050_map41k", "CUR_t080_gf_flat"):
            a = np.degrees(np.arccos(np.clip(Z["cos_CMB2_t050_accCC_ccl6"][m], -1, 1)))
            bb = np.degrees(np.arccos(np.clip(Z[f"cos_{ref}"][m], -1, 1)))
            row[f"CMB2_vs_{ref}"] = {
                "d_theta68": row["CMB2_t050_accCC_ccl6"]["theta68"] - row[ref]["theta68"],
                "d_mean": float((a - bb).mean()),
                "d_mean_sem": float((a - bb).std(ddof=1) / sqrt(len(a))),
                "d_median": float(np.median(a - bb)),
                "frac_improved": float(np.mean(a < bb))}
        T["bins"][key] = row
    return T


def fig_R(out, coeffs):
    probe = fib_grid(200000)
    r = band_density(coeffs, probe, LMAX)[0]
    pa = pole_angle(probe)
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    e = np.linspace(0, 54.7356, 40)
    c = 0.5 * (e[1:] + e[:-1])
    prof = [r[(pa >= e[i]) & (pa < e[i + 1])].mean() for i in range(len(e) - 1)]
    ax[0].plot(c, prof, "k-", lw=2)
    ax[0].axhline(1.0, color="grey", ls=":")
    ax[0].set_xlabel("angle of the reco direction to the nearest axis [deg]")
    ax[0].set_ylabel(r"$\langle R\rangle$")
    ax[0].set_title("measured acceptance, $l\\leq6$, from slice true-CC reco dirs")
    ax[0].grid(alpha=0.3)
    # Mollweide of R
    th = np.arcsin(np.clip(probe[:, 2], -1, 1))
    ph = np.arctan2(probe[:, 1], probe[:, 0])
    sub = np.random.default_rng(0).choice(len(r), 60000, replace=False)
    ax[1].remove()
    ax2 = fig.add_subplot(1, 2, 2, projection="mollweide")
    sc = ax2.scatter(ph[sub], th[sub], c=r[sub], s=1.2, cmap="RdBu_r", vmin=0.1, vmax=1.9)
    for p, nm in zip(POLES, ["+x", "-x", "+y", "-y", "+z", "-z"]):
        ax2.plot(np.arctan2(p[1], p[0]), np.arcsin(p[2]), "k+", ms=9)
        ax2.text(np.arctan2(p[1], p[0]), np.arcsin(p[2]), " " + nm, fontsize=7)
    ax2.set_title("$R(d)$ in the detector frame")
    ax2.grid(alpha=0.3)
    fig.colorbar(sc, ax=ax2, shrink=0.75)
    fig.tight_layout()
    fig.savefig(out / "pole_R_map.png", dpi=140)
    plt.close(fig)


def fig_real(out, T, Tf):
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.4))
    keys = list(Tf["bins"])
    x = [Tf["bins"][k]["mean_pole_angle"] for k in keys]
    for arm in ARMS:
        y = [Tf["bins"][k][arm]["theta68"] for k in keys]
        lo = [Tf["bins"][k][arm]["theta68_ci68"][0] for k in keys]
        hi = [Tf["bins"][k][arm]["theta68_ci68"][1] for k in keys]
        ax[0].errorbar(x, y, yerr=[np.array(y) - lo, np.array(hi) - np.array(y)],
                       marker="o", color=COL[arm], label=LABEL[arm], capsize=3)
        ax[1].plot(x, [Tf["bins"][k][arm]["radial_bias_mean"] for k in keys], "o-",
                   color=COL[arm], label=LABEL[arm])
        ax[1].plot(x, [Tf["bins"][k][arm]["radial_bias_geom_expected"] for k in keys], "--",
                   color=COL[arm], alpha=0.5, lw=1)
    ax[0].set_xlabel("angle(true burst dir, nearest axis) [deg]")
    ax[0].set_ylabel(r"$\theta_{68}$ [deg]")
    ax[0].legend(fontsize=7)
    ax[0].grid(alpha=0.3)
    ax[0].set_title("722 evaluation cats")
    ax[1].axhline(0, color="k", lw=0.8)
    ax[1].set_xlabel("angle(true burst dir, nearest axis) [deg]")
    ax[1].set_ylabel("signed radial bias [deg]\n(+ = pushed away from the axis)")
    ax[1].legend(fontsize=7)
    ax[1].grid(alpha=0.3)
    ax[1].set_title("solid = measured, dashed = geometric expectation")
    for arm, ref in (("CMB2_t050_accCC_ccl6", "DEC_t050_noR"),):
        ax[2].plot(x, [Tf["bins"][k][f"CMB2_vs_{ref}"]["frac_improved"] for k in keys],
                   "o-", color="#d62728", label="frac improved vs DEC (no correction)")
        ax[2].plot(x, [Tf["bins"][k][f"CMB2_vs_{ref}"]["d_theta68"] / 20 + 0.5 for k in keys],
                   "s--", color="#2ca02c",
                   label=r"$\Delta\theta_{68}$/20 + 0.5 vs DEC")
    ax[2].axhline(0.5, color="k", lw=0.8)
    ax[2].set_ylim(0, 1)
    ax[2].set_xlabel("angle(true burst dir, nearest axis) [deg]")
    ax[2].legend(fontsize=7)
    ax[2].grid(alpha=0.3)
    ax[2].set_title("does the correction help in every bin?")
    fig.tight_layout()
    fig.savefig(out / "pole_real_bins.png", dpi=140)
    plt.close(fig)


def fig_mc(out, MC):
    modes = [m for m in ("accept", "migrate", "migself") if m in MC["results"]]
    fig, ax = plt.subplots(len(modes), 3, figsize=(15, 4 * len(modes)),
                           squeeze=False)
    for r, mode in enumerate(modes):
        keys = list(MC["results"][mode])
        x = [float(k) for k in keys]
        no = [MC["results"][mode][k]["without"]["theta68"] for k in keys]
        wi = [MC["results"][mode][k]["with"]["theta68"] for k in keys]
        ax[r, 0].plot(x, no, "o-", color="#1f77b4", label="without $-\\log Z$")
        ax[r, 0].plot(x, wi, "s-", color="#d62728", label="with $-\\log Z$")
        ax[r, 0].set_ylabel(r"$\theta_{68}$ [deg]")
        ax[r, 0].set_title(f"{mode}: resolution")
        bn = [MC["results"][mode][k]["without"]["radial_bias_excess"] for k in keys]
        bw = [MC["results"][mode][k]["with"]["radial_bias_excess"] for k in keys]
        en = [MC["results"][mode][k]["without"]["radial_bias_sem"] for k in keys]
        ew = [MC["results"][mode][k]["with"]["radial_bias_sem"] for k in keys]
        ax[r, 1].errorbar(x, bn, yerr=en, marker="o", color="#1f77b4",
                          label="without", capsize=3)
        ax[r, 1].errorbar(x, bw, yerr=ew, marker="s", color="#d62728",
                          label="with", capsize=3)
        ax[r, 1].axhline(0, color="k", lw=0.8)
        ax[r, 1].set_ylabel("excess radial bias [deg]")
        ax[r, 1].set_title(f"{mode}: push away from the axis")
        ax[r, 2].plot(x, [MC["results"][mode][k]["d_theta68"] for k in keys], "o-", color="k")
        ax[r, 2].axhline(0, color="k", lw=0.8)
        ax[r, 2].set_ylabel(r"$\Delta\theta_{68}$ (with $-$ without) [deg]")
        ax[r, 2].set_title(f"{mode}: gain (<0 = the term helps)")
        for c in range(3):
            ax[r, c].set_xlabel("burst angle to the nearest axis [deg]")
            ax[r, c].grid(alpha=0.3)
            ax[r, c].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(out / "pole_mc.png", dpi=140)
    plt.close(fig)


def fig_obs(out, OB):
    D2 = OB["D2_model_prediction"]["bins"]
    keys = list(D2)
    x = [np.mean([float(v) for v in k.split("-")]) for k in keys]
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.4))
    ax[0].errorbar(x, [D2[k]["obs_mean_cos_reco"] for k in keys],
                   yerr=[D2[k]["obs_sem_cos_reco"] for k in keys], marker="o",
                   color="#d62728", label="measured, reco dir", capsize=3)
    ax[0].plot(x, [D2[k]["pred_mean_cos_reco_acceptance"] for k in keys], "s--",
               color="k", label="acceptance-model prediction")
    ax[0].errorbar(x, [D2[k]["obs_mean_cos_true_electron"] for k in keys],
                   yerr=[D2[k]["obs_sem_cos_true_electron"] for k in keys], marker="^",
                   color="#1f77b4", label="measured, TRUE electron dir", capsize=3)
    ax[0].set_xlabel("burst angle to the nearest axis [deg]")
    ax[0].set_ylabel(r"$\langle\cos(d,\,n_{\rm burst})\rangle$, true ES")
    ax[0].legend(fontsize=7)
    ax[0].grid(alpha=0.3)
    ax[0].set_title("D2: is the pile-up a reweighting or a drag?")
    ax[1].errorbar(x, [D2[k]["residual_obs_minus_pred"] for k in keys],
                   yerr=[D2[k]["obs_sem_cos_reco"] for k in keys], marker="o",
                   color="#d62728", capsize=3)
    ax[1].axhline(0, color="k", lw=0.8)
    ax[1].set_xlabel("burst angle to the nearest axis [deg]")
    ax[1].set_ylabel("residual (measured $-$ predicted)")
    ax[1].grid(alpha=0.3)
    ax[1].set_title("D2 residual of the multiplicative model")
    D3 = OB["D3_class_test"]["classes"]
    bk = list(D3["all"]["mean_R_vs_pole_angle"])
    bx = [np.mean([float(v) for v in k.split("-")]) for k in bk]
    for tag, st, cl in (("burst_pole_lt25", "o-", "#d62728"),
                        ("burst_pole_gt35", "s-", "#1f77b4"), ("all", "^:", "k")):
        ax[2].plot(bx, [D3[tag]["mean_R_vs_pole_angle"][k] for k in bk], st, color=cl,
                   label=f"ES, {tag} (n={D3[tag]['n_events']})")
    ax[2].plot(bx, [OB["R_reference"]["mean_R_vs_pole_angle"][k] for k in bk], "d--",
               color="#2ca02c", label="R from true CC (deployed)")
    ax[2].set_xlabel("angle of the reco direction to the nearest axis [deg]")
    ax[2].set_ylabel(r"$\langle R_{\rm eff}\rangle$")
    ax[2].legend(fontsize=7)
    ax[2].grid(alpha=0.3)
    ax[2].set_title("D3: is R the same for near- and far-pointing bursts?")
    fig.tight_layout()
    fig.savefig(out / "pole_observables.png", dpi=140)
    plt.close(fig)


def fig_energy(out, OB):
    D4 = OB["D4_energy"]["bins"]
    keys = [k for k in D4 if k != "5-25"]
    x = [np.mean([float(v) for v in k.split("-")]) for k in keys]
    fig, ax = plt.subplots(1, 2, figsize=(10.5, 4.2))
    ax[0].errorbar(x, [D4[k]["contrast_R_near_over_far"] for k in keys],
                   yerr=[D4[k]["noise_floor"][4] for k in keys], marker="o", color="k",
                   capsize=3)
    ax[0].axhline(1.0, color="grey", ls=":")
    ax[0].set_xlabel("reco energy [MeV]")
    ax[0].set_ylabel(r"$\langle R\rangle_{<10^\circ}/\langle R\rangle_{>40^\circ}$")
    ax[0].set_title("D4: pile-up strength vs energy (true CC)")
    ax[0].grid(alpha=0.3)
    for l in (2, 4, 6):
        ax[1].plot(x, [D4[k]["rms_R_l"][l] for k in keys], "o-", label=f"$l={l}$")
        ax[1].plot(x, [D4[k]["noise_floor"][l] for k in keys], ":", alpha=0.5)
    ax[1].set_xlabel("reco energy [MeV]")
    ax[1].set_ylabel("rms $R_l$ over the sphere")
    ax[1].set_title("multipole content vs energy (dotted = noise floor)")
    ax[1].legend(fontsize=8)
    ax[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out / "pole_energy.png", dpi=140)
    plt.close(fig)


def fig_discrim(out, DS):
    """The D2 estimator run through the whole chain under each mechanism."""
    keys = list(DS["real"]["bins"])
    x = [np.mean([float(v) for v in k.split("-")]) for k in keys]
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.3))
    style = {"real": ("o-", "#d62728", "REAL 722 cats"),
             "accept": ("s--", "#2ca02c", "MC: pure acceptance (model true)"),
             "migrate": ("^:", "#1f77b4", "MC: migration (same marginal)")}
    for tag, (st, cl, lb) in style.items():
        if tag not in DS:
            continue
        ax[0].errorbar(x, [DS[tag]["bins"][k]["residual"] for k in keys],
                       yerr=[DS[tag]["bins"][k]["obs_sem"] for k in keys],
                       fmt=st, color=cl, label=lb, capsize=3)
        ax[1].plot(x, [DS[tag]["bins"][k]["obs_std"] - DS[tag]["bins"][k]["pred_std"]
                       for k in keys], st, color=cl, label=lb)
    for a, t, yl in ((ax[0], r"$\langle\cos\rangle$ residual: measured $-$ acceptance model",
                      "residual"),
                     (ax[1], r"width residual: ${\rm std}_{\rm obs}-{\rm std}_{\rm pred}$",
                      "residual of std(cos)")):
        a.axhline(0, color="k", lw=0.8)
        a.set_xlabel("burst angle to the nearest axis [deg]")
        a.set_ylabel(yl)
        a.set_title(t, fontsize=9)
        a.legend(fontsize=7)
        a.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out / "pole_discrim.png", dpi=140)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = Path(args.out)
    Z = dict(np.load(out / "pole_refit.npz", allow_pickle=True))
    rng = np.random.default_rng(17)
    J = {"part1_derivation": json.loads((out / "pole_derive.json").read_text())}
    gate = json.loads((out / "pole_refit_gate.json").read_text())
    J["part1_reproduction_gate"] = gate
    pa = pole_angle(Z["truth"])
    J["part2a_real_722"] = {
        "pole_angle_distribution": {"mean": float(pa.mean()),
                                    "quantiles_10_25_50_75_90":
                                        [float(q) for q in
                                         np.quantile(pa, [0.1, 0.25, 0.5, 0.75, 0.9])],
                                    "n_lt_10deg": int((pa < 10).sum()),
                                    "n_lt_20deg": int((pa < 20).sum())},
        "overall": {arm: {"theta68": theta68(Z[f"cos_{arm}"]),
                          "median": float(np.median(np.degrees(np.arccos(
                              np.clip(Z[f"cos_{arm}"], -1, 1)))))} for arm in ARMS},
        "bins_main": bin_table(Z, BINS_MAIN, rng),
        "bins_fine": bin_table(Z, BINS_FINE, rng)}
    for f, key in (("pole_mc.json", "part2bc_monte_carlo"),
                   ("pole_observables.json", "part2d_observables"),
                   ("pole_discrim.json", "part2d_discrimination"),
                   ("pole_mc_crosscheck.json", "part2bc_fitter_crosscheck")):
        p = out / f
        if p.exists():
            J[key] = json.loads(p.read_text())
    (out / "pole_dependence.json").write_text(json.dumps(J, indent=1))

    # ------------------------------------------------------------------------------ figures
    fig_R(out, Z["coeffs"])
    fig_real(out, J["part2a_real_722"]["bins_main"], J["part2a_real_722"]["bins_fine"])
    if "part2bc_monte_carlo" in J:
        fig_mc(out, J["part2bc_monte_carlo"])
    if "part2d_observables" in J:
        fig_obs(out, J["part2d_observables"])
        fig_energy(out, J["part2d_observables"])
    if "part2d_discrimination" in J:
        fig_discrim(out, J["part2d_discrimination"])

    # ------------------------------------------------------------------------------ printout
    for tag, T in (("MAIN", J["part2a_real_722"]["bins_main"]),
                   ("FINE", J["part2a_real_722"]["bins_fine"])):
        print(f"\n=== {tag} bins: theta68 / median ===")
        hdr = f"{'bin':>12} {'n':>4} " + " ".join(f"{a.split('_')[0]:>16}" for a in ARMS)
        print(hdr)
        for k, row in T["bins"].items():
            if ARMS[0] not in row:
                continue
            print(f"{k:>12} {row['n_cats']:>4} " + " ".join(
                f"{row[a]['theta68']:7.2f}/{row[a]['median']:<8.2f}" for a in ARMS))
        print(f"\n=== {tag} bins: signed radial bias (measured / geometric / excess) ===")
        for k, row in T["bins"].items():
            if ARMS[0] not in row:
                continue
            print(f"{k:>12} " + " ".join(
                f"{a.split('_')[0]:>6}:{row[a]['radial_bias_mean']:+6.2f}"
                f"({row[a]['radial_bias_geom_expected']:+5.2f})"
                f"[{row[a]['radial_bias_excess']:+5.2f}+-{row[a]['radial_bias_sem']:.2f}]"
                for a in ARMS))
        print(f"\n=== {tag} bins: CMB2 vs DEC (no correction) ===")
        for k, row in T["bins"].items():
            if ARMS[0] not in row:
                continue
            v = row["CMB2_vs_DEC_t050_noR"]
            print(f"{k:>12} n={row['n_cats']:>4} d_theta68={v['d_theta68']:+6.2f} "
                  f"d_mean={v['d_mean']:+6.2f}+-{v['d_mean_sem']:.2f} "
                  f"frac_improved={v['frac_improved']:.3f}")
    print(f"\nwrote {out/'pole_dependence.json'} and pole_*.png")


if __name__ == "__main__":
    main()
