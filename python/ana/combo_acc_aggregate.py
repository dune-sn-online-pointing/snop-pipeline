#!/usr/bin/env python3
"""Aggregate the acceptance-scenario replay over the r3 campaign and compare it with

  * the r3 campaign's own scenario_3_full_pipeline (the currently deployed configuration),
  * the offline combo study's arm CMB2_t050_accCC_ccl6, per cat.

Cat subsets: 722 evaluation cats (2-399 + 901-1224, HEADLINE), 50 dev cats (623-672) and the
227 slice cats (673-900, IN SAMPLE for the tables and for R -- never a headline).  Cats
400-621 are never read.  cat000001 has reduced CC statistics and is flagged, not used.

Usage:
  python3 python/ana/combo_acc_aggregate.py --acc <root> --ref <r3 campaign root> \
      --study-results <combo_study/results> --out-md <md> [--out-json <json>]
"""
import argparse
import json
from pathlib import Path

import numpy as np

EVAL = [(2, 399), (901, 1224)]
DEV = [(623, 672)]
SLICE = [(673, 900)]
ALL_CAMPAIGN = [(1, 399), (623, 1224)]
STUDY_ARM = "CMB2_t050_accCC_ccl6"


def in_ranges(n, ranges):
    return any(lo <= n <= hi for lo, hi in ranges)


def load_root(root, scenario):
    out = {}
    for rep in sorted(Path(root).glob("cat*/scenario_cos_theta_report.json")):
        try:
            n = int(rep.parent.name[3:])
        except ValueError:
            continue
        try:
            payload = json.loads(rep.read_text())
        except Exception:  # noqa: BLE001
            continue
        for s in payload.get("scenarios", []):
            if s.get("scenario") != scenario:
                continue
            cos = s.get("cos_to_truth")
            if cos is None or not np.isfinite(cos):
                continue
            out[n] = {"cos": float(cos), "theta": float(np.degrees(np.arccos(np.clip(cos, -1, 1)))),
                      "q68": float(s.get("q68_theta_deg", np.nan)),
                      "n_selected": int(s.get("n_selected") or 0),
                      "label": s.get("label", scenario)}
    return out


def load_study(results_dir, arm=STUDY_ARM):
    out = {}
    for f in sorted(Path(results_dir).glob("*.npz")):
        try:
            z = np.load(f, allow_pickle=True)
        except Exception:  # noqa: BLE001
            continue
        key = f"cos_{arm}"
        if key not in z.files or "cats" not in z.files:
            continue
        nkey = f"nsel_{arm}"
        for i, c in enumerate(np.asarray(z["cats"]).astype(int)):
            v = float(z[key][i])
            if np.isfinite(v):
                out[int(c)] = {"cos": v,
                               "theta": float(np.degrees(np.arccos(np.clip(v, -1, 1)))),
                               "n_selected": int(z[nkey][i]) if nkey in z.files else -1}
    return out


def theta68(cos):
    c = np.asarray(cos, dtype=np.float64)
    return float(np.degrees(np.arccos(np.clip(np.quantile(c, 0.32), -1.0, 1.0))))


def summarise(rows):
    cos = np.array([r["cos"] for r in rows])
    th = np.array([r["theta"] for r in rows])
    q = np.array([r["q68"] for r in rows], dtype=np.float64)
    t68 = theta68(cos)
    med_q = float(np.nanmedian(q)) if np.isfinite(q).any() else float("nan")
    return {"n_cats": len(rows), "theta68": t68, "median": float(np.median(th)),
            "mean": float(np.mean(th)),
            "theta90": float(np.degrees(np.arccos(np.clip(np.quantile(cos, 0.10), -1, 1)))),
            "frac_gt_30": float(np.mean(th > 30)),
            "coverage": (t68 / med_q if np.isfinite(med_q) and med_q > 0 else float("nan")),
            "mean_n_selected": float(np.mean([r["n_selected"] for r in rows]))}


