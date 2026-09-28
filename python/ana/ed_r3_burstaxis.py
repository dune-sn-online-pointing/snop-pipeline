#!/usr/bin/env python3
"""Burst-axis likelihood tables for the true-ES / reco-direction scenarios (2, 5, 6).

Those scenarios fit true-ES events that the CT never filtered, with v63 reconstructed
directions.  The density their likelihood queries is

    p( cos(reco electron dir, BURST dir) | E_reco )

which is the ED resolution CONVOLVED with the ES kinematic spread cos(true e, nu) -- not the
resolution alone, which is what `data/cosine_energy_pdf.npz` and the v62/v63 tables encode
(they were built from cos(reco, TRUE ELECTRON); see section 20 of the ED doc).

Built on true-ES events with a valid reco direction, NO CT filter, one table per energy cut
(E > 3 / 5 / 10 MeV for scenarios 2 / 6 / 5).  The cut only changes the single energy row it
straddles -- rows below the cut are never queried and rows above it are cut-independent -- so
the three tables are nearly identical; the script prints the per-row differences so the
choice can be justified rather than assumed.

Also builds the same table from a second campaign (default: the v80_fixed_1000 r2-era
campaign, ED v58) so that what the DEPLOYED table should have been can be quantified.

Usage:
  python3 python/ana/ed_r3_burstaxis.py --cat-min 673 --cat-max 900 --out-dir <model dir>
  python3 python/ana/ed_r3_burstaxis.py --cat-min 673 --cat-max 900 --out-dir <dir> \
      --campaign <v80_fixed_1000> --prefix cosine_energy_pdf_burstaxis_v58era --no-mixtures
"""
import argparse
import io
import json
import sys
import tarfile
import time
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

R3 = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-campaign/v63_matchfix_1000")
ENERGY_BINS = np.array([(2, 4), (4, 6), (6, 8), (8, 10), (10, 12), (12, 14), (14, 16),
                        (16, 18), (18, 20), (20, 22), (22, 24), (24, 26), (26, 28),
                        (28, 30), (30, 35), (35, 40), (40, 50), (50, 70)], dtype=float)
N_COS = 100
COS_EDGES = np.linspace(-1.0, 1.0, N_COS + 1)
COS_CENTERS = 0.5 * (COS_EDGES[:-1] + COS_EDGES[1:])
CUTS = {"e3": 3.0, "e5": 5.0, "e10": 10.0}


def _norm(v):
    n = np.linalg.norm(v, axis=1, keepdims=True)
    return v / np.where(n > 0, n, 1.0)


def burst_dir(meta):
    v = meta[:, 15:18]
    ok = np.linalg.norm(v, axis=1) > 0
    if not ok.any():
        return None
    d = _norm(v[ok]).mean(axis=0)
    n = np.linalg.norm(d)
    return d / n if n > 0 else None


def read_sc2(tar_path):
    """metadata + reco dirs of the true-ES / reco-direction scenario (2, 5 and 6 share them)."""
    with tarfile.open(tar_path) as tf:
        names = tf.getnames()
        for scen in ("scenario_2_perfect_ct", "scenario_6_perfect_ct_e_gt_5mev",
                     "scenario_5_perfect_ct_e_gt_10mev"):
            vol = [n for n in names if n.startswith(scen + "/") and n.endswith("volume_images/volumes.npz")]
            if not vol:
                continue
            pre = vol[0].rsplit("/volume_images/", 1)[0]
            rn = f"{pre}/predictions/reco_directions.npz"
            if rn not in names:
                continue
            m = np.asarray(np.load(io.BytesIO(tf.extractfile(vol[0]).read()),
                                   allow_pickle=True)["metadata"], dtype=np.float64)
            d = np.load(io.BytesIO(tf.extractfile(rn).read()), allow_pickle=True)
            return m, np.asarray(d["reco_dirs"], dtype=np.float64), np.asarray(d["has_reco"]).astype(bool)
    return None


def hist_table(cos, energy):
    pdf = np.zeros((len(ENERGY_BINS), N_COS))
    n_per = np.zeros(len(ENERGY_BINS), dtype=np.int64)
    w = COS_EDGES[1] - COS_EDGES[0]
    for i, (lo, hi) in enumerate(ENERGY_BINS):
        m = (energy >= lo) & (energy < hi)
        n_per[i] = int(m.sum())
        if n_per[i] > 0:
            c, _ = np.histogram(cos[m], bins=COS_EDGES)
            pdf[i] = c / (c.sum() * w)
    return pdf, n_per


def fill_rows(pdf, n_per, min_count):
    pdf = np.array(pdf, dtype=np.float64, copy=True)
    good = np.asarray(n_per) >= min_count
    if not good.any():
        raise SystemExit("no energy row has enough statistics")
    idx = np.arange(len(n_per))
    gi = idx[good]
    for i in idx:
        if not good[i]:
            pdf[i] = pdf[gi[np.argmin(np.abs(gi - i))]]
    return pdf, good


