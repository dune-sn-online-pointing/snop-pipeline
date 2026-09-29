#!/usr/bin/env python3
"""Merge the ct_rescan_eval chunks and write the re-scan results table.

For every variant: theta68 = degrees(arccos(quantile(cos(reco, true burst), 0.32))) across
cats, the median theta, frac > 30 deg, mean n_selected, the ES purity of the selection on the
evaluated cats, the coverage ratio theta68 / median per-cat q68, and the paired bootstrap 68%
interval of (theta68_variant - theta68_S0) over cats (2000 resamples, seed 23 -- the
convention of ed_r3_report.py).  Variants are compared only on the cats all of them have.

Usage:
  python3 python/ana/ct_rescan_report.py --results <dir> --variants <variants.json> \
      --tables-provenance <ct_rescan_tables_provenance.json> \
      --out-json <r3_rescan_results.json> --out-md <r3_rescan_results.md>
"""
import argparse
import glob
import json
from pathlib import Path

import numpy as np

ERAS = {"2-399 (old era)": (2, 399), "901-1224 (new era)": (901, 1224)}
DEV = (623, 672)
N_BOOT = 2000
BOOT_SEED = 23


def theta68(cos):
    c = np.asarray(cos, dtype=np.float64)
    c = c[np.isfinite(c)]
    if c.size == 0:
        return float("nan")
    return float(np.degrees(np.arccos(np.clip(np.quantile(c, 0.32), -1.0, 1.0))))


def load(results_dir):
    """tag -> {cat: (cos, q68, nsel, nes)}, plus cat -> ref_cos."""
    per = {}
    ref = {}
    for f in sorted(glob.glob(str(Path(results_dir) / "*.npz"))):
        z = np.load(f, allow_pickle=True)
        cats = [int(c) for c in z["cats"]]
        tags = json.loads(str(z["tags"]))
        for i, c in enumerate(cats):
            if np.isfinite(z["ref_cos"][i]):
                ref[c] = (float(z["ref_cos"][i]), int(z["ref_nsel"][i]))
        for t in tags:
            d = per.setdefault(t, {})
            for i, c in enumerate(cats):
                d[c] = (float(z[f"cos_{t}"][i]), float(z[f"q68_{t}"][i]),
                        int(z[f"nsel_{t}"][i]), int(z[f"nes_{t}"][i]))
    return per, ref


def stats(rows):
    cos = np.array([r[0] for r in rows]); q68 = np.array([r[1] for r in rows])
    nsel = np.array([r[2] for r in rows]); nes = np.array([r[3] for r in rows])
    good = np.isfinite(cos)
    th = np.degrees(np.arccos(np.clip(cos[good], -1, 1)))
    return {"theta68": theta68(cos), "median": float(np.median(th)) if th.size else float("nan"),
            "frac_gt_30": float(np.mean(th > 30)) if th.size else float("nan"),
            "coverage": (float(theta68(cos) / np.median(q68[good & np.isfinite(q68)]))
                         if np.isfinite(q68[good]).any() else float("nan")),
            "mean_n_selected": float(nsel.mean()), "es_purity": float(nes.sum() / max(nsel.sum(), 1)),
            "n_cats": int(good.sum()), "n_failed": int((~good).sum())}


