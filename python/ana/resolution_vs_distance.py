#!/usr/bin/env python3
"""Pointing resolution of the deployed configuration versus supernova distance.

The campaign bursts hold the first 330 ES + 3300 CC GENERATED events (sample_loader's
generated-event budget), the GKVM yield of a 40 kt DUNE far detector at 10 kpc (tech note).
A supernova at d kpc gives N(d) = N(10) (10/d)^2 events of BOTH classes, which the replay
emulates by keeping a random fraction F = (10/d)^2 of the generated ES and, independently, of the
generated CC events before the unchanged scenario-8 selection and fit
(`replay_scenario_from_slim.py --keep-fraction`, condor/distance_replay/).  d = 10 kpc is the
existing untrimmed result (`v63_matchfix_1000_acc_t030`).  722 evaluation cats only.

Per distance and draw: theta68 = degrees(arccos(quantile(cos_to_truth, 0.32))) over the 722 cats
with a 68% bootstrap interval, median, frac>30, mean n_selected.  Pooled over the 3 draws:
mean theta68, the spread of the draws, and the mean per-draw bootstrap interval.

Usage:
  python3 python/ana/resolution_vs_distance.py [--dist-root ...] [--out-dir ...]
"""
import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

PC = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-campaign")
BASE = PC / "v63_matchfix_1000_acc_t030"
DIST = PC / "v63_matchfix_1000_acc_t030_distance"
SCEN = "scenario_8_full_pipeline_acc_t030"
EVAL = [(2, 399), (901, 1224)]
DISTANCES = [10, 11, 12, 13, 14, 15]
FAR_DISTANCES = [20, 25, 30, 40, 50]
FAR_F = {20: 0.25, 25: 0.16, 30: 0.111111, 40: 0.0625, 50: 0.04}   # F values as submitted
N_GEN_ES, N_GEN_CC = 330, 3300


def in_eval(n):
    return any(lo <= n <= hi for lo, hi in EVAL)


def theta68(cos):
    return float(np.degrees(np.arccos(np.clip(np.quantile(np.asarray(cos), 0.32), -1, 1))))


def stats(cos, nsel, nes, rng, n_boot):
    cos = np.asarray(cos, dtype=np.float64)
    th = np.degrees(np.arccos(np.clip(cos, -1, 1)))
    boots = np.array([theta68(cos[rng.integers(0, cos.size, cos.size)]) for _ in range(n_boot)])
    lo, hi = np.percentile(boots, [16, 84])
    t = theta68(cos)
    return {"N": int(cos.size), "theta68": t, "theta68_lo": float(lo), "theta68_hi": float(hi),
            "sky_frac": float((1 - np.cos(np.radians(t))) / 2),
            "median": float(np.median(th)), "frac_gt30": float(np.mean(th > 30)),
            "theta90": float(np.degrees(np.arccos(np.clip(np.quantile(cos, 0.10), -1, 1)))),
            "mean_n_selected": float(np.mean(nsel)),
            "mean_true_es_in_fit": float(np.mean(nes)) if nes is not None else None}


def load_base():
    out = {}
    for f in sorted(BASE.glob("cat*/scenario_cos_theta_report.json")):
        n = int(f.parent.name[3:])
        if not in_eval(n):
            continue
        for s in json.loads(f.read_text()).get("scenarios", []):
            if s.get("scenario") == SCEN:
                out[n] = (float(s["cos_to_truth"]), int(s["n_selected"]),
                          int(s.get("n_true_es_used", -1)))
    return out


