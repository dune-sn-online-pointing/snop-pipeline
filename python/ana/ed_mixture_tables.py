#!/usr/bin/env python3
"""Build mixture cosine-vs-energy likelihood tables for the contaminated deployed selection.

    p(cos | E) = f(E) * pdf_ES(cos | E) + (1 - f(E)) * pdf_CC(cos | E)

with f(E) the measured ES purity of the CT-selected sample (ed_mixture_purity.py) and
pdf_CC either flat (reconstructed CC directions are anisotropic in the DETECTOR frame,
not versus the neutrino, so versus cos-to-burst they are flat to first order) or the
measured CC table data/cosine_energy_pdf_cc.npz.

The output has the deployed table layout, so it deploys through PDF_PATH with no code
change.  Components are floored and per-row renormalised exactly as the pipeline's own
load_pdf_table does, so each mixture row is already a proper density in cos on [-1, 1].

f(E) is only measured where the CT-selected sample has events (the CT v80 keeps almost
nothing above ~18 MeV).  Bins with fewer than `--min-count` events take the nearest
measured bin's value (constant extrapolation); no event of the deployed selection can
land there, the value only affects interpolation at the edge of the populated range.

Usage:
  python3 python/ana/ed_mixture_tables.py --es-table <v63 pdf> --purity <purity npz> \
      --out-dir <model dir> [--cc-table data/cosine_energy_pdf_cc.npz]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from ana.burst_direction import load_pdf_table

PDF_FLOOR = 1e-4


def flat_pdf(shape):
    """Uniform density in cos on [-1, 1]: integral = 1 -> height 0.5."""
    return np.full(shape, 0.5, dtype=np.float64)


def resolve_f(purity_npz, min_count=20):
    d = np.load(purity_npz, allow_pickle=True)
    f = np.asarray(d["f"], dtype=np.float64).copy()
    n = np.asarray(d["n_tot"], dtype=np.float64)
    measured = (n >= min_count) & np.isfinite(f)
    if not measured.any():
        raise SystemExit("no energy bin has enough statistics to measure f(E)")
    idx = np.arange(len(f))
    first, last = idx[measured][0], idx[measured][-1]
    for i in idx:
        if not measured[i]:
            f[i] = f[first] if i < first else (f[last] if i > last else f[max(j for j in idx[measured] if j < i)])
    return f, measured, float(d["overall_purity"]), n


def write_table(path, pdf, ref, note, extra=None):
    payload = dict(pdf_2d=pdf,
                   cosine_bin_edges=ref["cos_edges"],
                   cosine_bin_centers=ref["cos_centers"],
                   energy_bins=np.asarray(ref["energy_bins"], dtype=np.int64),
                   n_events_per_bin=ref["n_events_per_bin"],
                   smoothing_method=np.asarray(note))
    if extra:
        payload.update(extra)
    np.savez(path, **payload)
    print(f"wrote {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--es-table", required=True)
    ap.add_argument("--cc-table", default=str(_HERE.parents[1] / "data" / "cosine_energy_pdf_cc.npz"))
    ap.add_argument("--purity", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--min-count", type=int, default=20)
    ap.add_argument("--prefix", default="cosine_energy_pdf_mixture")
    args = ap.parse_args()

    es = load_pdf_table(args.es_table, pdf_floor=PDF_FLOOR)
    pdf_es = es["pdf"]
    src = np.load(args.es_table, allow_pickle=True)
    ref = {"cos_edges": es["cos_edges"], "cos_centers": es["cos_centers"],
           "energy_bins": es["energy_bins"],
           "n_events_per_bin": np.asarray(src["n_events_per_bin"])}

    f, measured, overall, n_tot = resolve_f(args.purity, args.min_count)
    pdf_flat = flat_pdf(pdf_es.shape)
    cc = load_pdf_table(args.cc_table, pdf_floor=PDF_FLOOR)
    pdf_cc = cc["pdf"]
    if pdf_cc.shape != pdf_es.shape:
        raise SystemExit(f"CC table shape {pdf_cc.shape} != ES table shape {pdf_es.shape}")

    out = Path(args.out_dir)
    variants = {
        "fE_flatcc":      (f, pdf_flat, "mixture f(E)*ES_v63 + (1-f(E))*flat CC"),
        "fE_ccmeas":      (f, pdf_cc, "mixture f(E)*ES_v63 + (1-f(E))*measured CC table"),
        "global_flatcc":  (np.full_like(f, overall), pdf_flat,
                           f"mixture with a single global f={overall:.4f} + flat CC"),
        "fE075_flatcc":   (np.clip(f * 0.75, 0.01, 0.99), pdf_flat,
                           "mixture f(E)*0.75 (purity sensitivity) + flat CC"),
        "fE125_flatcc":   (np.clip(f * 1.25, 0.01, 0.99), pdf_flat,
                           "mixture f(E)*1.25 (purity sensitivity) + flat CC"),
    }
    summary = {"es_table": args.es_table, "cc_table": args.cc_table, "purity": args.purity,
               "overall_purity": overall, "min_count": args.min_count,
               "f_used": f.tolist(), "f_measured_mask": measured.tolist(),
               "n_tot_per_bin": n_tot.tolist(), "variants": {}}
    for name, (fv, cc_pdf, note) in variants.items():
        mix = fv[:, None] * pdf_es + (1.0 - fv)[:, None] * cc_pdf
        widths = ref["cos_edges"][1:] - ref["cos_edges"][:-1]
        norm = np.sum(mix * widths[None, :], axis=1)
        if not np.allclose(norm, 1.0, atol=1e-8):
            mix = mix / norm[:, None]
        path = out / f"{args.prefix}_{name}.npz"
        write_table(path, mix, ref, note, extra={"f_of_E": fv, "mixture_note": np.asarray(note)})
        mc = np.sum(mix * ref["cos_centers"][None, :], axis=1) / np.sum(mix, axis=1)
        summary["variants"][name] = {"path": str(path), "f": fv.tolist(),
                                     "mean_cos_per_bin": [round(float(x), 4) for x in mc]}
    (out / f"{args.prefix}_provenance.json").write_text(json.dumps(summary, indent=2))

    print(f"\noverall ES purity f = {overall:.4f}")
    print(f"{'E bin':>10} {'n_sel':>8} {'f(E)':>7} {'meas':>5} | pdf-weighted <cos>: "
          f"{'ES v63':>8} {'mixture':>8}")
    mix = variants['fE_flatcc'][0][:, None] * pdf_es + (1 - variants['fE_flatcc'][0])[:, None] * pdf_flat
    for i, (lo, hi) in enumerate(ref["energy_bins"]):
        mc_es = float(np.sum(pdf_es[i] * ref["cos_centers"]) / np.sum(pdf_es[i]))
        mc_mx = float(np.sum(mix[i] * ref["cos_centers"]) / np.sum(mix[i]))
        print(f"{int(lo):4d}-{int(hi):<5d} {n_tot[i]:8.0f} {f[i]:7.3f} {str(bool(measured[i])):>5} | "
              f"{mc_es:8.3f} {mc_mx:8.3f}")


if __name__ == "__main__":
    main()