def paired(cos_v, cos_ref):
    """theta68 difference and its paired bootstrap 68% interval over cats."""
    d = theta68(cos_v) - theta68(cos_ref)
    rng = np.random.RandomState(BOOT_SEED)
    n = len(cos_v)
    bs = np.empty(N_BOOT)
    for k in range(N_BOOT):
        i = rng.randint(0, n, n)
        bs[k] = theta68(cos_v[i]) - theta68(cos_ref[i])
    return d, float(np.percentile(bs, 16)), float(np.percentile(bs, 84))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--variants", required=True)
    ap.add_argument("--tables-provenance", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--ref-tag", default="S0")
    args = ap.parse_args()

    spec = {v["tag"]: v for v in json.loads(Path(args.variants).read_text())}
    prov = json.loads(Path(args.tables_provenance).read_text())
    per, ref = load(args.results)
    eval_cats = lambda cs: [c for c in cs if any(lo <= c <= hi for lo, hi in ERAS.values())]
    dev_cats = lambda cs: [c for c in cs if DEV[0] <= c <= DEV[1]]

    md, out = [], {"variants": {}, "purity_scan": prov["purity_scan"]}
    md.append("# CT selection-rule re-scan on the r3 campaign (v63 directions, corrected tables)\n")
    md.append(f"Results merged from `{args.results}`. theta68 = "
              "degrees(arccos(quantile(cos(reco, true burst), 0.32))).\n")

    # ---------------------------------------------------------------- purity scan
    md.append("\n## Purity vs selection rule (training slice, cats 673-900, 227 cats)\n")
    md.append("| rule | selection | events/burst | true-ES/burst | ES purity f | <cos>_ES | <cos>_CC |")
    md.append("|---|---|---|---|---|---|---|")
    for r in prov["purity_scan"]:
        md.append(f"| `{r['rule']}` | {r['label']} | {r['n_per_burst']:.1f} | "
                  f"{r['n_es_per_burst']:.1f} | {r['purity']:.4f} | {r['mean_cos_es']:.3f} | "
                  f"{r['mean_cos_cc']:+.3f} |")

    # ---------------------------------------------------------------- main table
    tags = [t for t in spec if t in per and t != "GATE_TG"]
    common = sorted(set.intersection(*[set(eval_cats(per[t])) for t in tags])) if tags else []
    assert args.ref_tag in tags, f"{args.ref_tag} missing from the results"
    md.append(f"\n## Evaluation cats 2-399 + 901-1224 ({len(common)} cats common to all variants)\n")
    md.append(f"| variant | selection / table | theta68 | d vs {args.ref_tag} [68% paired boot] | "
              "median | frac>30 | mean n_sel | ES purity | coverage |")
    md.append("|---|---|---|---|---|---|---|---|---|")
    ref_cos = np.array([per[args.ref_tag][c][0] for c in common])
    rows = []
    for t in tags:
        rws = [per[t][c] for c in common]
        s = stats(rws)
        cv = np.array([per[t][c][0] for c in common])
        d, lo, hi = paired(cv, ref_cos)
        s.update(delta_vs_ref=d, delta_lo=lo, delta_hi=hi, label=spec[t].get("label", ""))
        out["variants"][t] = s
        rows.append((s["theta68"], t, s))
    for th, t, s in sorted(rows):
        dcell = "-" if t == args.ref_tag else f"{s['delta_vs_ref']:+.2f} [{s['delta_lo']:+.2f}, {s['delta_hi']:+.2f}]"
        md.append(f"| **{t}** | {s['label']} | **{s['theta68']:.2f}** | {dcell} | "
                  f"{s['median']:.2f} | {s['frac_gt_30']:.2f} | {s['mean_n_selected']:.0f} | "
                  f"{s['es_purity']:.3f} | {s['coverage']:.2f} |")
    out["n_cats_common"] = len(common)
    out["cats_common"] = common

    # ---------------------------------------------------------------- per era, best 3
    best = [t for _, t, _ in sorted(rows)[:3]]
    if args.ref_tag not in best:
        best.append(args.ref_tag)
    md.append(f"\n## Per era, best variants\n")
    md.append("| era | Ncats | " + " | ".join(best) + " |")
    md.append("|---|---|" + "---|" * len(best))
    out["per_era"] = {}
    for era, (lo, hi) in ERAS.items():
        cs = [c for c in common if lo <= c <= hi]
        if not cs:
            continue
        cells = []
        for t in best:
            v = theta68([per[t][c][0] for c in cs])
            out["per_era"].setdefault(era, {})[t] = v
            cells.append(f"{v:.2f}")
        md.append(f"| {era} | {len(cs)} | " + " | ".join(cells) + " |")
    md.append(f"\npaired difference vs {args.ref_tag} per era:\n")
    md.append("| era | " + " | ".join(t for t in best if t != args.ref_tag) + " |")
    md.append("|---|" + "---|" * (len(best) - 1))
    for era, (lo, hi) in ERAS.items():
        cs = [c for c in common if lo <= c <= hi]
        if not cs:
            continue
        a = np.array([per[args.ref_tag][c][0] for c in cs])
        cells = []
        for t in best:
            if t == args.ref_tag:
                continue
            d, l, h = paired(np.array([per[t][c][0] for c in cs]), a)
            out["per_era"].setdefault(era, {})[f"{t}_vs_{args.ref_tag}"] = [d, l, h]
            cells.append(f"{d:+.2f} [{l:+.2f}, {h:+.2f}]")
        md.append(f"| {era} | " + " | ".join(cells) + " |")

    # ---------------------------------------------------------------- dev cats
    dtags = [t for t in tags if dev_cats(per[t])]
    if dtags:
        dcommon = sorted(set.intersection(*[set(dev_cats(per[t])) for t in dtags]))
        md.append(f"\n## Development cats 623-672 ({len(dcommon)} cats), reported separately\n")
        md.append("| variant | theta68 | median | mean n_sel | ES purity | coverage |")
        md.append("|---|---|---|---|---|---|")
        out["dev_cats"] = {}
        for th, t, _ in sorted(rows):
            if t not in dtags:
                continue
            s = stats([per[t][c] for c in dcommon])
            out["dev_cats"][t] = s
            md.append(f"| {t} | {s['theta68']:.2f} | {s['median']:.2f} | "
                      f"{s['mean_n_selected']:.0f} | {s['es_purity']:.3f} | {s['coverage']:.2f} |")

    # ---------------------------------------------------------------- campaign gate
    if "GATE_TG" in per:
        cs = [c for c in sorted(per["GATE_TG"]) if c in ref]
        a = np.array([per["GATE_TG"][c][0] for c in cs])
        b = np.array([ref[c][0] for c in cs])
        ns = np.array([per["GATE_TG"][c][2] for c in cs])
        nr = np.array([ref[c][1] for c in cs])
        out["campaign_gate"] = {"n_cats": len(cs), "max_abs_cos_minus_report": float(np.nanmax(np.abs(a - b))),
                               "median_abs_cos_minus_report": float(np.nanmedian(np.abs(a - b))),
                               "n_bit_exact": int(np.sum(np.abs(a - b) < 1e-12)),
                               "n_sel_matching_report": int(np.sum(ns == nr)),
                               "theta68_offline": theta68(a), "theta68_report": theta68(b)}
        g = out["campaign_gate"]
        md.append(f"\n## Gate against the r3 campaign's own reports (variant GATE_TG, "
                  f"{g['n_cats']} cats)\n")
        md.append(f"- offline theta68 {g['theta68_offline']:.2f} vs the reports' "
                  f"{g['theta68_report']:.2f} on the same cats")
        md.append(f"- per-cat cos: {g['n_bit_exact']}/{g['n_cats']} bit-exact, "
                  f"median |d| = {g['median_abs_cos_minus_report']:.1e}, "
                  f"max |d| = {g['max_abs_cos_minus_report']:.1e}")
        md.append(f"- n_selected matches the report on {g['n_sel_matching_report']}/{g['n_cats']} cats")

    Path(args.out_json).write_text(json.dumps(out, indent=2))
    Path(args.out_md).write_text("\n".join(md) + "\n")
    print("\n".join(md))
    print(f"\nwrote {args.out_json}\nwrote {args.out_md}")


if __name__ == "__main__":
    main()