def load_trimmed(root):
    rows, errors, files = [], [], sorted(Path(root).glob("chunk_*.json"))
    for f in files:
        d = json.loads(f.read_text())
        rows.extend(d["rows"])
        errors.extend(d.get("errors", []))
    return rows, errors, [str(f) for f in files]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist-root", default=str(DIST))
    ap.add_argument("--out-dir", default=str(DIST))
    ap.add_argument("--far-root", default=str(DIST / "far"),
                    help="chunks for 20-50 kpc (condor/distance_replay/submit_distance_far.sub)")
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=2024)
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    out = Path(args.out_dir)

    base = load_base()
    assert len(base) == 722, len(base)
    rows, errors, files = load_trimmed(args.dist_root)
    fr_of_d = {d: (10.0 / d) ** 2 for d in DISTANCES}

    res = {10: {"F": 1.0, "n_gen_es": N_GEN_ES, "n_gen_cc": N_GEN_CC, "draws": {}}}
    c = [base[n][0] for n in sorted(base)]
    res[10]["draws"]["untrimmed"] = stats(c, [base[n][1] for n in sorted(base)],
                                          [base[n][2] for n in sorted(base)], rng, args.n_boot)
    coverage = {}
    for d in DISTANCES[1:]:
        F = fr_of_d[d]
        sel = [r for r in rows if abs(r["keep_fraction"] - F) < 5e-6 and in_eval(int(r["cat"]))]
        seeds = sorted({int(r["trim_seed"]) for r in sel})
        res[d] = {"F": F, "n_gen_es": int(np.floor(F * N_GEN_ES + 0.5)),
                  "n_gen_cc": int(np.floor(F * N_GEN_CC + 0.5)), "draws": {}}
        for s in seeds:
            rs = sorted((r for r in sel if int(r["trim_seed"]) == s), key=lambda r: r["cat"])
            coverage[(d, s)] = len(rs)
            res[d]["draws"][str(s)] = stats([r["cos_to_truth"] for r in rs],
                                            [r["n_selected"] for r in rs],
                                            [r.get("n_true_es_used", np.nan) for r in rs],
                                            rng, args.n_boot)
            res[d]["draws"][str(s)]["mean_reco_es_kept"] = float(np.mean([r["n_reco_es_kept"] for r in rs]))
            res[d]["draws"][str(s)]["mean_reco_cc_kept"] = float(np.mean([r["n_reco_cc_kept"] for r in rs]))
    # pooled over draws
    summary = []
    for d in DISTANCES:
        dr = list(res[d]["draws"].values())
        t = np.array([x["theta68"] for x in dr])
        row = {"d_kpc": d, "F": res[d]["F"], "n_gen_es": res[d]["n_gen_es"],
               "n_gen_cc": res[d]["n_gen_cc"], "n_draws": len(dr),
               "n_cats": [x["N"] for x in dr],
               "theta68_mean": float(t.mean()),
               "theta68_draw_spread_std": float(t.std(ddof=1)) if t.size > 1 else 0.0,
               "theta68_draw_min": float(t.min()), "theta68_draw_max": float(t.max()),
               "theta68_boot_lo_mean": float(np.mean([x["theta68_lo"] for x in dr])),
               "theta68_boot_hi_mean": float(np.mean([x["theta68_hi"] for x in dr])),
               "median_mean": float(np.mean([x["median"] for x in dr])),
               "theta90_mean": float(np.mean([x["theta90"] for x in dr])),
               "frac_gt30_mean": float(np.mean([x["frac_gt30"] for x in dr])),
               "mean_n_selected": float(np.mean([x["mean_n_selected"] for x in dr])),
               "mean_true_es_in_fit": float(np.mean([x["mean_true_es_in_fit"] for x in dr])),
               "sky_frac_mean": float(np.mean([x["sky_frac"] for x in dr]))}
        row["theta68_boot_halfwidth"] = 0.5 * (row["theta68_boot_hi_mean"] - row["theta68_boot_lo_mean"])
        row["theta68_total_err"] = float(np.hypot(row["theta68_boot_halfwidth"],
                                                  row["theta68_draw_spread_std"]))
        summary.append(row)

    # a + b/sqrt(N) least squares on the pooled means (reference line only)
    x = np.array([1 / np.sqrt(r["n_gen_es"]) for r in summary])
    y = np.array([r["theta68_mean"] for r in summary])
    w = 1 / np.array([max(r["theta68_total_err"], 1e-3) for r in summary]) ** 2
    A = np.column_stack([np.ones_like(x), x])
    coef = np.linalg.solve(A.T @ (A * w[:, None]), A.T @ (w * y))
    prop = y[0] * np.sqrt(np.array([r["n_gen_es"] for r in summary]) ** -1.0 * summary[0]["n_gen_es"])

    # ------------------------------------------------------------------ figure
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(7.2, 7.6), sharex=True,
                                  gridspec_kw={"height_ratios": [2.2, 1], "hspace": 0.06})
    lo = np.array([r["theta68_boot_lo_mean"] for r in summary])
    hi = np.array([r["theta68_boot_hi_mean"] for r in summary])
    ax.fill_between(x, lo, hi, color="#1f77b4", alpha=0.25, lw=0,
                    label="68% bootstrap band (mean over draws)")
    ax.errorbar(x, y, yerr=[r["theta68_draw_spread_std"] for r in summary], fmt="o-",
                color="#1f77b4", capsize=3,
                label=r"$\theta_{68}$, mean of 3 trimming draws ($\pm$ draw spread)")
    for r, xi in zip(summary[1:], x[1:]):
        for dr in res[r["d_kpc"]]["draws"].values():
            ax.plot(xi, dr["theta68"], "_", color="#1f77b4", ms=9, alpha=0.8)
    ax.plot(x, prop, ":", color="gray", label=r"$\propto 1/\sqrt{N}$ from the 10 kpc point")
    ax.set_ylabel(r"$\theta_{68}$ [deg]")
    ax.set_ylim(0, max(hi) * 1.25)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="upper left")
    ax.set_title("Deployed configuration (CT v80 $\\geq$ 0.30, E > 5 MeV, mixture + acceptance),\n"
                 "722 evaluation bursts; 40 kt, GKVM, 330 ES + 3300 CC generated at 10 kpc",
                 fontsize=9.5)
    top = ax.secondary_xaxis("top")
    top.set_xticks(x)
    top.set_xticklabels([str(r["d_kpc"]) for r in summary])
    top.set_xlabel("supernova distance [kpc]  (N $\\propto$ 1/d$^2$)")
    sf = np.array([r["sky_frac_mean"] for r in summary])
    sflo = (1 - np.cos(np.radians(lo))) / 2
    sfhi = (1 - np.cos(np.radians(hi))) / 2
    ax2.fill_between(x, sflo * 100, sfhi * 100, color="#d62728", alpha=0.25, lw=0)
    ax2.plot(x, sf * 100, "s-", color="#d62728")
    ax2.set_ylabel("sky fraction\n$(1-\\cos\\theta_{68})/2$ [%]")
    ax2.set_ylim(0, max(sfhi) * 100 * 1.2)
    ax2.grid(alpha=0.3)
    ax2.set_xticks(x)
    ax2.set_xticklabels([f"$1/\\sqrt{{{r['n_gen_es']}}}$" for r in summary], fontsize=8)
    ax2.set_xlabel("1/$\\sqrt{N_{ES}}$  (generated ES events per burst)")
    fig.savefig(out / "resolution_vs_distance.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    payload = {"summary": summary, "per_draw": {str(k): v for k, v in res.items()},
               "fit_a_plus_b_over_sqrtN": {"a": float(coef[0]), "b": float(coef[1])},
               "rows_per_distance_seed": {f"{d}_{s}": n for (d, s), n in coverage.items()},
               "n_errors": len(errors), "errors": errors[:20], "chunk_files": files,
               "n_boot": args.n_boot, "seed": args.seed}
    (out / "resolution_vs_distance.json").write_text(json.dumps(payload, indent=1) + "\n")

    L = ["# Pointing resolution versus supernova distance (deployed configuration)\n",
         "*Generated by `python/ana/resolution_vs_distance.py`.  Figure `resolution_vs_distance.png`.*\n",
         "## Method\n",
         "* **Reference yield.**  The campaign bursts hold the first 330 ES + 3300 CC GENERATED events "
         "(`python/lib/sample_loader.py`, generated-event budget).  The tech note "
         "(`snop-tech-notes/chapters/pipeline.tex`) evaluates the pipeline on \"realistic burst samples "
         "containing 325 ES and 3,300 CC events\" and its (currently commented-out) event-rate section in "
         "`chapters/supernova_physics.tex` states the source: GKVM, **40 kt DUNE far detector at 10 kpc**, "
         "3300 nu_e CC and 325.8 ES (SNOwGLoBES), with rates scaling as 1/d^2; the introduction also "
         "quotes 10 kpc.  10 kpc is therefore the reference distance of the campaign bursts.",
         "* **Distance by trimming.**  N(d) = N(10 kpc) (10/d)^2 for both classes, so a burst at d is "
         "emulated by keeping F = (10/d)^2 of its generated ES events and, independently, F of its "
         "generated CC events, BEFORE the unchanged scenario-8 selection (CT >= 0.30, E > 5 MeV) and "
         "grid-mixture fit with the acceptance term (`replay_scenario_from_slim.py --keep-fraction F "
         "--trim-seed S`).  Exactly round(F N_gen) generated events of each class are kept, drawn "
         "uniformly among the GENERATED events (those that left no matched cluster count, as in the "
         "loader's budget), so the reconstructed ones kept fluctuate hypergeometrically.  The purity "
         "prior (`pi_fixed`), the ES table, the calibration and the acceptance are unchanged: they do "
         "not depend on the number of events, and the ES/CC ratio is distance independent.  The "
         "stored ED v63 directions and CT v80 scores are re-fitted, nothing is re-inferred.",
         "* **Draws.**  3 independent seeds (1, 2, 3) per distance on the 722 evaluation cats.  For a "
         "given seed the draws are NESTED in F (the events kept at 15 kpc are a subset of those kept at "
         "14 kpc, ...), i.e. each seed is one burst \"moved\" outward; this correlates neighbouring "
         "distances of the same seed and smooths the curve, while the 3 seeds are independent.  "
         "theta68 is computed per draw; the table quotes the mean over the draws, their spread "
         "(sample std) and the mean per-draw 68% bootstrap interval (2000 resamples of the 722 cats).  "
         "The draw spread (0.2-0.36 deg) is comparable to the bootstrap half-width (0.2-0.25 deg); it "
         "measures only the trimming randomness for the SAME 722 bursts, while the bootstrap measures "
         "the finite number of bursts, so the two are complementary (the table gives both; their "
         "quadrature sum is `theta68_total_err` in the json).",
         "* **Event identity.**  `volumes.npz` stores the per-file event number but not the input-file "
         "index, so the draw identifies an event by its stored truth record (class, event number, "
         "neutrino energy and momentum, true vertex); all clusters of an event share it (in this "
         "campaign every loaded event has exactly one matched cluster).  F = 1 reproduces the "
         "untrimmed per-cat result exactly (checked on cats 2-4).\n",
         "## Results (722 evaluation cats)\n",
         "| d [kpc] | F | gen. ES / CC kept | theta68 [deg] mean of draws | draw spread (std; min-max) | "
         "68% bootstrap (mean of draws) | sky fraction [%] | median [deg] | theta90 [deg] | frac>30 | "
         "mean n in fit | mean true ES in fit |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in summary:
        spread = ("-" if r["n_draws"] == 1 else
                  f"{r['theta68_draw_spread_std']:.2f}; {r['theta68_draw_min']:.2f}-{r['theta68_draw_max']:.2f}")
        L.append(f"| {r['d_kpc']} | {r['F']:.4f} | {r['n_gen_es']} / {r['n_gen_cc']} | "
                 f"**{r['theta68_mean']:.2f}** | {spread} | [{r['theta68_boot_lo_mean']:.2f}, "
                 f"{r['theta68_boot_hi_mean']:.2f}] | {100 * r['sky_frac_mean']:.3f} | "
                 f"{r['median_mean']:.2f} | {r['theta90_mean']:.2f} | {r['frac_gt30_mean']:.4f} | "
                 f"{r['mean_n_selected']:.0f} | {r['mean_true_es_in_fit']:.1f} |")
    L.append("")
    L.append("d = 10 kpc is the existing untrimmed replay (`v63_matchfix_1000_acc_t030`, one \"draw\").  "
             "Per-draw values are in `resolution_vs_distance.json` (`per_draw`).\n")
    L.append(f"Reference fit theta68 = a + b/sqrt(N_ES) to the six means: a = {coef[0]:.2f} deg, "
             f"b = {coef[1]:.1f} deg (b/sqrt(330) = {coef[1] / np.sqrt(330):.2f} deg).  The dotted line in "
             "the figure is pure 1/sqrt(N) scaling from the 10 kpc point: the measured degradation from "
             f"10 to 15 kpc is a factor {summary[-1]['theta68_mean'] / summary[0]['theta68_mean']:.2f}, "
             f"slower than the statistical 1.5 (= sqrt(330/147)), which suggests a part of the "
             "resolution (ES-table / acceptance modelling, CC leakage, reconstruction tails) that does "
             "not shrink with N.  The intercept is an extrapolation over a short lever arm "
             "(1/sqrt(330) to 1/sqrt(147)) and should not be quoted as an asymptotic floor.\n")
    L.append("Per (distance, seed) the number of cats fitted: " +
             ", ".join(f"{d} kpc s{s}: {n}" for (d, s), n in sorted(coverage.items())) +
             f"; fit errors: {len(errors)}.\n")
    L.append("## Why the curve stops at 10 kpc\n")
    L.append("Trimming can only REMOVE events.  The stored per-event predictions (ED v63 directions, "
             "CT v80 scores, `volumes.npz` metadata) of each campaign cat hold only the 330 ES + 3300 CC "
             "generated events that were loaded into that burst, and the CC cluster images of the campaign "
             "cats were pruned after the campaign (only the slim tars remain), so a closer supernova (more "
             "events per burst, F > 1) would need new event samples drawn into each burst and a re-run of "
             "the CT and ED inference on them.  Re-using events of other cats would break the "
             "independence of the bursts (and the burst direction is per cat), so it is not done.\n")
    L.append("## Outputs\n")
    L.append(f"* chunk files (one per condor job, per-cat rows inside): {len(files)} x "
             "`chunk_<cats>.json` in this directory")
    L.append("* condor: `condor/distance_replay/` (submit file, chunk list, wrapper); logs "
             "`condor/logs/distance_replay/`")
    L.append("* `resolution_vs_distance.png`, `resolution_vs_distance.json`, this file")
    (out / "resolution_vs_distance.md").write_text("\n".join(L) + "\n")
    for r in summary:
        print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}))
    print("errors", len(errors), "coverage", coverage)
    if list(Path(args.far_root).glob("chunk_*.json")):
        extended(args, rng, res, summary, out)