def save(path, pdf, n_per, note, extra=None):
    payload = dict(pdf_2d=pdf, cosine_bin_edges=COS_EDGES, cosine_bin_centers=COS_CENTERS,
                   energy_bins=ENERGY_BINS.astype(np.int64), n_events_per_bin=n_per,
                   smoothing_method=np.asarray("Raw histogram (no smoothing)"),
                   table_note=np.asarray(note))
    if extra:
        payload.update(extra)
    np.savez(path, **payload)
    print(f"wrote {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cat-min", type=int, default=673)
    ap.add_argument("--cat-max", type=int, default=900)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--campaign", default=str(R3))
    ap.add_argument("--prefix", default="cosine_energy_pdf_burstaxis_r3")
    ap.add_argument("--row-min-count", type=int, default=50)
    args = ap.parse_args()
    assert args.cat_min >= 673 and args.cat_max <= 900, \
        "training slice is 673-900 (623-672 are dev cats, 400-621 off limits, 901+ evaluation)"

    out = Path(args.out_dir)
    camp = Path(args.campaign)
    cos_all, e_all, cats = [], [], []
    t0 = time.time()
    for n in range(args.cat_min, args.cat_max + 1):
        cat = f"cat{n:06d}"
        tar = camp / cat / f"{cat}_scenarios_slim.tar"
        if not tar.exists():
            continue
        got = read_sc2(tar)
        if got is None:
            continue
        m, d, has = got
        bd = burst_dir(m)
        if bd is None:
            continue
        d = _norm(d)
        ok = has & np.isfinite(d).all(axis=1) & (np.linalg.norm(d, axis=1) > 0) \
            & (m[:, 3].astype(int) == 1)          # TRUE ES, no CT filter
        if not ok.any():
            continue
        cos_all.append(np.clip(d[ok] @ bd, -1.0, 1.0))
        e_all.append(m[ok, 10])
        cats.append(cat)
    cos_all = np.concatenate(cos_all)
    e_all = np.concatenate(e_all)
    print(f"{len(cats)} cats, {len(cos_all)} true-ES events with a reco direction, "
          f"{time.time()-t0:.0f}s")

    tables, prov_rows = {}, {}
    for tag, cut in CUTS.items():
        m = e_all >= cut
        raw, n_per = hist_table(cos_all[m], e_all[m])
        pdf, good = fill_rows(raw, n_per, args.row_min_count)
        tables[tag] = (pdf, n_per, good)
        save(out / f"{args.prefix}_{tag}.npz", pdf, n_per,
             f"cos(v63 reco electron dir, TRUE BURST dir) of true-ES events (NO CT filter) "
             f"with E_reco > {cut} MeV; campaign {camp.name}, cats {args.cat_min}-{args.cat_max}; "
             f"energy axis = reco cluster energy (col 10); rows with < {args.row_min_count} "
             "events filled from the nearest measured row",
             extra={"pdf_2d_raw": raw, "row_measured": good, "energy_cut": np.float64(cut)})
        prov_rows[tag] = {"cut": cut, "n_events": int(n_per.sum()),
                          "n_per_bin": n_per.tolist(), "rows_measured": good.tolist()}

    # how much do the three tables actually differ?
    print(f"\nrow-by-row <cos> of the three cuts (only the row straddling a cut can differ)")
    print(f"{'E [MeV]':>9} " + " ".join(f"{t:>16}" for t in CUTS) + "   max|d<cos>|")
    diffs = []
    for i, (lo, hi) in enumerate(ENERGY_BINS):
        vals, ns = [], []
        for t in CUTS:
            pdf, n_per, _ = tables[t]
            vals.append(float(np.sum(pdf[i] * COS_CENTERS) / np.sum(pdf[i])))
            ns.append(int(n_per[i]))
        d = max(vals) - min(vals)
        diffs.append((f"{int(lo)}-{int(hi)}", d, ns))
        print(f"{int(lo):4d}-{int(hi):<4d} " +
              " ".join(f"{v:7.3f}(N={n:6d})" for v, n in zip(vals, ns)) + f"   {d:.4f}")
    prov = {"campaign": str(camp), "cats": [args.cat_min, args.cat_max], "n_cats": len(cats),
            "n_events_no_cut": int(len(cos_all)), "selection": "true-ES, valid reco dir, NO CT cut",
            "cos_convention": "vs TRUE BURST direction (what the likelihood queries)",
            "energy_axis": "reco cluster energy, metadata col 10",
            "cuts": prov_rows,
            "row_mean_cos_by_cut": {t: [float(np.sum(tables[t][0][i] * COS_CENTERS) /
                                        np.sum(tables[t][0][i])) for i in range(len(ENERGY_BINS))]
                                    for t in CUTS},
            "max_row_mean_cos_spread": {lab: d for lab, d, _ in diffs}}
    (out / f"{args.prefix}_provenance.json").write_text(json.dumps(prov, indent=2))
    print(f"wrote {out / (args.prefix + '_provenance.json')}")


if __name__ == "__main__":
    main()
