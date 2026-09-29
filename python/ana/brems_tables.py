#!/usr/bin/env python3
"""Likelihood-table variants for the brems / purity-conditioning study.

Built from the per-event table `brems_collect.py` wrote for the TRAINING SLICE (cats
673-900).  Nothing existing is overwritten: every file goes to --out-dir (the study area).

The deployed lookup is p(cos | x) with x = whatever `reconstruct_burst_direction` is handed
as `selected_energies`, interpolated linearly between the table's energy-bin centres.  Two
kinds of variant are produced:

  * "axis" variants -- the same 18-row layout as the deployed tables, but the row variable is
    a different energy estimate (reco main-cluster energy, E' = main + secondary MARLEY
    clusters, or the TRUE electron energy).  `brems_eval.py` passes the matching per-event
    variable.
  * "pseudo-grid" variants -- rows enumerate (fine energy node) x (CT-score node) pairs on a
    synthetic monotone axis, so a per-event purity f(E, score) can be expressed inside a
    table the pipeline reads unchanged.  `brems_eval.py` maps each event to the centre of its
    row, which the interpolator returns exactly.  A control variant with the same
    discretisation but f = f(E) isolates the purity model from the binning.

Usage:
  python3 python/ana/brems_tables.py --collect <collect_673_900.npz> --out-dir <study>/tables
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from ana.burst_direction import load_pdf_table, pdf_rows_for_energies

MODEL = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/neural-networks/"
             "electron_direction/three_plane_v63_matchfix_ft58_20260921_132520")
ENERGY_BINS = np.array([(2, 4), (4, 6), (6, 8), (8, 10), (10, 12), (12, 14), (14, 16),
                        (16, 18), (18, 20), (20, 22), (22, 24), (24, 26), (26, 28),
                        (28, 30), (30, 35), (35, 40), (40, 50), (50, 70)], dtype=float)
N_COS = 100
COS_EDGES = np.linspace(-1.0, 1.0, N_COS + 1)
COS_CENTERS = 0.5 * (COS_EDGES[:-1] + COS_EDGES[1:])
WIDTH = COS_EDGES[1] - COS_EDGES[0]
PDF_FLOOR = 1e-4
CT_MIN, E_MIN = 0.80, 5.0
# CT v80 saturates at ~0.92 on burst data, so the useful score axis inside the selected
# band is 0.80-0.92.  Edges = quintiles of the selected sample on the training slice.
SCORE_EDGES = np.array([0.80, 0.8196, 0.8383, 0.8566, 0.8746, 1.0001])
E_NODES = np.concatenate([np.arange(4.5, 20.0, 0.5), [21.0, 25.0, 35.0, 50.0]])


def hist_rows(cos, x, bins, label, min_count=50):
    pdf = np.zeros((len(bins), N_COS))
    n = np.zeros(len(bins), dtype=np.int64)
    for i, (lo, hi) in enumerate(bins):
        m = (x >= lo) & (x < hi)
        n[i] = int(m.sum())
        if n[i] > 0:
            c, _ = np.histogram(cos[m], bins=COS_EDGES)
            pdf[i] = c / (c.sum() * WIDTH)
    good = n >= min_count
    idx = np.arange(len(n))
    gi = idx[good]
    out = pdf.copy()
    for i in idx:
        if not good[i]:
            out[i] = pdf[gi[np.argmin(np.abs(gi - i))]]
    print(f"  {label}: {int(n.sum())} events, {int(good.sum())}/{len(n)} rows measured")
    return out, n, good


def normed(pdf):
    p = np.maximum(np.asarray(pdf, dtype=np.float64), PDF_FLOOR)
    return p / np.sum(p * WIDTH, axis=1, keepdims=True)


def purity(x_es, x_cc, bins, min_count=20):
    n_es = np.array([((x_es >= lo) & (x_es < hi)).sum() for lo, hi in bins], dtype=float)
    n_cc = np.array([((x_cc >= lo) & (x_cc < hi)).sum() for lo, hi in bins], dtype=float)
    tot = n_es + n_cc
    f = np.divide(n_es, tot, out=np.full(len(tot), np.nan), where=tot > 0)
    meas = (tot >= min_count) & np.isfinite(f)
    idx = np.arange(len(f))
    lo_i, hi_i = idx[meas][0], idx[meas][-1]
    out = f.copy()
    for i in idx:
        if not meas[i]:
            out[i] = f[lo_i] if i < lo_i else (f[hi_i] if i > hi_i else
                                              f[max(j for j in idx[meas] if j < i)])
    err = np.sqrt(np.clip(f * (1 - f), 0, None) / np.where(tot > 0, tot, 1))
    return out, f, err, n_es, tot, meas


def save(path, pdf, n_per, bins, note, extra=None):
    payload = dict(pdf_2d=np.asarray(pdf, dtype=np.float64), cosine_bin_edges=COS_EDGES,
                   cosine_bin_centers=COS_CENTERS, energy_bins=np.asarray(bins, dtype=np.float64),
                   n_events_per_bin=np.asarray(n_per),
                   smoothing_method=np.asarray("Raw histogram (no smoothing)"),
                   table_note=np.asarray(note))
    if extra:
        payload.update(extra)
    np.savez(path, **payload)
    print(f"  wrote {path.name}")


def mixture(f_vec, es_pdf, cc_pdf=None):
    f = np.asarray(f_vec, dtype=np.float64)[:, None]
    cc = np.full_like(es_pdf, 0.5) if cc_pdf is None else np.asarray(cc_pdf, dtype=np.float64)
    mix = f * es_pdf + (1.0 - f) * cc
    return mix / np.sum(mix * WIDTH, axis=1, keepdims=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collect", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    z = np.load(args.collect, allow_pickle=True)
    A = np.asarray(z["table"], dtype=np.float64)
    C = {c: A[:, i] for i, c in enumerate(list(z["cols"]))}
    cats = np.asarray(z["cats"])
    assert cats.min() >= 673 and cats.max() <= 900, "tables must be built on the slice 673-900"

    sel = (C["ct"] >= CT_MIN) & (C["e_reco"] >= E_MIN)
    es = C["is_es"] == 1
    S, Ses, Scc = sel, sel & es, sel & ~es
    print(f"slice: {len(cats)} cats, {int(S.sum())} selected events "
          f"({S.sum()/len(cats):.1f}/burst), purity {Ses.sum()/S.sum():.4f}")
    f_glob = float(Ses.sum() / S.sum())

    # ---- per-event conditioning variables -------------------------------------------------
    e_reco = C["e_reco"]
    e_true = C["e_true"]
    e_prime = np.where(es & np.isfinite(C["e_sec_es"]), e_reco + np.nan_to_num(C["e_sec_es"]), e_reco)
    cosb = C["cos_burst"]
    prov = {"n_cats": int(len(cats)), "n_selected": int(S.sum()), "f_global": f_glob,
            "cat_range": [int(cats.min()), int(cats.max())],
            "mean_cos_cc_selected": float(cosb[Scc].mean()), "variants": {}}

    # ---------------------------------------------------------------- axis variants
    axes = {"ereco": e_reco, "eprime": e_prime, "etrue": e_true}
    for tag, x in axes.items():
        print(f"\n[axis {tag}]")
        es_pdf_raw, n_es, good = hist_rows(cosb[Ses], x[Ses], ENERGY_BINS, f"pdf_ES,sel({tag})")
        es_pdf = normed(es_pdf_raw)
        f_of_x, f_raw, f_err, n_esb, n_tot, meas = purity(x[Ses], x[Scc], ENERGY_BINS)
        cc_raw, n_cc, _ = hist_rows(cosb[Scc], x[Scc], ENERGY_BINS, f"pdf_CC,meas({tag})",
                                    min_count=200)
        cc_pdf = normed(cc_raw)
        save(out / f"tbl_{tag}_es.npz", es_pdf, n_es, ENERGY_BINS,
             f"cos(v63 reco, TRUE BURST) of CT-selected true ES, axis = {tag}")
        save(out / f"tbl_{tag}_fE.npz", mixture(f_of_x, es_pdf), n_es, ENERGY_BINS,
             f"mixture f({tag}) * pdf_ES,sel({tag}) + (1-f) * flat",
             extra={"f_of_E": f_of_x})
        save(out / f"tbl_{tag}_glob.npz", mixture(np.full(len(ENERGY_BINS), f_glob), es_pdf),
             n_es, ENERGY_BINS, f"mixture global f={f_glob:.4f} * pdf_ES,sel({tag}) + flat",
             extra={"f_of_E": np.full(len(ENERGY_BINS), f_glob)})
        if tag == "ereco":
            for s, lbl in ((0.8, "g080"), (1.2, "g120")):
                fv = np.full(len(ENERGY_BINS), min(f_glob * s, 0.99))
                save(out / f"tbl_ereco_{lbl}.npz", mixture(fv, es_pdf), n_es, ENERGY_BINS,
                     f"mixture global f x {s} = {fv[0]:.4f}", extra={"f_of_E": fv})
            save(out / "tbl_ereco_fE_ccmeas.npz", mixture(f_of_x, es_pdf, cc_pdf), n_es,
                 ENERGY_BINS, "mixture f(E) * pdf_ES,sel + (1-f) * MEASURED CC density",
                 extra={"f_of_E": f_of_x, "n_cc_per_bin": n_cc})
        prov["variants"][tag] = {"f": f_of_x.tolist(), "f_raw": f_raw.tolist(),
                                 "f_err": f_err.tolist(), "n_es": n_esb.tolist(),
                                 "n_tot": n_tot.tolist(), "measured": meas.tolist(),
                                 "n_cc_per_bin": n_cc.tolist()}

    # ---------------------------------------------------------------- pseudo-grid variants
    print("\n[pseudo grid: fine energy x CT score]")
    es_tab = load_pdf_table(out / "tbl_ereco_es.npz", pdf_floor=PDF_FLOOR)
    es_nodes = pdf_rows_for_energies(es_tab, E_NODES)                       # (n_e, n_cos)
    f_ereco = np.asarray(prov["variants"]["ereco"]["f"])
    f_node_E = np.interp(E_NODES, ENERGY_BINS.mean(axis=1), f_ereco)

    i_s_es = np.clip(np.digitize(C["ct"][Ses], SCORE_EDGES) - 1, 0, len(SCORE_EDGES) - 2)
    i_s_cc = np.clip(np.digitize(C["ct"][Scc], SCORE_EDGES) - 1, 0, len(SCORE_EDGES) - 2)
    n_s = len(SCORE_EDGES) - 1
    f_score = np.zeros(n_s)
    n_s_tot = np.zeros(n_s)
    for j in range(n_s):
        a = int((i_s_es == j).sum()); b = int((i_s_cc == j).sum())
        n_s_tot[j] = a + b
        f_score[j] = a / max(a + b, 1)
    print("  P(ES|score): " + "  ".join(
        f"[{SCORE_EDGES[j]:.2f},{SCORE_EDGES[j+1]:.2f}) {f_score[j]:.3f} (n={int(n_s_tot[j])})"
        for j in range(n_s)))

    # 2-D purity P(ES | coarse energy bin, score bin), coarse = the 18 deployed rows
    i_e_es = np.clip(np.digitize(C["e_reco"][Ses], ENERGY_BINS[:, 0]) - 1, 0, len(ENERGY_BINS) - 1)
    i_e_cc = np.clip(np.digitize(C["e_reco"][Scc], ENERGY_BINS[:, 0]) - 1, 0, len(ENERGY_BINS) - 1)
    f2 = np.full((len(ENERGY_BINS), n_s), np.nan)
    n2 = np.zeros((len(ENERGY_BINS), n_s))
    for i in range(len(ENERGY_BINS)):
        for j in range(n_s):
            a = int(((i_e_es == i) & (i_s_es == j)).sum())
            b = int(((i_e_cc == i) & (i_s_cc == j)).sum())
            n2[i, j] = a + b
            if a + b >= 30:
                f2[i, j] = a / (a + b)
    # fill: fall back to f(score) then to global
    for i in range(len(ENERGY_BINS)):
        for j in range(n_s):
            if not np.isfinite(f2[i, j]):
                f2[i, j] = f_score[j] if n_s_tot[j] >= 200 else f_glob
    f2_node = np.empty((len(E_NODES), n_s))
    e_centers = ENERGY_BINS.mean(axis=1)
    for j in range(n_s):
        f2_node[:, j] = np.interp(E_NODES, e_centers, f2[:, j])

    n_rows = len(E_NODES) * n_s
    centers = 5.0 + np.arange(n_rows, dtype=float)
    ps_bins = np.column_stack([centers - 0.5, centers + 0.5])
    es_grid = np.repeat(es_nodes, n_s, axis=0)                              # row = i_e*n_s + i_s
    f_ctl = np.repeat(f_node_E, n_s)
    f_sc = np.tile(f_score, len(E_NODES))
    f_2d = f2_node.reshape(-1)
    n_dummy = np.full(n_rows, 1000, dtype=np.int64)
    meta = {"e_nodes": E_NODES, "score_edges": SCORE_EDGES, "n_score": n_s,
            "row_centers": centers, "f_score": f_score, "f2": f2, "n2": n2}
    for lbl, fv, note in (
            ("ps_ctl_fE", f_ctl, "pseudo-grid control: f = f(E_reco), score axis unused"),
            ("ps_ctl_glob", np.full(n_rows, f_glob), "pseudo-grid control: f = global"),
            ("ps_score", f_sc, "pseudo-grid: f = P(ES | CT score bin)"),
            ("ps_score2d", f_2d, "pseudo-grid: f = P(ES | E_reco bin, CT score bin)")):
        save(out / f"tbl_{lbl}.npz", mixture(fv, normed(es_grid)), n_dummy, ps_bins,
             note + f"; ES component = pdf_ES,sel(cos|E_reco) interpolated on the node grid",
             extra={"f_of_E": fv, **meta})
    prov["pseudo"] = {"e_nodes": E_NODES.tolist(), "score_edges": SCORE_EDGES.tolist(),
                      "f_score": f_score.tolist(), "n_score_tot": n_s_tot.tolist(),
                      "f2": np.where(np.isfinite(f2), f2, None).tolist(), "n2": n2.tolist(),
                      "row_centers": centers.tolist()}
    (out / "brems_tables_provenance.json").write_text(json.dumps(prov, indent=2, default=float))
    print(f"\nwrote {out/'brems_tables_provenance.json'}")

    # ---------------------------------------------------------------- gate vs the deployed r3 tables
    print("\ngate: my pdf_ES,sel(E_reco) vs the deployed cosine_energy_pdf_es_ctselected_r3.npz")
    ref = load_pdf_table(MODEL / "cosine_energy_pdf_es_ctselected_r3.npz", pdf_floor=PDF_FLOOR)
    mine = load_pdf_table(out / "tbl_ereco_es.npz", pdf_floor=PDF_FLOOR)
    d = np.abs(ref["pdf"] - mine["pdf"])
    print(f"  max|dpdf| = {d.max():.3e}   mean|dpdf| = {d.mean():.3e}")
    rf = np.load(MODEL / "purity_fE_ct080_e5_r3.npz", allow_pickle=True)
    print("  deployed f(E) : " + " ".join(f"{v:.3f}" for v in rf["f_filled"][1:8]))
    print("  my       f(E) : " + " ".join(f"{v:.3f}" for v in f_ereco[1:8]))
    print(f"  deployed overall f {float(rf['overall_purity']):.4f}  mine {f_glob:.4f}")


if __name__ == "__main__":
    main()