def _valid(r):
    return (np.isfinite(r["cos_to_truth"]) and int(r["n_selected"]) > 0)


def extended(args, rng, res, summary, out):
    """10-50 kpc: the original 10-15 kpc results plus the far chunks (20-50 kpc)."""
    frows, ferrs, ffiles = [], [], sorted(Path(args.far_root).glob("chunk_*.json"))
    nofit_rows = []
    for f in ffiles:
        d = json.loads(f.read_text())
        frows.extend(d["rows"])
        ferrs.extend(d.get("errors", []))
        nofit_rows.extend(d.get("no_fit", []))
    far_res, cover, nofit = {}, {}, {}
    for d in FAR_DISTANCES:
        F = FAR_F[d]
        sel = [r for r in frows if abs(r["keep_fraction"] - F) < 5e-7 and in_eval(int(r["cat"]))]
        nf = [r for r in nofit_rows if abs(r["keep_fraction"] - F) < 5e-7 and in_eval(int(r["cat"]))]
        far_res[d] = {"F": F, "n_gen_es": int(np.floor(F * N_GEN_ES + 0.5)),
                      "n_gen_cc": int(np.floor(F * N_GEN_CC + 0.5)), "draws": {}}
        for sd in sorted({int(r["trim_seed"]) for r in sel} | {int(r["trim_seed"]) for r in nf}):
            allr = [r for r in sel if int(r["trim_seed"]) == sd]
            ok = sorted((r for r in allr if _valid(r)), key=lambda r: r["cat"])
            cover[(d, sd)] = len(allr) + sum(1 for r in nf if int(r["trim_seed"]) == sd)
            nofit[(d, sd)] = 722 - len(ok)
            st = stats([r["cos_to_truth"] for r in ok], [r["n_selected"] for r in ok],
                       [r.get("n_true_es_used", np.nan) for r in ok], rng, args.n_boot)
            st["mean_true_es_in_fit"] = float(np.nanmean([r.get("n_true_es_used", np.nan) for r in ok]))
            st["n_no_fit"] = 722 - len(ok)
            st["n_zero_selected"] = sum(1 for r in allr if int(r["n_selected"]) == 0)
            st["n_nothing_kept"] = sum(1 for r in nf if int(r["trim_seed"]) == sd)
            far_res[d]["draws"][str(sd)] = st
    ext = []
    for r in summary:
        e = dict(r)
        e["n_no_fit_per_draw"] = [0] * r["n_draws"]
        e["n_no_fit_mean"] = 0.0
        ext.append(e)
    for d in FAR_DISTANCES:
        dr = list(far_res[d]["draws"].values())
        t = np.array([x["theta68"] for x in dr])
        e = {"d_kpc": d, "F": far_res[d]["F"], "n_gen_es": far_res[d]["n_gen_es"],
             "n_gen_cc": far_res[d]["n_gen_cc"], "n_draws": len(dr),
             "n_cats": [x["N"] for x in dr], "theta68_mean": float(t.mean()),
             "theta68_draw_spread_std": float(t.std(ddof=1)) if t.size > 1 else 0.0,
             "theta68_draw_min": float(t.min()), "theta68_draw_max": float(t.max()),
             "theta68_boot_lo_mean": float(np.mean([x["theta68_lo"] for x in dr])),
             "theta68_boot_hi_mean": float(np.mean([x["theta68_hi"] for x in dr])),
             "median_mean": float(np.mean([x["median"] for x in dr])),
             "theta90_mean": float(np.mean([x["theta90"] for x in dr])),
             "frac_gt30_mean": float(np.mean([x["frac_gt30"] for x in dr])),
             "mean_n_selected": float(np.mean([x["mean_n_selected"] for x in dr])),
             "mean_true_es_in_fit": float(np.mean([x["mean_true_es_in_fit"] for x in dr])),
             "sky_frac_mean": float(np.mean([x["sky_frac"] for x in dr])),
             "n_no_fit_per_draw": [x["n_no_fit"] for x in dr],
             "n_no_fit_mean": float(np.mean([x["n_no_fit"] for x in dr]))}
        e["theta68_boot_halfwidth"] = 0.5 * (e["theta68_boot_hi_mean"] - e["theta68_boot_lo_mean"])
        e["theta68_total_err"] = float(np.hypot(e["theta68_boot_halfwidth"], e["theta68_draw_spread_std"]))
        ext.append(e)
    allres = {**{d: res[d] for d in DISTANCES}, **far_res}
    x = np.array([1 / np.sqrt(r["n_gen_es"]) for r in ext])
    y = np.array([r["theta68_mean"] for r in ext])
    lo = np.array([r["theta68_boot_lo_mean"] for r in ext])
    hi = np.array([r["theta68_boot_hi_mean"] for r in ext])
    prop = y[0] * x / x[0]
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(9.0, 7.8), sharex=True,
                                  gridspec_kw={"height_ratios": [2.2, 1], "hspace": 0.06})
    ax.fill_between(x, lo, hi, color="#1f77b4", alpha=0.25, lw=0,
                    label="68% bootstrap band (mean over draws)")
    ax.errorbar(x, y, yerr=[r["theta68_draw_spread_std"] for r in ext], fmt="o-",
                color="#1f77b4", capsize=3,
                label=r"$\theta_{68}$, mean of 3 trimming draws ($\pm$ draw spread)")
    for r, xi in zip(ext[1:], x[1:]):
        for dr in allres[r["d_kpc"]]["draws"].values():
            ax.plot(xi, dr["theta68"], "_", color="#1f77b4", ms=9, alpha=0.8)
    ax.plot(x, prop, ":", color="gray", label=r"$\propto 1/\sqrt{N}$ from the 10 kpc point")
    ax.set_ylabel(r"$\theta_{68}$ [deg]")
    ax.set_ylim(0, max(hi.max(), prop.max()) * 1.1)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="upper left")
    ax.set_title("Deployed configuration (CT v80 $\\geq$ 0.30, E > 5 MeV, mixture + acceptance),\n"
                 "722 evaluation bursts; 40 kt, GKVM, 330 ES + 3300 CC generated at 10 kpc; "
                 "20-50 kpc for illustration", fontsize=9)
    top = ax.secondary_xaxis("top")
    top.set_xticks(x)
    top.set_xticklabels([str(r["d_kpc"]) for r in ext], fontsize=8)
    top.set_xlabel("supernova distance [kpc]  (N $\\propto$ 1/d$^2$)")
    sf = np.array([r["sky_frac_mean"] for r in ext])
    sflo = (1 - np.cos(np.radians(lo))) / 2
    sfhi = (1 - np.cos(np.radians(hi))) / 2
    ax2.fill_between(x, sflo * 100, sfhi * 100, color="#d62728", alpha=0.25, lw=0)
    ax2.plot(x, sf * 100, "s-", color="#d62728")
    ax2.set_ylabel("sky fraction\n$(1-\\cos\\theta_{68})/2$ [%]")
    ax2.set_ylim(0, max(sfhi) * 100 * 1.1)
    ax2.grid(alpha=0.3)
    ax2.set_xticks(x)
    ax2.set_xticklabels([f"$1/\\sqrt{{{r['n_gen_es']}}}$" for r in ext], fontsize=7, rotation=60)
    ax2.set_xlabel("1/$\\sqrt{N_{ES}}$  (generated ES events per burst)")
    fig.savefig(out / "resolution_vs_distance_to50kpc.png", dpi=150, bbox_inches="tight")
    plt.close(fig)

    payload = {"summary": ext, "per_draw": {str(k): v for k, v in allres.items()},
               "rows_per_distance_seed_far": {f"{d}_{s}": n for (d, s), n in cover.items()},
               "no_fit_per_distance_seed_far": {f"{d}_{s}": n for (d, s), n in nofit.items()},
               "n_errors_far": len(ferrs), "errors_far": ferrs[:20],
               "n_no_fit_records_far": len(nofit_rows), "far_chunk_files": [str(f) for f in ffiles],
               "n_boot": args.n_boot, "seed": args.seed,
               "no_fit_definition": "722 - bursts with a finite direction and n_selected > 0; "
                                    "these are excluded from theta68, median, frac>30 and the means"}
    (out / "resolution_vs_distance_to50kpc.json").write_text(json.dumps(payload, indent=1) + "\n")

    L = ["", "## Extension to 50 kpc (illustration)\n",
         "*Figure `resolution_vs_distance_to50kpc.png`, data `resolution_vs_distance_to50kpc.json`; "
         "chunks `far/chunk_<cats>.json` (15 jobs, `condor/distance_replay/submit_distance_far.sub`).*\n",
         "Same method as above (same 722 cats, seeds 1, 2, 3, unchanged scenario-8 selection and fit) at "
         "d = 20, 25, 30, 40, 50 kpc, F = 0.25, 0.16, 0.111111, 0.0625, 0.04 (generated ES / CC per burst "
         "83 / 825, 53 / 528, 37 / 367, 21 / 206, 13 / 132).  The 10-15 kpc rows are those of the table "
         "above; 16-19 kpc were not run, so the curve has a gap between 15 and 20 kpc.  At these yields "
         "the result is an ILLUSTRATION: the ES table, purity prior and acceptance are those tuned for "
         "the 10 kpc yield, and the theta68 is dominated by the tail of a few-event fit.  Bursts with no "
         "fit (no reconstructed event kept, or 0 selected events, or no direction) are excluded from the "
         "quantiles; their number is in the last column (per-draw counts in the json).  1/sqrt(N) line "
         "is anchored at the 10 kpc point.\n",
         "| d [kpc] | F | gen. ES / CC kept | theta68 [deg] mean of draws | draw spread (std; min-max) | "
         "68% bootstrap (mean of draws) | sky fraction [%] | median [deg] | frac>30 | "
         "mean n in fit | mean true ES in fit | bursts with no fit (per draw, of 722) |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in ext:
        spread = ("-" if r["n_draws"] == 1 else
                  f"{r['theta68_draw_spread_std']:.2f}; {r['theta68_draw_min']:.2f}-{r['theta68_draw_max']:.2f}")
        L.append(f"| {r['d_kpc']} | {r['F']:.4f} | {r['n_gen_es']} / {r['n_gen_cc']} | "
                 f"**{r['theta68_mean']:.2f}** | {spread} | [{r['theta68_boot_lo_mean']:.2f}, "
                 f"{r['theta68_boot_hi_mean']:.2f}] | {100 * r['sky_frac_mean']:.3f} | "
                 f"{r['median_mean']:.2f} | {r['frac_gt30_mean']:.4f} | "
                 f"{r['mean_n_selected']:.1f} | {r['mean_true_es_in_fit']:.1f} | "
                 f"{'/'.join(str(v) for v in r['n_no_fit_per_draw'])} |")
    L.append("")
    L.append(f"Far-chunk fit errors: {len(ferrs)}; no-fit records written by the replay: {len(nofit_rows)}.  "
             "Rows per (distance, seed) incl. no-fit: " +
             ", ".join(f"{d} kpc s{s}: {n}" for (d, s), n in sorted(cover.items())) + ".\n")
    with open(out / "resolution_vs_distance.md", "a") as fh:
        fh.write("\n".join(L) + "\n")
    for r in ext[len(summary):]:
        print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}))


if __name__ == "__main__":
    main()
