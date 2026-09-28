#!/usr/bin/env python3
"""Build likelihood tables from the r3 campaign's per-event outputs.

Three tables, all in the deployed layout (18 reco-cluster-energy bins 2-70 MeV, 100 cosine
bins on [-1, 1], raw histogram, per-row renormalised by the pipeline on load):

  1. pdf_ES,sel  -- cos(v63 reco electron direction, TRUE BURST direction) of TRUE-ES events
     that pass the deployed selection (CT v80 >= 0.80, E > 5 MeV).  This is the ES component
     the full-pipeline mixture needs.
  2. kinematic   -- cos(TRUE electron direction, TRUE neutrino direction) of the true-ES
     events scenario 1 fits (E > 3 MeV).  This is the right density when the fit is given
     TRUE directions.
  3. the mixtures f*pdf_ES,sel + (1-f)*flat, with a global f and with f(E).

WHY THESE ARE DIFFERENT FROM THE EXISTING TABLES.  `data/cosine_energy_pdf.npz` and the v62
/ v63 tables were built from cos(reco electron, TRUE ELECTRON), i.e. the ED angular
RESOLUTION.  The burst likelihood, however, evaluates cos(d_i, n) against a trial BURST
direction (`_pdf_likelihood`: `selected_dirs @ true_direction`), so the density it needs is
resolution CONVOLVED with the ES kinematic spread cos(true electron, nu).  Using a
resolution-only table makes every event look more informative than it is; that is exactly
the 0.04-0.11 deficit in <cos> seen in the section-16 closure test, and the reason
scenario 1 (TRUE directions, where the resolution is a delta function and only kinematics
remain) is 0.2 deg WORSE with the v63 table.

The energy axis is the RECO cluster energy (metadata col 10) for every table, because that
is what `select_electrons_from_run` passes to the lookup.  For the kinematic table the
true-energy-binned variant is stored alongside as `pdf_2d_true_energy_axis` for reference
only.

Slice: cats 673-900 by default (training slice).  Never the dev cats 623-672, never 400-621.

Usage:
  python3 python/ana/ed_r3_tables.py --cat-min 673 --cat-max 900 --out-dir <model dir>
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

from ana.burst_direction import load_pdf_table

CAMPAIGN = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-campaign/v63_matchfix_1000")
ENERGY_BINS = np.array([(2, 4), (4, 6), (6, 8), (8, 10), (10, 12), (12, 14), (14, 16),
                        (16, 18), (18, 20), (20, 22), (22, 24), (24, 26), (26, 28),
                        (28, 30), (30, 35), (35, 40), (40, 50), (50, 70)], dtype=float)
N_COS = 100
COS_EDGES = np.linspace(-1.0, 1.0, N_COS + 1)
COS_CENTERS = 0.5 * (COS_EDGES[:-1] + COS_EDGES[1:])
CT_THRESHOLD, MIN_E_SEL, MIN_E_SC1 = 0.80, 5.0, 3.0
PDF_FLOOR = 1e-4


def _norm(v):
    n = np.linalg.norm(v, axis=1, keepdims=True)
    return v / np.where(n > 0, n, 1.0)


def burst_dir(meta):
    """Same construction as ana.burst_direction._resolve_direction_inputs."""
    v = meta[:, 15:18]
    ok = np.linalg.norm(v, axis=1) > 0
    if not ok.any():
        return None
    d = _norm(v[ok]).mean(axis=0)
    n = np.linalg.norm(d)
    return d / n if n > 0 else None


def read_scenario(tar_path, scenario, want=("volumes", "reco", "pred")):
    with tarfile.open(tar_path) as tf:
        names = tf.getnames()
        vol = [n for n in names if n.startswith(scenario + "/") and n.endswith("volume_images/volumes.npz")]
        if not vol:
            return None
        pre = vol[0].rsplit("/volume_images/", 1)[0]
        out = {}
        out["metadata"] = np.asarray(np.load(io.BytesIO(tf.extractfile(vol[0]).read()),
                                             allow_pickle=True)["metadata"], dtype=np.float64)
        for key, fn in (("reco", "reco_directions.npz"), ("pred", "channel_predictions.npz")):
            if key not in want:
                continue
            n = f"{pre}/predictions/{fn}"
            out[key] = np.load(io.BytesIO(tf.extractfile(n).read()), allow_pickle=True) if n in names else None
    return out


def hist_table(cos, energy, label):
    """Raw per-energy-row histogram of cos, deployed layout."""
    pdf = np.zeros((len(ENERGY_BINS), N_COS))
    n_per = np.zeros(len(ENERGY_BINS), dtype=np.int64)
    width = COS_EDGES[1] - COS_EDGES[0]
    for i, (lo, hi) in enumerate(ENERGY_BINS):
        m = (energy >= lo) & (energy < hi)
        n_per[i] = int(m.sum())
        if n_per[i] > 0:
            c, _ = np.histogram(cos[m], bins=COS_EDGES)
            pdf[i] = c / (c.sum() * width)
    print(f"  {label}: {int(n_per.sum())} events, "
          f"{int((n_per > 0).sum())}/{len(ENERGY_BINS)} bins populated")
    return pdf, n_per


def fill_rows(pdf, n_per, min_count):
    """Replace rows with fewer than min_count events by the nearest well-populated row.

    An empty raw row would be floored and renormalised to a FLAT density by the pipeline,
    i.e. "an event at this energy carries no information", which is wrong: the ES density
    does not collapse above 18 MeV, there are simply no CT-selected events there to measure
    it.  Constant extrapolation keeps the table sane where the energy interpolation reaches
    into unmeasured bins.  Returns (filled pdf, mask of measured rows).
    """
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


def fill_empty(f, n, min_count):
    """Constant extrapolation of f(E) into bins with too few events."""
    f = np.asarray(f, dtype=np.float64).copy()
    meas = (n >= min_count) & np.isfinite(f)
    idx = np.arange(len(f))
    lo, hi = idx[meas][0], idx[meas][-1]
    for i in idx:
        if not meas[i]:
            f[i] = f[lo] if i < lo else (f[hi] if i > hi else f[max(j for j in idx[meas] if j < i)])
    return f, meas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cat-min", type=int, default=673)
    ap.add_argument("--cat-max", type=int, default=900)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--campaign", default=str(CAMPAIGN))
    ap.add_argument("--min-count", type=int, default=20,
                    help="min selected events for f(E) to count as measured in a bin")
    ap.add_argument("--row-min-count", type=int, default=50,
                    help="min events for a TABLE row to be used instead of extrapolated")
    args = ap.parse_args()
    assert args.cat_min >= 673 and args.cat_max <= 900, \
        "training slice is 673-900: 623-672 are dev cats, 400-621 are off limits, 901+ is evaluation"

    out = Path(args.out_dir)
    camp = Path(args.campaign)
    acc = {k: [] for k in ("cos_sel_es", "e_sel_es", "cos_sel_cc", "e_sel_cc",
                           "cos_kin", "e_kin", "etrue_kin")}
    cats, t0 = [], time.time()
    for n in range(args.cat_min, args.cat_max + 1):
        cat = f"cat{n:06d}"
        tar = camp / cat / f"{cat}_scenarios_slim.tar"
        if not tar.exists():
            continue
        try:
            s3 = read_scenario(tar, "scenario_3_full_pipeline")
            s1 = read_scenario(tar, "scenario_1_best_case", want=("volumes",))
        except Exception as e:  # noqa: BLE001
            print(f"  {cat}: {e!r}")
            continue
        if s3 is None or s3.get("reco") is None or s3.get("pred") is None:
            continue

        m = s3["metadata"]
        bd = burst_dir(m)
        if bd is None:
            continue
        d = _norm(np.asarray(s3["reco"]["reco_dirs"], dtype=np.float64))
        has = np.asarray(s3["reco"]["has_reco"]).astype(bool)
        ok = has & np.isfinite(d).all(axis=1) & (np.linalg.norm(d, axis=1) > 0)
        proba = np.asarray(s3["pred"]["y_pred_proba"], dtype=np.float64)
        sel = ok & (proba >= CT_THRESHOLD) & (m[:, 10] >= MIN_E_SEL)
        is_es = m[:, 3].astype(int) == 1
        c_burst = np.clip(d @ bd, -1.0, 1.0)
        acc["cos_sel_es"].append(c_burst[sel & is_es]); acc["e_sel_es"].append(m[sel & is_es, 10])
        acc["cos_sel_cc"].append(c_burst[sel & ~is_es]); acc["e_sel_cc"].append(m[sel & ~is_es, 10])

        # kinematic: scenario 1's population, TRUE electron vs TRUE neutrino direction
        m1 = s1["metadata"] if s1 else m
        bd1 = burst_dir(m1)
        te = m1[:, 7:10]
        good = (np.linalg.norm(te, axis=1) > 0) & (m1[:, 3].astype(int) == 1) & (m1[:, 10] >= MIN_E_SC1)
        if good.any() and bd1 is not None:
            acc["cos_kin"].append(np.clip(_norm(te[good]) @ bd1, -1.0, 1.0))
            acc["e_kin"].append(m1[good, 10])
            acc["etrue_kin"].append(m1[good, 11])
        cats.append(cat)
        if len(cats) % 50 == 0:
            print(f"  {len(cats)} cats, {time.time()-t0:.0f}s", flush=True)
    A = {k: (np.concatenate(v) if v else np.array([])) for k, v in acc.items()}
    print(f"\n{len(cats)} cats in {time.time()-t0:.0f}s")

    # ---------------------------------------------------------------- pdf_ES,sel
    print("\nTables:")
    pdf_es_raw, n_es = hist_table(A["cos_sel_es"], A["e_sel_es"], "pdf_ES,sel (CT-selected true ES)")
    pdf_es, good_es = fill_rows(pdf_es_raw, n_es, args.row_min_count)
    print(f"  rows measured (>= {args.row_min_count} ev): {int(good_es.sum())}/{len(n_es)}; "
          f"others filled from the nearest measured row")
    save(out / "cosine_energy_pdf_es_ctselected_r3.npz", pdf_es, n_es,
         "cos(v63 reco electron dir, TRUE BURST dir) of true-ES events passing "
         f"CT v80>={CT_THRESHOLD} and E>{MIN_E_SEL} MeV; r3 cats {args.cat_min}-{args.cat_max}; "
         "energy axis = reco cluster energy (metadata col 10); rows with "
         f"< {args.row_min_count} events filled from the nearest measured row",
         extra={"pdf_2d_raw": pdf_es_raw, "row_measured": good_es})

    # ---------------------------------------------------------------- purity f(E)
    n_tot = np.zeros(len(ENERGY_BINS)); n_esc = np.zeros(len(ENERGY_BINS))
    for i, (lo, hi) in enumerate(ENERGY_BINS):
        n_esc[i] = int(((A["e_sel_es"] >= lo) & (A["e_sel_es"] < hi)).sum())
        n_tot[i] = n_esc[i] + int(((A["e_sel_cc"] >= lo) & (A["e_sel_cc"] < hi)).sum())
    f_raw = np.divide(n_esc, n_tot, out=np.full(len(n_tot), np.nan), where=n_tot > 0)
    f_err = np.sqrt(np.clip(f_raw * (1 - f_raw), 0, None) / np.where(n_tot > 0, n_tot, 1))
    overall = float(n_esc.sum() / n_tot.sum())
    f, meas = fill_empty(f_raw, n_tot, args.min_count)
    np.savez(out / "purity_fE_ct080_e5_r3.npz", energy_bins=ENERGY_BINS, n_es=n_esc, n_tot=n_tot,
             f=f_raw, f_err=f_err, f_filled=f, overall_purity=np.float64(overall),
             n_cats=np.int64(len(cats)), cats=np.asarray(cats))
    print(f"\nr3 purity on cats {args.cat_min}-{args.cat_max}: overall f = {overall:.4f} "
          f"({int(n_tot.sum())} selected events, {n_tot.sum()/len(cats):.1f}/burst)")

    # ---------------------------------------------------------------- mixtures
    es_norm = load_pdf_table(out / "cosine_energy_pdf_es_ctselected_r3.npz", pdf_floor=PDF_FLOOR)["pdf"]
    flat = np.full_like(es_norm, 0.5)
    widths = COS_EDGES[1:] - COS_EDGES[:-1]
    for tag, fv in (("global", np.full(len(ENERGY_BINS), overall)), ("fE", f)):
        mix = fv[:, None] * es_norm + (1 - fv)[:, None] * flat
        mix = mix / np.sum(mix * widths[None, :], axis=1, keepdims=True)
        save(out / f"cosine_energy_pdf_mixture_ctsel_{tag}_flatcc.npz", mix, n_es,
             f"mixture f*pdf_ES,sel + (1-f)*flat CC, f = {'global %.4f' % overall if tag=='global' else 'f(E) measured on r3'}",
             extra={"f_of_E": fv})

    # ---------------------------------------------------------------- kinematic
    pdf_kin_raw, n_kin = hist_table(A["cos_kin"], A["e_kin"], "kinematic (true e vs true nu)")
    pdf_kin, good_kin = fill_rows(pdf_kin_raw, n_kin, args.row_min_count)
    pdf_kin_t_raw, n_kin_t = hist_table(A["cos_kin"], A["etrue_kin"], "kinematic (true-energy axis, reference)")
    pdf_kin_t, _ = fill_rows(pdf_kin_t_raw, n_kin_t, args.row_min_count)
    save(out / "cosine_energy_pdf_kinematic_r3.npz", pdf_kin, n_kin,
         "cos(TRUE electron dir, TRUE neutrino dir) of true-ES events with E>3 MeV; "
         f"r3 cats {args.cat_min}-{args.cat_max}; energy axis = reco cluster energy "
         "(matches what select_electrons_from_run passes to the lookup)",
         extra={"pdf_2d_true_energy_axis": pdf_kin_t,
                "n_events_per_bin_true_energy_axis": n_kin_t})

    # ---------------------------------------------------------------- comparison
    v63 = load_pdf_table(out / "cosine_energy_pdf.npz", pdf_floor=PDF_FLOOR)["pdf"]
    print(f"\npdf-weighted <cos> per energy bin")
    print(f"{'E [MeV]':>9} {'N_ES,sel':>9} {'f(E)':>6} {'meas':>5} | {'v63 (reso)':>10} "
          f"{'ES,sel':>8} {'actual':>8} | {'kinematic':>10} {'N_kin':>8}")
    rows = []
    for i, (lo, hi) in enumerate(ENERGY_BINS):
        mc = lambda p: float(np.sum(p[i] * COS_CENTERS) / np.sum(p[i]))
        m = (A["e_sel_es"] >= lo) & (A["e_sel_es"] < hi)
        act = float(A["cos_sel_es"][m].mean()) if m.sum() > 20 else float("nan")
        kv = mc(pdf_kin) if n_kin[i] > 0 else float("nan")
        rows.append(dict(bin=f"{int(lo)}-{int(hi)}", n_es=int(n_es[i]), f=float(f[i]),
                         measured=bool(meas[i]), v63=mc(v63), es_sel=mc(es_norm) if n_es[i] else None,
                         actual=act, kinematic=kv, n_kin=int(n_kin[i])))
        print(f"{int(lo):4d}-{int(hi):<4d} {int(n_es[i]):9d} {f[i]:6.3f} {str(bool(meas[i])):>5} | "
              f"{mc(v63):10.3f} {mc(es_norm):8.3f} {act:8.3f} | {kv:10.3f} {int(n_kin[i]):8d}")
    prov = {"campaign": str(camp), "cats": [args.cat_min, args.cat_max], "n_cats": len(cats),
            "ct_threshold": CT_THRESHOLD, "min_energy_selection": MIN_E_SEL,
            "overall_purity_r3": overall, "f_used": f.tolist(),
            "f_measured_mask": meas.tolist(), "n_tot_per_bin": n_tot.tolist(),
            "n_es_selected": int(len(A["cos_sel_es"])), "n_cc_selected": int(len(A["cos_sel_cc"])),
            "mean_cos_cc_selected": float(A["cos_sel_cc"].mean()),
            "n_kinematic": int(len(A["cos_kin"])),
            "cos_convention": "vs TRUE BURST direction (what the likelihood queries)",
            "comparison": rows}
    (out / "r3_tables_provenance.json").write_text(json.dumps(prov, indent=2))
    print(f"\nflat-CC check: <cos> of the {len(A['cos_sel_cc'])} selected CC events = "
          f"{A['cos_sel_cc'].mean():+.4f}")
    print(f"wrote {out / 'r3_tables_provenance.json'}")


if __name__ == "__main__":
    main()