def paired(cos_a, cos_b, theta_a, theta_b, n_boot=4000, seed=7):
    """B - A: theta68 difference with a paired bootstrap 68/95% interval, plus the paired
    per-cat mean/median difference and the fraction of cats improved."""
    rng = np.random.default_rng(seed)
    d = np.empty(n_boot)
    n = len(cos_a)
    for k in range(n_boot):
        idx = rng.integers(0, n, n)
        d[k] = theta68(cos_b[idx]) - theta68(cos_a[idx])
    dt = theta_b - theta_a
    return {"d_theta68": theta68(cos_b) - theta68(cos_a),
            "ci68": [float(x) for x in np.quantile(d, [0.16, 0.84])],
            "ci95": [float(x) for x in np.quantile(d, [0.025, 0.975])],
            "d_mean": float(np.mean(dt)), "d_mean_err": float(np.std(dt) / np.sqrt(n)),
            "d_median": float(np.median(dt)),
            "frac_cats_improved": float(np.mean(dt < 0))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--acc", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--acc-scenario", default="scenario_7_full_pipeline_acc")
    ap.add_argument("--ref-scenario", default="scenario_3_full_pipeline")
    ap.add_argument("--study-results", default=None)
    ap.add_argument("--study-arm", default=STUDY_ARM,
                    help="arm tag inside the study npz files (e.g. CMB2_t030_accCC_ccl6)")
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-json", default=None)
    args = ap.parse_args()

    A = load_root(args.acc, args.acc_scenario)
    R = load_root(args.ref, args.ref_scenario)
    S = load_study(args.study_results, args.study_arm) if args.study_results else {}
    for name, d in (("acceptance replay", A), ("r3 scenario 3", R), ("offline study", S)):
        bad = [n for n in d if 400 <= n <= 621]
        assert not bad, f"{name} contains off-limits cats {bad[:5]}"
    print(f"loaded: {len(A)} acceptance cats, {len(R)} r3 sc3 cats, {len(S)} offline study cats")

    subsets = [("722 evaluation cats (2-399, 901-1224) -- HEADLINE", EVAL),
               ("50 development cats (623-672)", DEV),
               ("227 slice cats (673-900) -- IN SAMPLE, not a headline", SLICE),
               ("all 1000 campaign cats (1-399, 623-1224 minus 701)", ALL_CAMPAIGN)]
    out, lines = {}, []
    lines.append("## 1. The acceptance scenario on the r3 campaign\n")
    lines.append("theta68 = degrees(arccos(quantile(cos(reco, true burst), 0.32))); "
                 "coverage = theta68 / median of the per-burst 68% posterior quantile "
                 "(1.0 = calibrated, < 1 = conservative).\n")
    lines.append("| subset | Ncats | theta68 | median | mean | theta90 | frac>30 | coverage | n/burst |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for label, ranges in subsets:
        cats = sorted(n for n in A if in_ranges(n, ranges))
        if not cats:
            continue
        s = summarise([A[n] for n in cats])
        out[label] = {"acceptance": s, "cats": cats}
        lines.append(f"| {label} | {s['n_cats']} | **{s['theta68']:.2f}** | {s['median']:.2f} | "
                     f"{s['mean']:.2f} | {s['theta90']:.2f} | {s['frac_gt_30']:.3f} | "
                     f"{s['coverage']:.2f} | {s['mean_n_selected']:.0f} |")

    lines.append("\n## 2. Paired comparison against the r3 campaign's scenario 3 "
                 "(the deployed configuration)\n")
    lines.append("| subset | Ncats | theta68 sc3 | theta68 acc | d theta68 [68%] [95%] | "
                 "median sc3 | median acc | paired mean d | paired median d | frac cats improved | "
                 "frac>30 sc3 -> acc | n/burst sc3 -> acc |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for label, ranges in subsets:
        cats = sorted(n for n in A if n in R and in_ranges(n, ranges))
        if not cats:
            continue
        ra = [R[n] for n in cats]
        rb = [A[n] for n in cats]
        sa, sb = summarise(ra), summarise(rb)
        p = paired(np.array([r["cos"] for r in ra]), np.array([r["cos"] for r in rb]),
                   np.array([r["theta"] for r in ra]), np.array([r["theta"] for r in rb]))
        out.setdefault(label, {})["vs_r3_sc3"] = {"sc3": sa, "acc": sb, "paired": p}
        lines.append(
            f"| {label} | {len(cats)} | {sa['theta68']:.2f} | **{sb['theta68']:.2f}** | "
            f"**{p['d_theta68']:+.2f}** [{p['ci68'][0]:+.2f}, {p['ci68'][1]:+.2f}] "
            f"[{p['ci95'][0]:+.2f}, {p['ci95'][1]:+.2f}] | {sa['median']:.2f} | {sb['median']:.2f} | "
            f"{p['d_mean']:+.2f} +- {p['d_mean_err']:.2f} | {p['d_median']:+.2f} | "
            f"{p['frac_cats_improved']:.3f} | {sa['frac_gt_30']:.3f} -> {sb['frac_gt_30']:.3f} | "
            f"{sa['mean_n_selected']:.0f} -> {sb['mean_n_selected']:.0f} |")

    if S:
        lines.append("\n## 3. Per-cat agreement with the offline study "
                     f"(arm {args.study_arm}, grid 12000)\n")
        lines.append("| subset | Ncats | theta68 pipeline | theta68 offline | d theta68 | "
                     "mean \\|dtheta\\| per cat | median \\|dtheta\\| | max \\|dtheta\\| | "
                     "n_selected identical |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for label, ranges in subsets:
            cats = sorted(n for n in A if n in S and in_ranges(n, ranges))
            if not cats:
                continue
            ta = np.array([A[n]["theta"] for n in cats])
            ts = np.array([S[n]["theta"] for n in cats])
            ca = np.array([A[n]["cos"] for n in cats])
            cs = np.array([S[n]["cos"] for n in cats])
            same_n = sum(1 for n in cats if S[n]["n_selected"] == A[n]["n_selected"])
            dd = np.abs(ta - ts)
            out.setdefault(label, {})["vs_offline_study"] = {
                "n_cats": len(cats), "theta68_pipeline": theta68(ca), "theta68_offline": theta68(cs),
                "mean_abs_dtheta": float(dd.mean()), "median_abs_dtheta": float(np.median(dd)),
                "max_abs_dtheta": float(dd.max()), "n_selected_identical": same_n}
            lines.append(f"| {label} | {len(cats)} | {theta68(ca):.3f} | {theta68(cs):.3f} | "
                         f"{theta68(ca) - theta68(cs):+.3f} | {dd.mean():.4f} | "
                         f"{np.median(dd):.4f} | {dd.max():.3f} | {same_n}/{len(cats)} |")

    flags = []
    if 1 in A:
        flags.append(f"cat000001 (REDUCED CC STATISTICS, 37 of 83 CC tpstreams) is present in the "
                     f"replay with n_selected = {A[1]['n_selected']} and theta = {A[1]['theta']:.2f} "
                     f"deg; it is inside the 'all 1000' row only and is excluded from every "
                     f"evaluation, dev and slice number above.")
    missing = [n for n in sorted(A) if n not in R]
    if missing:
        flags.append(f"{len(missing)} cats have no r3 scenario-3 report: {missing[:8]}")
    if flags:
        lines.append("\n## 4. Flags\n")
        lines += [f"* {f}" for f in flags]

    Path(args.out_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_md).write_text("\n".join(lines) + "\n")
    if args.out_json:
        Path(args.out_json).write_text(json.dumps(out, indent=1, default=float) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
