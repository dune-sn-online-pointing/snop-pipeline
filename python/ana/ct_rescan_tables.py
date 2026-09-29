#!/usr/bin/env python3
"""Per-selection-rule likelihood tables for the CT-threshold re-scan (r3, v63 directions).

Everything is built from the training-slice cache written by `ct_rescan_cache.py`
(cats 673-900 only) and follows the construction validated in sections 20-23 of
docs/ED_v62_matchfix_retrain.md:

  pdf_ES,rule(cos | E) = cos(v63 reco electron dir, TRUE BURST dir) of the TRUE-ES events
                         that pass the rule  (burst axis, not the ED resolution)
  p(cos | E)           = f(E) pdf_ES,rule(cos | E) + (1 - f(E)) * 1/2     (flat CC)

with f measured on the same slice FOR THAT RULE.  A mixture table is only valid for the
selection whose purity it encodes, so every rule gets its own pair.

Rules (selection is always `proba >= t(E)` AND `E_reco > 5 MeV`):
  tNNN    constant threshold t = 0.NNN
  b2_NN   two-band: 0.80 below 10 MeV, 0.NN at and above it
  ramp    t(E) = max(0.5, 0.8 - 0.02 (E - 5))

Purity flavours, one mixture file each:
  _gf   one global f for all rows (the flavour that won in section 23)
  _fE   the measured per-energy-bin f(E)
  _bf   two-band only: one f per band (the per-band analogue of the global f)

Also written: the purity-vs-threshold summary, the per-score-bin P(ES | score) calibration
for the all-events mixture (measured here, NOT the v80 test-set calibration), and the CC
events file from which `build_cc_direction_map.py` makes the detector-frame CC map.

Outputs go to <out-dir> (pipeline-dev/r3_rescan/tables), not next to the model: only a
recommended table is promoted there afterwards.

Usage:
  python3 python/ana/ct_rescan_tables.py --cache <slice_cache.npz> --out-dir <dir>
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from ana.burst_direction import load_pdf_table

ENERGY_BINS = np.array([(2, 4), (4, 6), (6, 8), (8, 10), (10, 12), (12, 14), (14, 16),
                        (16, 18), (18, 20), (20, 22), (22, 24), (24, 26), (26, 28),
                        (28, 30), (30, 35), (35, 40), (40, 50), (50, 70)], dtype=float)
E_CENTERS = ENERGY_BINS.mean(axis=1)
N_COS = 100
COS_EDGES = np.linspace(-1.0, 1.0, N_COS + 1)
COS_CENTERS = 0.5 * (COS_EDGES[:-1] + COS_EDGES[1:])
WIDTHS = COS_EDGES[1:] - COS_EDGES[:-1]
PDF_FLOOR = 1e-4
MIN_E = 5.0
BAND_EDGE = 10.0
SCAN_THRESHOLDS = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]

RULES = {
    **{f"t{int(t*100):03d}": ("const", t) for t in SCAN_THRESHOLDS},
    "b2_50": ("twoband", 0.80, 0.50), "b2_60": ("twoband", 0.80, 0.60),
    "b2_70": ("twoband", 0.80, 0.70), "ramp": ("ramp",),
}


def rule_threshold(rule, energy):
    """Per-event CT threshold of a rule, as a function of the reco cluster energy."""
    spec = RULES[rule]
    e = np.asarray(energy, dtype=np.float64)
    if spec[0] == "const":
        return np.full(e.shape, float(spec[1]))
    if spec[0] == "twoband":
        return np.where(e < BAND_EDGE, float(spec[1]), float(spec[2]))
    if spec[0] == "ramp":
        return np.maximum(0.5, 0.8 - 0.02 * (e - 5.0))
    raise ValueError(f"unknown rule {rule!r}")


def rule_label(rule):
    spec = RULES[rule]
    if spec[0] == "const":
        return f"t = {spec[1]:.2f}"
    if spec[0] == "twoband":
        return f"t = {spec[1]:.2f} below {BAND_EDGE:.0f} MeV, {spec[2]:.2f} above"
    return "t(E) = max(0.5, 0.8 - 0.02 (E - 5))"


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


def fill_rows(pdf, n_per, min_count):
    """Rows with too few events take the nearest measured row (never a flat row)."""
    pdf = np.array(pdf, dtype=np.float64, copy=True)
    good = np.asarray(n_per) >= min_count
    if not good.any():
        return None, good
    idx = np.arange(len(n_per))
    gi = idx[good]
    for i in idx:
        if not good[i]:
            pdf[i] = pdf[gi[np.argmin(np.abs(gi - i))]]
    return pdf, good


def fill_f(f_raw, n_tot, min_count):
    f = np.asarray(f_raw, dtype=np.float64).copy()
    meas = (n_tot >= min_count) & np.isfinite(f)
    idx = np.arange(len(f))
    if not meas.any():
        return None, meas
    gi = idx[meas]
    for i in idx:
        if not meas[i]:
            f[i] = f[gi[np.argmin(np.abs(gi - i))]]
    return f, meas


def save_table(path, pdf, n_per, note, extra=None):
    payload = dict(pdf_2d=pdf, cosine_bin_edges=COS_EDGES, cosine_bin_centers=COS_CENTERS,
                   energy_bins=ENERGY_BINS.astype(np.int64), n_events_per_bin=n_per,
                   smoothing_method=np.asarray("Raw histogram (no smoothing)"),
                   table_note=np.asarray(note))
    if extra:
        payload.update(extra)
    np.savez(path, **payload)


def mixture(es_pdf_path, f_vec, out_path, note):
    es = load_pdf_table(es_pdf_path, pdf_floor=PDF_FLOOR)["pdf"]
    mix = f_vec[:, None] * es + (1.0 - f_vec)[:, None] * 0.5
    mix = mix / np.sum(mix * WIDTHS[None, :], axis=1, keepdims=True)
    n_per = np.asarray(np.load(es_pdf_path)["n_events_per_bin"])
    save_table(out_path, mix, n_per, note, extra={"f_of_E": f_vec})
    return mix


def pava(y, w):
    """Weighted isotonic (non-decreasing) regression, pool-adjacent-violators."""
    y = list(map(float, y)); w = list(map(float, w))
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--row-min-count", type=int, default=50)
    ap.add_argument("--f-min-count", type=int, default=20)
    ap.add_argument("--min-per-burst", type=float, default=5.0,
                    help="rules selecting fewer events per burst than this are not tabulated")
    ap.add_argument("--n-score-bins", type=int, default=50)
    ap.add_argument("--rules", default=None,
                    help="comma list of rule names to (re)build; default all. Use it to add a "
                         "rule without rewriting tables a running job may be reading.")
    ap.add_argument("--prov-suffix", default="",
                    help="suffix for the provenance file name (use with --rules)")
    ap.add_argument("--skip-calibration", action="store_true")
    ap.add_argument("--cc-events-out", default=None,
                    help="where to write the CC reco-direction event file for build_cc_direction_map.py")
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    z = np.load(args.cache, allow_pickle=True)
    lo, hi = [int(v) for v in z["cat_range"]]
    assert lo >= 673 and hi <= 900, f"tables must come from the training slice, cache is {lo}-{hi}"
    E = np.asarray(z["energy"], dtype=np.float64)
    P = np.asarray(z["proba"], dtype=np.float64)
    ES = np.asarray(z["is_es"], dtype=bool)
    COS = np.asarray(z["cos_burst"], dtype=np.float64)
    ncat = int(z["n_cats"])
    print(f"cache: {ncat} cats {lo}-{hi}, {len(E)} valid clusters, "
            f"{ES.mean()*100:.2f}% true ES, max CT score {P.max():.4f}")

    rules = list(RULES) if not args.rules else [r.strip() for r in args.rules.split(",")]
    for r in rules:
        assert r in RULES, f"unknown rule {r!r}"
    prov = {"cache": str(args.cache), "rules_built": rules, "cats": [lo, hi], "n_cats": ncat,
            "n_valid_clusters": int(len(E)), "min_energy": MIN_E, "band_edge": BAND_EDGE,
            "cos_convention": "cos(v63 reco electron dir, TRUE BURST dir)",
            "energy_axis": "reco cluster energy (metadata col 10)",
            "pdf_floor": PDF_FLOOR, "row_min_count": args.row_min_count,
            "rules": {}, "purity_scan": []}

    # ---------------------------------------------------------------- purity scan
    print(f"\n{'rule':8} {'selection':44} {'n/burst':>8} {'ES/burst':>9} {'f':>7} "
          f"{'<cos>ES':>8} {'<cos>CC':>8}")
    for rule in RULES:
        sel = (P >= rule_threshold(rule, E)) & (E > MIN_E)
        n, nes = int(sel.sum()), int((sel & ES).sum())
        row = {"rule": rule, "label": rule_label(rule), "n_per_burst": n / ncat,
               "n_es_per_burst": nes / ncat, "purity": nes / n if n else float("nan"),
               "mean_cos_es": float(COS[sel & ES].mean()) if nes else float("nan"),
               "mean_cos_cc": float(COS[sel & ~ES].mean()) if n - nes else float("nan"),
               "n_selected_slice": n, "n_es_slice": nes}
        prov["purity_scan"].append(row)
        print(f"{rule:8} {rule_label(rule):44} {row['n_per_burst']:8.1f} "
              f"{row['n_es_per_burst']:9.1f} {row['purity']:7.4f} "
              f"{row['mean_cos_es']:8.3f} {row['mean_cos_cc']:+8.3f}")

    # ---------------------------------------------------------------- per-rule tables
    for rule in rules:
        sel = (P >= rule_threshold(rule, E)) & (E > MIN_E)
        n = int(sel.sum())
        if n / ncat < args.min_per_burst:
            print(f"\n{rule}: {n/ncat:.2f} selected events per burst -- below "
                  f"--min-per-burst {args.min_per_burst}, no table built")
            prov["rules"][rule] = {"label": rule_label(rule), "skipped": True,
                                   "n_per_burst": n / ncat}
            continue
        es_sel = sel & ES
        raw, n_es = hist_table(COS[es_sel], E[es_sel])
        pdf_es, good = fill_rows(raw, n_es, args.row_min_count)
        es_path = out / f"pdf_es_burstaxis_{rule}.npz"
        save_table(es_path, pdf_es, n_es,
                   f"cos(v63 reco dir, TRUE BURST dir) of true-ES events passing {rule_label(rule)} "
                   f"and E>{MIN_E} MeV; r3 cats {lo}-{hi}; energy axis = reco cluster energy; "
                   f"rows with <{args.row_min_count} events filled from the nearest measured row",
                   extra={"pdf_2d_raw": raw, "row_measured": good,
                          "rule": np.asarray(rule), "rule_label": np.asarray(rule_label(rule))})

        n_tot = np.zeros(len(ENERGY_BINS)); n_esb = np.zeros(len(ENERGY_BINS))
        for i, (elo, ehi) in enumerate(ENERGY_BINS):
            in_bin = (E >= elo) & (E < ehi) & sel
            n_tot[i] = int(in_bin.sum()); n_esb[i] = int((in_bin & ES).sum())
        f_raw = np.divide(n_esb, n_tot, out=np.full(len(n_tot), np.nan), where=n_tot > 0)
        f_err = np.sqrt(np.clip(f_raw * (1 - f_raw), 0, None) / np.where(n_tot > 0, n_tot, 1))
        f_fill, f_meas = fill_f(f_raw, n_tot, args.f_min_count)
        f_global = float(n_esb.sum() / n_tot.sum())

        flavours = {"gf": np.full(len(ENERGY_BINS), f_global), "fE": f_fill}
        if RULES[rule][0] == "twoband":
            band = np.where(E_CENTERS < BAND_EDGE,
                            float((sel & ES & (E < BAND_EDGE)).sum()) / max(int((sel & (E < BAND_EDGE)).sum()), 1),
                            float((sel & ES & (E >= BAND_EDGE)).sum()) / max(int((sel & (E >= BAND_EDGE)).sum()), 1))
            flavours["bf"] = band
        made = {}
        for tag, fv in flavours.items():
            mp = out / f"mixture_{rule}_{tag}.npz"
            mixture(es_path, fv, mp,
                    f"mixture f*pdf_ES + (1-f)*flat CC for selection [{rule_label(rule)}, E>{MIN_E}]; "
                    f"f = {tag} ({'global %.4f' % f_global if tag == 'gf' else 'per energy bin' if tag == 'fE' else 'per band'}); "
                    f"r3 slice {lo}-{hi}")
            made[tag] = str(mp)
        prov["rules"][rule] = {
            "label": rule_label(rule), "skipped": False,
            "n_per_burst": n / ncat, "purity_global": f_global,
            "f_of_E_raw": f_raw.tolist(), "f_of_E_err": f_err.tolist(),
            "f_of_E_filled": f_fill.tolist(), "f_measured": f_meas.tolist(),
            "n_tot_per_bin": n_tot.tolist(), "n_es_per_bin": n_esb.tolist(),
            "rows_measured": good.tolist(), "pdf_es": str(es_path), "mixtures": made,
            "band_purities": (flavours["bf"][[0, -1]].tolist()
                              if RULES[rule][0] == "twoband" else None),
            "mean_cos_es_table": [float(np.sum(pdf_es[i] * COS_CENTERS) / np.sum(pdf_es[i]))
                                  for i in range(len(ENERGY_BINS))],
        }
        print(f"\n{rule} ({rule_label(rule)}): {n/ncat:.1f}/burst, f = {f_global:.4f}, "
              f"{int(good.sum())}/{len(good)} table rows measured")
        print("  f(E): " + " ".join(f"{int(ENERGY_BINS[i][0])}-{int(ENERGY_BINS[i][1])}:"
                                   f"{f_raw[i]:.3f}" for i in range(len(ENERGY_BINS))
                                   if n_tot[i] >= args.f_min_count))

    # ---------------------------------------------------------------- P(ES | score)
    for cut, tag in (() if args.skip_calibration else ((3.0, "e3"), (5.0, "e5"))):
        m = E > cut
        s = P[m]; y = ES[m].astype(np.float64)
        q = np.unique(np.quantile(s, np.linspace(0, 1, args.n_score_bins + 1)))
        q[0], q[-1] = -1e-9, 1.0 + 1e-9
        idx = np.clip(np.searchsorted(q, s, side="right") - 1, 0, len(q) - 2)
        nb = len(q) - 1
        n = np.bincount(idx, minlength=nb).astype(np.float64)
        nes = np.bincount(idx, weights=y, minlength=nb)
        smean = np.bincount(idx, weights=s, minlength=nb) / np.maximum(n, 1)
        p_raw = np.divide(nes, n, out=np.zeros(nb), where=n > 0)
        p_mono = pava(p_raw, n)
        np.savez(out / f"p_es_given_score_{tag}.npz", score_edges=q, score_center=smean,
                 p_es_raw=p_raw, p_es_mono=p_mono, n=n, n_es=nes, energy_cut=np.float64(cut),
                 cats=np.asarray([lo, hi]),
                 note=np.asarray("P(ES | CT v80 score) measured on the r3 training slice "
                                 f"(cats {lo}-{hi}) for clusters with a valid reco direction and "
                                 f"E>{cut} MeV; p_es_mono is the weighted isotonic fit; "
                                 "interpolate linearly in score_center"))
        prov[f"calibration_{tag}"] = {
            "n_bins": int(nb), "n_events": int(n.sum()), "n_es": float(nes.sum()),
            "monotone_violations_raw": int(np.sum(np.diff(p_raw) < 0)),
            "p_at_score": {f"{smean[i]:.3f}": float(p_mono[i])
                           for i in range(0, nb, max(1, nb // 10))},
            "p_range": [float(p_mono.min()), float(p_mono.max())],
            "path": str(out / f"p_es_given_score_{tag}.npz")}
        print(f"\nP(ES|score) {tag}: {nb} quantile bins, {int(n.sum())} events, "
              f"p from {p_mono.min():.4f} to {p_mono.max():.4f}, "
              f"{int(np.sum(np.diff(p_raw) < 0))} raw monotonicity violations")

    # ---------------------------------------------------------------- CC events for the map
    if args.cc_events_out:
        cc = (~ES) & (E > 3.0)
        d = np.asarray(z["dirs"], dtype=np.float64)[cc]
        Path(args.cc_events_out).parent.mkdir(parents=True, exist_ok=True)
        np.savez(args.cc_events_out, reco_dirs=d.astype(np.float32),
                 valid=np.ones(len(d), bool), energy_reco=E[cc].astype(np.float32),
                 note=np.asarray(f"v63 reco directions of TRUE CC clusters, r3 cats {lo}-{hi}, "
                                 "E>3 MeV, valid reco direction"))
        T = (d.T @ d) / len(d)
        w, _ = np.linalg.eigh(T)
        prov["cc_events"] = {"path": str(args.cc_events_out), "n": int(len(d)),
                             "inertia_eigenvalues": w.tolist(),
                             "mean_cos_burst": float(COS[cc].mean())}
        print(f"\nCC events for the direction map: {len(d)} dirs -> {args.cc_events_out}\n"
              f"  inertia eigenvalues {np.round(w, 4)} (isotropic 0.3333)")

    pj = out / f"ct_rescan_tables_provenance{args.prov_suffix}.json"
    pj.write_text(json.dumps(prov, indent=2))
    print(f"\nwrote {pj}")


if __name__ == "__main__":
    main()
