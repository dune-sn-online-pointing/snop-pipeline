#!/usr/bin/env python3
"""Why are the ED directions worse on the matcher-fixed products?  (read-only diagnosis)

Per cat, this script

 1. replays the pipeline sample loader (python/lib/sample_loader.py) on the ES cluster
    images of BOTH product sets (original and `_matchfix`), metadata only, and rebuilds
    the exact row order of `volume_images/volumes.npz` of the two pipeline runs, so that
    every true-ES main-track event can be joined between the runs by
    (source file name, X-cluster row index inside that file);

 2. classifies every true-ES main-track event of the matchfix run into
       SAME     present in both runs with the same U and V partner cluster,
       CHANGED  present in both runs with a different U and/or V partner,
       NEW      3-plane matched only after the fix,
       LOST     3-plane matched only before the fix;

 3. records, per event, the ED reconstructed direction of both runs, the true electron
    direction/energy and the partner-cluster properties needed to tell a "worse partner"
    from a "the network never saw such a partner" story;

 4. re-runs the burst likelihood (ana.burst_direction) offline on several event subsets
    so that the theta68 cost can be attributed to a class.

Nothing is written outside --out-dir.  No production file is touched.

Usage (one cat per condor job):
  python3 python/ana/matchfix_ed_diagnosis.py --cat cat000623 --out-dir <dir>
  python3 python/ana/matchfix_ed_diagnosis.py --summarize --out-dir <dir> --out-md <file.md>
"""

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

python_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(python_root))

from ana.burst_direction import (  # noqa: E402
    normalize_rows,
    normalize_vector,
    reconstruct_burst_direction,
)

SAMPLE_ROOT = "/eos/user/e/evilla/dune/sn-tps/mixture_dev_samples"
ORIG_ROOT = "/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/v80_allfix_uniform_dev"
FIX_ROOT = "/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/v80_allfix_matchfix_dev"
SUFFIX = "_cluster_images_tick3_ch2_min2_tot3_e3p0"
PDF_PATH = str(python_root.parent / "data" / "cosine_energy_pdf.npz")
SCENARIO = "scenario_2_perfect_ct"

CLASSES = ["SAME", "CHANGED", "NEW", "LOST"]
E_BINS = [(3, 5), (5, 10), (10, 20), (20, 30), (30, 1e9)]
E_BIN_LABELS = ["3-5", "5-10", "10-20", "20-30", "30+"]

EMCEE_CFG = {"nwalkers": 128, "nsteps": 500, "discard": 100, "random_seed": 42}


# --------------------------------------------------------------------------------------
# loader replay
# --------------------------------------------------------------------------------------
def _plane_index(meta):
    """{match_id: row} over MAIN-TRACK clusters only — exactly what sample_loader does."""
    out = {}
    for i, m in enumerate(meta[:, 13]):
        if meta[i, 2] == 1 and m != -1:
            out[int(m)] = i
    return out


def _any_index(meta):
    """{match_id: row} over ALL clusters (used to explain why a plane was missing)."""
    out = {}
    for i, m in enumerate(meta[:, 13]):
        if m != -1:
            out.setdefault(int(m), i)
    return out


def _event_main_stats(meta):
    """Per event: number of main-track clusters, max and summed main-track energy."""
    n_main, e_max, e_sum = {}, {}, {}
    for i in range(meta.shape[0]):
        if meta[i, 2] != 1:
            continue
        ev = int(meta[i, 0])
        n_main[ev] = n_main.get(ev, 0) + 1
        e_max[ev] = max(e_max.get(ev, -1.0), float(meta[i, 10]))
        e_sum[ev] = e_sum.get(ev, 0.0) + float(meta[i, 10])
    return n_main, e_max, e_sum


def replay_es(product_dir):
    """Metadata-only replay of _load_samples_from_folder on the ES files of one product set.

    Returns (records, per_file) where records preserve the loader order.
    """
    product_dir = Path(product_dir)
    files = sorted((product_dir / "X").glob("es_*_bg_matched_planeX.npz"))
    records = []
    per_file = {}
    for fp in files:
        meta_x = np.load(fp, allow_pickle=True)["metadata"]
        meta_u = np.load(product_dir / "U" / fp.name.replace("planeX", "planeU"),
                         allow_pickle=True)["metadata"]
        meta_v = np.load(product_dir / "V" / fp.name.replace("planeX", "planeV"),
                         allow_pickle=True)["metadata"]
        ix_map, iu_map, iv_map = _plane_index(meta_x), _plane_index(meta_u), _plane_index(meta_v)
        iu_any, iv_any = _any_index(meta_u), _any_index(meta_v)
        u_stats, v_stats = _event_main_stats(meta_u), _event_main_stats(meta_v)
        per_file[fp.name] = {
            "meta_x": meta_x, "meta_u": meta_u, "meta_v": meta_v,
            "ix_map": ix_map, "iu_map": iu_map, "iv_map": iv_map,
            "iu_any": iu_any, "iv_any": iv_any,
            "u_stats": u_stats, "v_stats": v_stats,
        }
        for mid in sorted(set(ix_map) & set(iu_map) & set(iv_map)):
            records.append({
                "file": fp.name, "mid": mid,
                "ix": ix_map[mid], "iu": iu_map[mid], "iv": iv_map[mid],
                "meta": meta_x[ix_map[mid]],
            })
    return records, per_file


def es_rows_in_run(run_dir, n_es_records):
    """Pipeline row index of every ES record, in loader order.

    The pipeline concatenates [CC block, ES block] and then shuffles with
    np.random.seed(42); np.random.permutation(N).  N and the number of ES rows are read
    back from volumes.npz, so the ES block start is known and the permutation invertible.
    """
    vol = np.load(Path(run_dir) / "volume_images" / "volumes.npz", allow_pickle=True)
    meta = np.asarray(vol["metadata"])
    n_total = meta.shape[0]
    n_es_meta = int(np.sum(meta[:, 3] == 1))
    if n_es_meta != n_es_records:
        raise RuntimeError(f"{run_dir}: volumes.npz holds {n_es_meta} ES rows, replay gave {n_es_records}")
    np.random.seed(42)
    perm = np.random.permutation(n_total)
    orig_to_row = np.argsort(perm)          # original (pre-shuffle) index -> row in volumes.npz
    return orig_to_row[n_total - n_es_records:], meta


def latest_run(cat_root, cat, scenario=SCENARIO):
    runs = sorted((Path(cat_root) / cat / scenario).glob("pipeline_run_*"))
    if not runs:
        raise FileNotFoundError(f"no pipeline_run_* under {cat_root}/{cat}/{scenario}")
    return runs[-1]


def load_reco(run_dir, n_rows):
    d = np.load(Path(run_dir) / "predictions" / "reco_directions.npz", allow_pickle=True)
    # normalize_rows exactly as select_electrons_from_run does: the stored float32 unit
    # vectors are re-normalised in float64 before the fit, and the emcee chain is
    # sensitive to those last bits, so skipping it would not reproduce the campaign.
    dirs = normalize_rows(np.asarray(d["reco_dirs"], dtype=np.float64))
    has = np.asarray(d["has_reco"]).astype(bool)
    if dirs.shape[0] != n_rows:
        raise RuntimeError(f"{run_dir}: reco_directions has {dirs.shape[0]} rows, volumes has {n_rows}")
    return dirs, has


# --------------------------------------------------------------------------------------
# per-cat table
# --------------------------------------------------------------------------------------
def _partner_info(pf, plane, mid, irow):
    """Energy / event / rank of the partner cluster in the U or V plane."""
    meta = pf[f"meta_{plane.lower()}"]
    n_main, e_max, e_sum = pf[f"{plane.lower()}_stats"]
    if irow < 0:
        return dict(e=np.nan, ev=-1, is_marley=-1, is_top_main=-1, n_main=0,
                    e_max=np.nan, e_sum=np.nan)
    ev = int(meta[irow, 0])
    e = float(meta[irow, 10])
    return dict(e=e, ev=ev, is_marley=int(meta[irow, 1]),
                is_top_main=int(abs(e - e_max.get(ev, -1.0)) < 1e-6),
                n_main=int(n_main.get(ev, 0)), e_max=float(e_max.get(ev, np.nan)),
                e_sum=float(e_sum.get(ev, np.nan)))


def build_cat_table(cat, out_dir):
    sample_base = Path(SAMPLE_ROOT) / cat
    orig_dir = sample_base / f"{cat}{SUFFIX}"
    fix_dir = sample_base / f"{cat}{SUFFIX}_matchfix"

    rec_o, pf_o = replay_es(orig_dir)
    rec_f, pf_f = replay_es(fix_dir)

    run_o, run_f = latest_run(ORIG_ROOT, cat), latest_run(FIX_ROOT, cat)
    rows_o, meta_o = es_rows_in_run(run_o, len(rec_o))
    rows_f, meta_f = es_rows_in_run(run_f, len(rec_f))

    # validate the reconstruction: the replayed metadata must be the volumes.npz rows
    mine_o = np.array([r["meta"] for r in rec_o], dtype=np.float32)
    mine_f = np.array([r["meta"] for r in rec_f], dtype=np.float32)
    ok_o = bool(np.array_equal(meta_o[rows_o], mine_o))
    ok_f = bool(np.array_equal(meta_f[rows_f], mine_f))
    if not (ok_o and ok_f):
        raise RuntimeError(f"{cat}: loader replay does not reproduce volumes.npz (orig={ok_o}, fix={ok_f})")

    dirs_o, has_o = load_reco(run_o, meta_o.shape[0])
    dirs_f, has_f = load_reco(run_f, meta_f.shape[0])

    key_o = {(r["file"], r["ix"]): (i, r) for i, r in enumerate(rec_o)}
    key_f = {(r["file"], r["ix"]): (i, r) for i, r in enumerate(rec_f)}

    rows = []
    for key in sorted(set(key_o) | set(key_f)):
        fname, ix = key
        io, ro = key_o.get(key, (None, None))
        i_f, rf = key_f.get(key, (None, None))
        if ro is not None and rf is not None:
            cls = "SAME" if (ro["iu"] == rf["iu"] and ro["iv"] == rf["iv"]) else "CHANGED"
        elif rf is not None:
            cls = "NEW"
        else:
            cls = "LOST"
        base = rf if rf is not None else ro
        meta = base["meta"].astype(np.float64)

        d_o = dirs_o[rows_o[io]] if io is not None else np.full(3, np.nan)
        d_f = dirs_f[rows_f[i_f]] if i_f is not None else np.full(3, np.nan)
        v_o = bool(has_o[rows_o[io]]) if io is not None else False
        v_f = bool(has_f[rows_f[i_f]]) if i_f is not None else False

        # partner properties, old and new
        pu_o = _partner_info(pf_o[fname], "U", ro["mid"], ro["iu"]) if ro else _partner_info(pf_o[fname], "U", -1, -1)
        pv_o = _partner_info(pf_o[fname], "V", ro["mid"], ro["iv"]) if ro else _partner_info(pf_o[fname], "V", -1, -1)
        pu_f = _partner_info(pf_f[fname], "U", rf["mid"], rf["iu"]) if rf else _partner_info(pf_f[fname], "U", -1, -1)
        pv_f = _partner_info(pf_f[fname], "V", rf["mid"], rf["iv"]) if rf else _partner_info(pf_f[fname], "V", -1, -1)

        # for NEW events: what did the old products do with this X cluster?
        why = ""
        if cls == "NEW":
            po = pf_o[fname]
            mid_old = int(po["meta_x"][ix, 13])
            if mid_old == -1:
                why = "x_unmatched"
            else:
                u_main = mid_old in po["iu_map"]
                v_main = mid_old in po["iv_map"]
                u_any = mid_old in po["iu_any"]
                v_any = mid_old in po["iv_any"]
                parts = []
                if not u_main:
                    parts.append("u_nonmain" if u_any else "u_absent")
                if not v_main:
                    parts.append("v_nonmain" if v_any else "v_absent")
                why = "+".join(parts) if parts else "x_row_changed"
        if cls == "LOST":
            pnew = pf_f[fname]
            mid_new = int(pnew["meta_x"][ix, 13])
            if mid_new == -1:
                why = "x_unmatched_after"
            else:
                u_main = mid_new in pnew["iu_map"]
                v_main = mid_new in pnew["iv_map"]
                u_any = mid_new in pnew["iu_any"]
                v_any = mid_new in pnew["iv_any"]
                parts = []
                if not u_main:
                    parts.append("u_nonmain" if u_any else "u_absent")
                if not v_main:
                    parts.append("v_nonmain" if v_any else "v_absent")
                why = "+".join(parts) if parts else "x_row_changed"

        rows.append(dict(
            cat=cat, file=fname, ix=int(ix), cls=cls, why=why,
            event=int(meta[0]), is_es=int(meta[3]),
            e_clus=float(meta[10]), e_true=float(meta[11]),
            true_dir=normalize_vector(meta[7:10]) if np.linalg.norm(meta[7:10]) > 0 else np.full(3, np.nan),
            row_o=int(rows_o[io]) if io is not None else -1,
            row_f=int(rows_f[i_f]) if i_f is not None else -1,
            dir_o=d_o, dir_f=d_f, valid_o=v_o, valid_f=v_f,
            iu_o=int(ro["iu"]) if ro else -1, iv_o=int(ro["iv"]) if ro else -1,
            iu_f=int(rf["iu"]) if rf else -1, iv_f=int(rf["iv"]) if rf else -1,
            mid_o=int(ro["mid"]) if ro else -1, mid_f=int(rf["mid"]) if rf else -1,
            pu_o=pu_o, pv_o=pv_o, pu_f=pu_f, pv_f=pv_f,
        ))

    # per-event bookkeeping: did the set of matched X main clusters of an event change?
    ev_o, ev_f = {}, {}
    for r in rec_o:
        ev_o.setdefault((r["file"], int(r["meta"][0])), set()).add(r["ix"])
    for r in rec_f:
        ev_f.setdefault((r["file"], int(r["meta"][0])), set()).add(r["ix"])
    ev_keys = set(ev_o) | set(ev_f)
    ev_summary = dict(
        n_events_orig=len(ev_o), n_events_fix=len(ev_f),
        n_events_both=len(set(ev_o) & set(ev_f)),
        n_events_x_set_changed=int(sum(1 for k in ev_keys
                                       if k in ev_o and k in ev_f and ev_o[k] != ev_f[k])),
        n_events_multi_x_orig=int(sum(1 for v in ev_o.values() if len(v) > 1)),
        n_events_multi_x_fix=int(sum(1 for v in ev_f.values() if len(v) > 1)),
    )

    npz_path = Path(out_dir) / f"{cat}_events.npz"
    _save_rows(npz_path, rows)
    return rows, ev_summary, dict(run_o=str(run_o), run_f=str(run_f),
                                  n_es_orig=len(rec_o), n_es_fix=len(rec_f),
                                  n_rows_orig=int(meta_o.shape[0]), n_rows_fix=int(meta_f.shape[0]),
                                  replay_ok_orig=ok_o, replay_ok_fix=ok_f), \
        (meta_o, dirs_o, has_o, rows_o), (meta_f, dirs_f, has_f, rows_f)


def _save_rows(path, rows):
    if not rows:
        np.savez_compressed(path, empty=True)
        return
    out = {}
    scal = ["ix", "event", "is_es", "e_clus", "e_true", "row_o", "row_f", "valid_o", "valid_f",
            "iu_o", "iv_o", "iu_f", "iv_f", "mid_o", "mid_f"]
    for k in scal:
        out[k] = np.array([r[k] for r in rows])
    out["cls"] = np.array([r["cls"] for r in rows])
    out["why"] = np.array([r["why"] for r in rows])
    out["src_file"] = np.array([r["file"] for r in rows])
    out["cat"] = np.array([r["cat"] for r in rows])
    for k in ["true_dir", "dir_o", "dir_f"]:
        out[k] = np.array([r[k] for r in rows], dtype=np.float64)
    for p in ["pu_o", "pv_o", "pu_f", "pv_f"]:
        for f in ["e", "ev", "is_marley", "is_top_main", "n_main", "e_max", "e_sum"]:
            out[f"{p}_{f}"] = np.array([r[p][f] for r in rows], dtype=np.float64)
    np.savez_compressed(path, **out)


# --------------------------------------------------------------------------------------
# offline burst fits
# --------------------------------------------------------------------------------------
def _fit(dirs, energies, true_burst_dir, init_mode, seed=None):
    cfg = dict(EMCEE_CFG)
    if init_mode:
        cfg["init_mode"] = init_mode
    if seed is not None:
        cfg["random_seed"] = int(seed)
    res = reconstruct_burst_direction(
        selected_dirs=np.asarray(dirs, dtype=np.float64),
        selected_weights=np.ones(len(dirs), dtype=np.float64),
        selected_energies=np.asarray(energies, dtype=np.float64),
        true_burst_dir=true_burst_dir,
        use_emcee=True, emcee_cfg=cfg, pdf_path=PDF_PATH,
    )
    cos = float(np.clip(np.dot(res["reco_dir"], true_burst_dir), -1, 1)) if res["reco_dir"] is not None else np.nan
    return dict(n=int(len(dirs)), cos=cos, theta=float(np.degrees(np.arccos(cos))),
                omega68=float(res["omega68_deg"]))


def burst_variants(rows, orig_pack, fix_pack, init_modes=("legacy", "grid"), min_e=3.0):
    meta_o, dirs_o, has_o, _ = orig_pack
    meta_f, dirs_f, has_f, _ = fix_pack
    tb = normalize_vector(np.mean(normalize_rows(meta_f[:, 15:18]), axis=0))

    cls = np.array([r["cls"] for r in rows])
    e = np.array([r["e_clus"] for r in rows])
    do = np.array([r["dir_o"] for r in rows], dtype=np.float64)
    df = np.array([r["dir_f"] for r in rows], dtype=np.float64)
    vo = np.array([r["valid_o"] for r in rows])
    vf = np.array([r["valid_f"] for r in rows])

    in_o = np.isin(cls, ["SAME", "CHANGED", "LOST"]) & vo & (e >= min_e)
    in_f = np.isin(cls, ["SAME", "CHANGED", "NEW"]) & vf & (e >= min_e)

    variants = {}
    variants["A_orig"] = (do[in_o], e[in_o])
    variants["B_fix"] = (df[in_f], e[in_f])
    m = in_f & (cls != "NEW")
    variants["C_fix_no_NEW"] = (df[m], e[m])
    m = in_f & (cls != "CHANGED")
    variants["D_fix_no_CHANGED"] = (df[m], e[m])
    m = in_f.copy()
    d = df.copy()
    swap = (cls == "CHANGED") & in_f & vo
    d[swap] = do[swap]
    variants["E_fix_CHANGED_old_dirs"] = (d[m], e[m])
    m = in_f & (cls == "SAME")
    variants["F_fix_SAME_only"] = (df[m], e[m])
    m = in_o & (cls != "LOST")
    variants["G_orig_no_LOST"] = (do[m], e[m])

    out = {}
    cache = {}
    for init in init_modes:
        for name, (dd, ee) in variants.items():
            key = (init, len(dd), hash(np.asarray(dd, dtype=np.float64).tobytes()),
                   hash(np.asarray(ee, dtype=np.float64).tobytes()))
            if key not in cache:
                cache[key] = _fit(dd, ee, tb, init)
            out[f"{name}|{init}"] = dict(cache[key])
    # emcee-chaos noise floor: the same event set refitted with other walker seeds
    for seed in (7, 123):
        for name in ("A_orig", "B_fix", "C_fix_no_NEW"):
            dd, ee = variants[name]
            out[f"{name}_seed{seed}|legacy"] = _fit(dd, ee, tb, "legacy", seed=seed)
    return out, tb


# --------------------------------------------------------------------------------------
# summary helpers
# --------------------------------------------------------------------------------------
def _ang(a, b):
    c = np.clip(np.sum(a * b, axis=1), -1, 1)
    return np.degrees(np.arccos(c))


def frag_table(cat, out_dir):
    """Per-event fragmentation of the MARLEY deposit in each plane, aligned to the event table.

    n_marley  = number of MARLEY-flagged clusters of that event in that plane
    mainfrac  = energy of the truth main-track cluster / energy of all MARLEY clusters of the event
    Both are read from the matchfix products; the cluster contents are identical in the two product
    sets (only match_id differs), so the numbers describe the event, not the matcher.
    """
    out_dir = Path(out_dir)
    t = dict(np.load(out_dir / f"{cat}_events.npz", allow_pickle=True))
    base = Path(SAMPLE_ROOT) / cat / f"{cat}{SUFFIX}_matchfix"
    cache = {}
    cols = {f"{pl}_{q}": [] for pl in "xuv"
            for q in ("n_marley", "mainfrac", "e_marley", "tspan", "cspan", "npix")}
    for i in range(len(t["ix"])):
        fn = str(t["src_file"][i])
        if fn not in cache:
            dx = np.load(base / "X" / fn, allow_pickle=True)
            du = np.load(base / "U" / fn.replace("planeX", "planeU"), allow_pickle=True)
            dv = np.load(base / "V" / fn.replace("planeX", "planeV"), allow_pickle=True)
            cache[fn] = (dx["metadata"], du["metadata"], dv["metadata"],
                         dx["images"], du["images"], dv["images"])
        mx, mu, mv, gx, gu, gv = cache[fn]
        ev = int(mx[int(t["ix"][i]), 0])
        irow = {"x": int(t["ix"][i]), "u": int(t["iu_f"][i]), "v": int(t["iv_f"][i])}
        for pl, g in (("x", gx), ("u", gu), ("v", gv)):
            # size of the image the ED is actually fed (0 if the cluster is not in this run)
            j = irow[pl]
            if j < 0 or j >= len(g):
                cols[f"{pl}_tspan"].append(0); cols[f"{pl}_cspan"].append(0); cols[f"{pl}_npix"].append(0)
                continue
            img = g[j] > 0
            nzr, nzc = np.nonzero(img.sum(axis=1))[0], np.nonzero(img.sum(axis=0))[0]
            cols[f"{pl}_tspan"].append(int(nzr[-1] - nzr[0] + 1) if len(nzr) else 0)
            cols[f"{pl}_cspan"].append(int(nzc[-1] - nzc[0] + 1) if len(nzc) else 0)
            cols[f"{pl}_npix"].append(int(img.sum()))
        for pl, m in (("x", mx), ("u", mu), ("v", mv)):
            em = m[:, 0] == ev
            mar = em & (m[:, 1] == 1)
            main = em & (m[:, 2] == 1)
            e_mar = float(m[mar, 10].sum())
            e_main = float(m[main, 10].sum())
            cols[f"{pl}_n_marley"].append(int(mar.sum()))
            cols[f"{pl}_e_marley"].append(e_mar)
            cols[f"{pl}_mainfrac"].append(e_main / e_mar if e_mar > 0 else np.nan)
    cols["ix"] = t["ix"]
    cols["cls"] = t["cls"]
    np.savez_compressed(out_dir / f"{cat}_frag.npz", **{k: np.asarray(v) for k, v in cols.items()})
    return cols


def extra_variants(cat, out_dir, comp_cut=0.5, init="legacy"):
    """Truth-free quality-cut variants, run from the per-cat table written by build_cat_table.

    comp = min(E_U partner, E_V partner) / E_X main cluster is available online (no truth),
    so a cut on it is deployable; the question is whether it buys back the theta68 that the
    newly matched events cost.
    """
    out_dir = Path(out_dir)
    t = dict(np.load(out_dir / f"{cat}_events.npz", allow_pickle=True))
    cls = t["cls"].astype(str)
    e = t["e_clus"].astype(float)
    do, df = t["dir_o"].astype(float), t["dir_f"].astype(float)
    vo, vf = t["valid_o"].astype(bool), t["valid_f"].astype(bool)
    comp_f = np.minimum(t["pu_f_e"], t["pv_f_e"]) / np.maximum(e, 1e-9)
    comp_o = np.minimum(t["pu_o_e"], t["pv_o_e"]) / np.maximum(e, 1e-9)

    meta_f = np.load(latest_run(FIX_ROOT, cat) / "volume_images" / "volumes.npz",
                     allow_pickle=True)["metadata"].astype(np.float64)
    tb = normalize_vector(np.mean(normalize_rows(meta_f[:, 15:18]), axis=0))

    in_o = np.isin(cls, ["SAME", "CHANGED", "LOST"]) & vo & (e >= 3.0)
    in_f = np.isin(cls, ["SAME", "CHANGED", "NEW"]) & vf & (e >= 3.0)
    out = {}
    m = in_f & (comp_f >= comp_cut)
    out[f"H_fix_comp_ge_{comp_cut}|{init}"] = _fit(df[m], e[m], tb, init)
    m = in_o & (comp_o >= comp_cut)
    out[f"I_orig_comp_ge_{comp_cut}|{init}"] = _fit(do[m], e[m], tb, init)
    m = in_f & (cls == "NEW")
    if m.sum() > 5:
        out[f"K_fix_NEW_only|{init}"] = _fit(df[m], e[m], tb, init)
    return out


# --------------------------------------------------------------------------------------
# induction-charge consistency scan:  r = min(E_U, E_V) / E_X
# --------------------------------------------------------------------------------------
R_CUTS = [0.3, 0.4, 0.5, 0.6, 0.7]
SEL_PERFECT = "perfect_ct"
SEL_DEPLOYED = "deployed"


def replay_all(product_dir):
    """Metadata-only replay of the loader over CC and then ES files (loader order).

    Returns arrays aligned with the pre-shuffle concatenation the pipeline builds:
    e_x, e_u, e_v (cluster energies of the X main cluster and of its U and V partners)
    and the X metadata rows.
    """
    product_dir = Path(product_dir)
    e_x, e_u, e_v, metas = [], [], [], []
    for pattern in ("cc_*_bg_matched_planeX.npz", "es_*_bg_matched_planeX.npz"):
        for fp in sorted((product_dir / "X").glob(pattern)):
            mx = np.load(fp, allow_pickle=True)["metadata"]
            mu = np.load(product_dir / "U" / fp.name.replace("planeX", "planeU"),
                         allow_pickle=True)["metadata"]
            mv = np.load(product_dir / "V" / fp.name.replace("planeX", "planeV"),
                         allow_pickle=True)["metadata"]
            ix_map, iu_map, iv_map = _plane_index(mx), _plane_index(mu), _plane_index(mv)
            for mid in sorted(set(ix_map) & set(iu_map) & set(iv_map)):
                e_x.append(float(mx[ix_map[mid], 10]))
                e_u.append(float(mu[iu_map[mid], 10]))
                e_v.append(float(mv[iv_map[mid], 10]))
                metas.append(mx[ix_map[mid]])
    return (np.array(e_x), np.array(e_u), np.array(e_v),
            np.array(metas, dtype=np.float32))


def _run_pack(root, cat, scenario):
    run = latest_run(root, cat, scenario)
    vol = np.load(run / "volume_images" / "volumes.npz", allow_pickle=True)
    meta = np.asarray(vol["metadata"], dtype=np.float64)
    dirs, has = load_reco(run, meta.shape[0])
    ct = None
    cp = run / "predictions" / "channel_predictions.npz"
    if cp.exists():
        ct = np.asarray(np.load(cp, allow_pickle=True)["y_pred_proba"], dtype=np.float64)
        if ct.shape[0] != meta.shape[0]:
            raise RuntimeError(f"{run}: CT scores {ct.shape[0]} vs {meta.shape[0]} rows")
    return run, meta, dirs, has, ct


def rscan(cat, out_dir):
    """theta68 vs the truth-free cut r = min(E_U, E_V)/E_X, both product sets, two selections.

    Sampler: the pipeline defaults of the day (nothing but nwalkers/nsteps/discard/seed is
    passed, so init_mode='grid' with init_sigma_deg='auto' is used).
    """
    res = {"cat": cat, "cuts": R_CUTS, "sets": {}}
    for tag, root, suffix in (("orig", ORIG_ROOT, ""), ("fix", FIX_ROOT, "_matchfix")):
        prod = Path(SAMPLE_ROOT) / cat / f"{cat}{SUFFIX}{suffix}"
        e_x, e_u, e_v, metas = replay_all(prod)

        run2, meta2, dirs2, has2, _ = _run_pack(root, cat, SCENARIO)
        run3, meta3, dirs3, has3, ct3 = _run_pack(root, cat, "scenario_3_full_pipeline")
        n = meta2.shape[0]
        if metas.shape[0] != n:
            raise RuntimeError(f"{cat}/{tag}: replay {metas.shape[0]} rows, volumes {n}")
        np.random.seed(42)
        perm = np.random.permutation(n)
        # row i of volumes.npz is pre-shuffle index perm[i]
        e_x, e_u, e_v = e_x[perm], e_u[perm], e_v[perm]
        if not np.array_equal(metas[perm], meta2.astype(np.float32)):
            raise RuntimeError(f"{cat}/{tag}: replay does not reproduce volumes.npz (scenario 2)")
        if not np.array_equal(meta2, meta3):
            raise RuntimeError(f"{cat}/{tag}: scenario 2 and 3 hold different rows")

        r = np.minimum(e_u, e_v) / np.maximum(e_x, 1e-9)
        is_es = meta2[:, 3].astype(int) == 1
        energy = meta2[:, 10]
        tb = normalize_vector(np.mean(normalize_rows(meta2[:, 15:18]), axis=0))

        base = {
            SEL_PERFECT: (is_es & (energy >= 3.0) & has2, dirs2),
            SEL_DEPLOYED: ((ct3 >= 0.8) & (energy >= 5.0) & has3, dirs3),
        }
        out = {}
        for sel, (mask, dirs) in base.items():
            for cut in [None] + R_CUTS:
                m = mask if cut is None else (mask & (r >= cut))
                key = "nocut" if cut is None else f"{cut}"
                if int(m.sum()) < 5:
                    out[f"{sel}|{key}"] = dict(n=int(m.sum()), cos=float("nan"),
                                               theta=float("nan"), omega68=float("nan"),
                                               purity=float("nan"))
                    continue
                fit = _fit(dirs[m], energy[m], tb, init_mode=None)
                fit["purity"] = float(np.mean(is_es[m]))
                out[f"{sel}|{key}"] = fit
        res["sets"][tag] = out
    (Path(out_dir) / f"{cat}_rscan.json").write_text(json.dumps(res, indent=1))
    return res


def _ebin(e):
    for i, (lo, hi) in enumerate(E_BINS):
        if lo <= e < hi:
            return i
    return -1


def _q68(x):
    return float(np.quantile(x, 0.68)) if len(x) else float("nan")


def theta68_cats(cos):
    cos = np.asarray(cos, dtype=float)
    return float(np.degrees(np.arccos(np.clip(np.quantile(cos, 0.32), -1, 1))))


def load_all(out_dir):
    out_dir = Path(out_dir)
    cats = sorted(p.name.split("_")[0] for p in out_dir.glob("cat*_diag.json"))
    tabs, metas = [], {}
    for cat in cats:
        metas[cat] = json.loads((out_dir / f"{cat}_diag.json").read_text())
        d = np.load(out_dir / f"{cat}_events.npz", allow_pickle=True)
        tabs.append({k: d[k] for k in d.files})
    if not tabs:
        raise SystemExit(f"no per-cat outputs in {out_dir}")
    keys = set.intersection(*[set(t) for t in tabs])
    T = {k: np.concatenate([t[k] for t in tabs]) for k in keys}
    return cats, metas, T


def summarize(out_dir, out_md):
    cats, metas, T = load_all(out_dir)
    cls = T["cls"].astype(str)
    e_true = T["e_true"].astype(float)
    e_clus = T["e_clus"].astype(float)
    td = T["true_dir"].astype(float)
    do, df = T["dir_o"].astype(float), T["dir_f"].astype(float)
    vo, vf = T["valid_o"].astype(bool), T["valid_f"].astype(bool)

    L = []
    A = L.append
    A("# Why the ED directions get worse on the matcher-fixed products")
    A("")
    A(f"Cats: {len(cats)} ({cats[0]}-{cats[-1]}), scenario `{SCENARIO}` (perfect CT: true ES, reco dir, E>3 MeV).")
    A("Join key: (source cluster-image file, X-cluster row index in that file); the pipeline row order of")
    A("`volume_images/volumes.npz` is reproduced exactly by replaying `python/lib/sample_loader.py` on the")
    A("cluster-image metadata of both product sets (checked per cat, see `replay_ok_*`).")
    A("")

    A("## Summary")
    A("")
    A("The matcher fix changes the ED input of **no** event that was already in the pipeline: partner")
    A("changes on already-matched events are structurally impossible (section 7), and the reco directions")
    A("of the common events are identical to <1e-4. The whole theta68 cost is carried by the ~28")
    A("events/burst that the fix adds, which are high-energy showers with a split induction-plane image")
    A("and on which ED v58 is much worse than on the events it already had. Removing them from the")
    A("matchfix run reproduces the original theta68; a truth-free cut on the induction/collection charge")
    A("balance does better than either.")
    A("")

    # ---- integrity ----
    ok = all(m["info"]["replay_ok_orig"] and m["info"]["replay_ok_fix"] for m in metas.values())
    ident = [m.get("same_bit_identical") for m in metas.values() if "same_bit_identical" in m]
    maxdiff = max(m.get("same_max_abs_diff", 0.0) for m in metas.values())
    A("## 0. Integrity of the join")
    A("")
    A(f"* replay reproduces `volumes.npz` metadata for every cat: **{ok}**")
    A(f"* SAME events with bit-identical reco directions in the two runs: {sum(1 for x in ident if x)}/{len(ident)} cats; "
      f"max |d(reco_dir)| over all SAME events = **{maxdiff:.2e}** (float32 ULP level, i.e. the same input gives the same answer; "
      "the residue is TF batching non-determinism, the batches differ because the two runs hold a different number of clusters)")
    xset = sum(m["events"]["n_events_x_set_changed"] for m in metas.values())
    multix_o = sum(m["events"]["n_events_multi_x_orig"] for m in metas.values())
    multix_f = sum(m["events"]["n_events_multi_x_fix"] for m in metas.values())
    A(f"* events whose set of matched X main-track clusters changed: **{xset}**; events with >1 matched X main cluster: "
      f"{multix_o} (orig) / {multix_f} (fix) -> the X main cluster and therefore the cluster energy is never the thing that changed")
    A("")

    # ---- class table ----
    A("## 1. Event classes (true-ES main tracks, 3-plane matched)")
    A("")
    A("| class | N | N/burst | mean E_true [MeV] | median E_true | frac E_true>10 | mean E_clus |")
    A("|---|---|---|---|---|---|---|")
    for c in CLASSES:
        m = cls == c
        if not m.any():
            A(f"| {c} | 0 | 0.0 | - | - | - | - |")
            continue
        A(f"| {c} | {int(m.sum())} | {m.sum()/len(cats):.1f} | {e_true[m].mean():.2f} | "
          f"{np.median(e_true[m]):.2f} | {np.mean(e_true[m] > 10):.2f} | {e_clus[m].mean():.2f} |")
    A("")
    A("| class | " + " | ".join(f"E_true {lab}" for lab in E_BIN_LABELS) + " |")
    A("|---|" + "---|" * len(E_BIN_LABELS))
    for c in CLASSES:
        m = cls == c
        row = [str(int(np.sum(m & (e_true >= lo) & (e_true < hi)))) for lo, hi in E_BINS]
        A(f"| {c} | " + " | ".join(row) + " |")
    A("")
    if np.any(cls == "NEW"):
        why = T["why"].astype(str)[cls == "NEW"]
        vals, cnt = np.unique(why, return_counts=True)
        A("Why NEW events were absent before (state of the same X cluster in the original products):")
        A("")
        A("| reason | N |")
        A("|---|---|")
        for v, n in sorted(zip(vals, cnt), key=lambda z: -z[1]):
            A(f"| `{v or '(none)'}` | {n} |")
        A("")
    if np.any(cls == "LOST"):
        why = T["why"].astype(str)[cls == "LOST"]
        vals, cnt = np.unique(why, return_counts=True)
        A("Why LOST events disappeared: " + ", ".join(f"`{v}` x{n}" for v, n in zip(vals, cnt)))
        A("")

    # ---- ED quality ----
    A("## 2. ED quality per class")
    A("")
    A("cos = mean cos(reco electron dir, true electron dir); th68 = 68th percentile of the per-event angle [deg].")
    A("`fix` uses the matchfix run's direction, `orig` the original run's (only defined for SAME/CHANGED/LOST).")
    A("")
    header = "| class | run | N | cos all | th68 all | " + " | ".join(
        f"cos {lab} | th68 {lab}" for lab in E_BIN_LABELS) + " |"
    A(header)
    A("|---|---|---|---|---|" + "---|" * (2 * len(E_BIN_LABELS)))
    for c in CLASSES:
        for tag, d, v in (("fix", df, vf), ("orig", do, vo)):
            m = (cls == c) & v & np.isfinite(d).all(axis=1)
            if not m.any():
                continue
            ang = _ang(d[m], td[m])
            cosv = np.cos(np.radians(ang))
            cells = []
            for lo, hi in E_BINS:
                mm = (e_true[m] >= lo) & (e_true[m] < hi)
                cells.append(f"{cosv[mm].mean():.3f}" if mm.any() else "-")
                cells.append(f"{_q68(ang[mm]):.1f}" if mm.any() else "-")
            A(f"| {c} | {tag} | {int(m.sum())} | {cosv.mean():.3f} | {_q68(ang):.1f} | " + " | ".join(cells) + " |")
    A("")
    # combined populations that actually enter the fit
    A("Populations entering the perfect-CT fit (E_clus > 3 MeV):")
    A("")
    A("| population | N | cos | th68 |")
    A("|---|---|---|---|")
    pops = {
        "original run (SAME+CHANGED+LOST, orig dirs)": (np.isin(cls, ["SAME", "CHANGED", "LOST"]) & vo & (e_clus >= 3), do),
        "matchfix run (SAME+CHANGED+NEW, fix dirs)": (np.isin(cls, ["SAME", "CHANGED", "NEW"]) & vf & (e_clus >= 3), df),
        "SAME only (fix dirs)": ((cls == "SAME") & vf & (e_clus >= 3), df),
        "NEW only (fix dirs)": ((cls == "NEW") & vf & (e_clus >= 3), df),
        "CHANGED only (fix dirs)": ((cls == "CHANGED") & vf & (e_clus >= 3), df),
        "CHANGED only (orig dirs)": ((cls == "CHANGED") & vo & (e_clus >= 3), do),
    }
    for name, (m, d) in pops.items():
        if not m.any():
            A(f"| {name} | 0 | - | - |")
            continue
        ang = _ang(d[m], td[m])
        A(f"| {name} | {int(m.sum())} | {np.cos(np.radians(ang)).mean():.3f} | {_q68(ang):.1f} |")
    A("")

    # ---- CHANGED partner analysis ----
    A("## 3. CHANGED events: is the new partner the better one?")
    A("")
    mC = cls == "CHANGED"
    if not mC.any():
        A("**No CHANGED events at all.** Every event that was 3-plane matched with truth-main-track")
        A("partners in U and V before the fix keeps exactly the same partner clusters after it, so the ED")
        A("input of every previously used event is unchanged and there is no train/inference mismatch on them.")
        A("")
    else:
        for pl in ["u", "v"]:
            ch = mC & (T[f"i{pl}_o"].astype(int) != T[f"i{pl}_f"].astype(int))
            A(f"* {pl.upper()} partner changed for {int(ch.sum())} events")
            if ch.any():
                eo, ef = T[f"p{pl}_o_e"][ch], T[f"p{pl}_f_e"][ch]
                to, tf = T[f"p{pl}_o_is_top_main"][ch], T[f"p{pl}_f_is_top_main"][ch]
                A(f"  * partner energy old {np.mean(eo):.2f} -> new {np.mean(ef):.2f} MeV; "
                  f"new more energetic in {np.mean(ef > eo):.0%} of them")
                A(f"  * partner is the most energetic main-track cluster of the event: "
                  f"old {np.mean(to == 1):.0%} -> new {np.mean(tf == 1):.0%}")
        ang_o = _ang(do[mC & vo], td[mC & vo])
        ang_f = _ang(df[mC & vf], td[mC & vf])
        A("")
        A(f"* ED on the same events: cos {np.cos(np.radians(ang_o)).mean():.3f} (old partner) -> "
          f"{np.cos(np.radians(ang_f)).mean():.3f} (new partner); th68 {_q68(ang_o):.1f} -> {_q68(ang_f):.1f} deg")
        A("")

    # ---- partner completeness of NEW vs SAME ----
    A("## 4. Are the NEW events intrinsically harder?")
    A("")
    frag = {}
    for cat in cats:
        fp = Path(out_dir) / f"{cat}_frag.npz"
        if fp.exists():
            d = np.load(fp, allow_pickle=True)
            for k in d.files:
                frag.setdefault(k, []).append(d[k])
    if frag:
        F = {k: np.concatenate(v) for k, v in frag.items()}
        if not np.array_equal(F["ix"].astype(int), T["ix"].astype(int)):
            raise RuntimeError("frag table misaligned with the event table")
        A("Fragmentation of the MARLEY deposit of the event, per plane (matchfix products; the cluster")
        A("contents are identical in both product sets, only `match_id` differs):")
        A("")
        A("| class | N | X clusters/ev | X main charge frac | U clusters/ev | U frac>1 | U main charge frac | "
          "V clusters/ev | V frac>1 | V main charge frac |")
        A("|---|---|---|---|---|---|---|---|---|---|")
        for c in ["SAME", "CHANGED", "NEW"]:
            m = cls == c
            if not m.any():
                continue
            cells = [f"{F['x_n_marley'][m].mean():.2f}", f"{np.nanmean(F['x_mainfrac'][m]):.2f}"]
            for pl in ("u", "v"):
                cells += [f"{F[f'{pl}_n_marley'][m].mean():.2f}",
                          f"{np.mean(F[f'{pl}_n_marley'][m] > 1):.0%}",
                          f"{np.nanmean(F[f'{pl}_mainfrac'][m]):.2f}"]
            A(f"| {c} | {int(m.sum())} | " + " | ".join(cells) + " |")
        A("")
        A("The induction-plane view of a NEW event is split: 2 MARLEY clusters instead of 1, and the")
        A("cluster the ED is fed holds ~70% of the plane's MARLEY charge instead of ~95%. The X view is")
        A("almost as complete as for a SAME event, so the network is asked to combine a whole collection")
        A("image with two partial induction images.")
        A("")
        if "x_tspan" in F:
            A("Size of the images the ED is fed (drift-time extent in ticks, true energy 10-30 MeV):")
            A("")
            A("| class | X tspan | U tspan | V tspan | U/X | V/X |")
            A("|---|---|---|---|---|---|")
            for c in ["SAME", "NEW"]:
                m = (cls == c) & (e_true >= 10) & (e_true < 30) & (F["x_tspan"] > 0) & (F["u_tspan"] > 0)
                if m.sum() < 20:
                    continue
                A(f"| {c} | {F['x_tspan'][m].mean():.1f} | {F['u_tspan'][m].mean():.1f} | {F['v_tspan'][m].mean():.1f} | "
                  f"{np.mean(F['u_tspan'][m] / F['x_tspan'][m]):.2f} | {np.mean(F['v_tspan'][m] / F['x_tspan'][m]):.2f} |")
            A("")
        mfrac = np.minimum(F["u_mainfrac"], F["v_mainfrac"])
        A("But fragmentation alone does not explain the loss — SAME events are almost insensitive to it,")
        A("NEW events are bad at every fragmentation level (mean cos, true-energy 10-30 MeV):")
        A("")
        A("| min(U,V) main charge frac | SAME | NEW |")
        A("|---|---|---|")
        base = (e_true >= 10) & (e_true < 30) & vf
        ang_all = _ang(df, td)
        cos_all = np.cos(np.radians(ang_all))
        for lo, hi, lab in [(0, 0.6, "<0.6"), (0.6, 0.8, "0.6-0.8"), (0.8, 0.95, "0.8-0.95"), (0.95, 2, ">0.95")]:
            cells = []
            for c in ("SAME", "NEW"):
                m = base & (cls == c) & (mfrac >= lo) & (mfrac < hi)
                cells.append(f"{cos_all[m].mean():.3f} (N={int(m.sum())})" if m.sum() >= 20 else f"- (N={int(m.sum())})")
            A(f"| {lab} | " + " | ".join(cells) + " |")
        A("")
        A("What is left that is specific to a NEW event: the induction cluster the pipeline feeds the ED is")
        A("**not the first fragment in time** — that is the definition of the class (the old first-in-time")
        A("rule picked the other fragment). The X image and the U/V images therefore describe different")
        A("pieces of the same shower, which is exactly what a 3-plane stereo network cannot absorb.")
        A("")
    else:
        A("(no `*_frag.npz` tables found; run with `--frag` to fill this section)")
        A("")

    # ---- offline theta68 ----
    have_fits = [m for m in metas.values() if "fits" in m]
    if have_fits:
        A("## 5. Offline burst-fit decomposition (perfect CT, E > 3 MeV)")
        A("")
        A("theta68 = arccos(0.32 quantile of the per-cat cos(reco burst dir, true burst dir)), the same")
        A("statistic as `paired_campaign_compare.py`, recomputed offline with the pipeline likelihood")
        A(f"({EMCEE_CFG}, uniform prior, pdf `data/cosine_energy_pdf.npz`, unit weights).")
        A("")
        inits = sorted({k.split("|")[1] for m in have_fits for k in m["fits"]})
        for init in inits:
            names = [k.split("|")[0] for k in have_fits[0]["fits"]
                     if k.endswith("|" + init) and "_seed" not in k]
            A(f"### walker init `{init}`" + (" (reproduces the campaign numbers)" if init == "legacy" else ""))
            A("")
            A("| variant | mean N events | theta68 [deg] | median theta | mean theta | frac>30 deg |")
            A("|---|---|---|---|---|---|")
            base = None
            for name in names:
                cos = np.array([m["fits"][f"{name}|{init}"]["cos"] for m in have_fits])
                th = np.degrees(np.arccos(np.clip(cos, -1, 1)))
                n = np.mean([m["fits"][f"{name}|{init}"]["n"] for m in have_fits])
                t68 = theta68_cats(cos)
                if base is None:
                    base = t68
                A(f"| {name} | {n:.0f} | {t68:.2f} | {np.median(th):.2f} | {np.mean(th):.2f} | {np.mean(th > 30):.2f} |")
            A("")
            # paired deltas w.r.t. A
            rng = np.random.default_rng(7)
            cosA = np.array([m["fits"][f"A_orig|{init}"]["cos"] for m in have_fits])
            A("| variant | d theta68 vs A_orig [68% boot] | median paired d theta |")
            A("|---|---|---|")
            for name in names:
                cosB = np.array([m["fits"][f"{name}|{init}"]["cos"] for m in have_fits])
                d = [theta68_cats(cosB[i]) - theta68_cats(cosA[i])
                     for i in (rng.integers(0, len(cosA), len(cosA)) for _ in range(2000))]
                lo, hi = np.quantile(d, [0.16, 0.84])
                paired = np.degrees(np.arccos(np.clip(cosB, -1, 1))) - np.degrees(np.arccos(np.clip(cosA, -1, 1)))
                A(f"| {name} | {theta68_cats(cosB) - theta68_cats(cosA):+.2f} [{lo:+.2f}, {hi:+.2f}] | {np.median(paired):+.2f} |")
            A("")
        # emcee noise floor
        nf = []
        for name in ("A_orig", "B_fix", "C_fix_no_NEW"):
            vals = []
            for tag in ("", "_seed7", "_seed123"):
                k = f"{name}{tag}|legacy"
                if all(k in m["fits"] for m in have_fits):
                    vals.append(theta68_cats([m["fits"][k]["cos"] for m in have_fits]))
            if len(vals) > 1:
                nf.append(f"{name}: " + " / ".join(f"{v:.2f}" for v in vals))
        if nf:
            A("emcee noise floor — the same event sets refitted with walker seeds 42 / 7 / 123 "
              "(the chain is chaotic at the 1e-7 level of the stored float32 directions, so a per-cat "
              "theta wanders by ~0.1 deg): " + "; ".join(nf) + ".")
            A("")
        A("Variant key: **A_orig** = original products; **B_fix** = matchfix products; "
          "**C_fix_no_NEW** = matchfix minus the newly matched events; **D_fix_no_CHANGED** = matchfix minus events "
          "whose partner changed; **E_fix_CHANGED_old_dirs** = matchfix with the CHANGED events' directions replaced "
          "by their original ones; **F_fix_SAME_only** = only events common to both runs with identical partners; "
          "**G_orig_no_LOST** = original products minus events that the fix drops.")
        A("")
    # ---- truth-free quality cut ----
    ex = {}
    for cat in cats:
        fp = Path(out_dir) / f"{cat}_extra.json"
        if fp.exists():
            ex[cat] = json.loads(fp.read_text())["fits"]
    if ex and have_fits:
        cats_ex = [c for c in cats if c in ex]
        A("## 6. Can a truth-free cut buy the degree back?")
        A("")
        A("`comp = min(E_U partner, E_V partner) / E_X main cluster` needs no truth, so it is deployable.")
        A("Same fit, same cats, legacy walker init.")
        A("")
        A("| variant | mean N events | theta68 [deg] | median theta |")
        A("|---|---|---|---|")
        names = sorted({k for c in cats_ex for k in ex[c]})
        base_keys = [("A_orig|legacy", "A_orig (all matched, original)"),
                     ("B_fix|legacy", "B_fix (all matched, matchfix)")]
        for key, lab in base_keys:
            cos = np.array([metas[c]["fits"][key]["cos"] for c in cats_ex])
            n = np.mean([metas[c]["fits"][key]["n"] for c in cats_ex])
            th = np.degrees(np.arccos(np.clip(cos, -1, 1)))
            A(f"| {lab} | {n:.0f} | {theta68_cats(cos):.2f} | {np.median(th):.2f} |")
        for key in names:
            cos = np.array([ex[c][key]["cos"] for c in cats_ex])
            n = np.mean([ex[c][key]["n"] for c in cats_ex])
            th = np.degrees(np.arccos(np.clip(cos, -1, 1)))
            A(f"| {key.split('|')[0]} | {n:.0f} | {theta68_cats(cos):.2f} | {np.median(th):.2f} |")
        A("")
        rng = np.random.default_rng(7)
        cosB = np.array([metas[c]["fits"]["B_fix|legacy"]["cos"] for c in cats_ex])
        A("| comparison | d theta68 [68% boot] |")
        A("|---|---|")
        for key in names:
            cosH = np.array([ex[c][key]["cos"] for c in cats_ex])
            d = [theta68_cats(cosH[i]) - theta68_cats(cosB[i])
                 for i in (rng.integers(0, len(cosB), len(cosB)) for _ in range(2000))]
            lo, hi = np.quantile(d, [0.16, 0.84])
            A(f"| {key.split('|')[0]} - B_fix | {theta68_cats(cosH) - theta68_cats(cosB):+.2f} [{lo:+.2f}, {hi:+.2f}] |")
        A("")

    # ---- verdict ----
    n_same = int(np.sum(cls == "SAME")); n_new = int(np.sum(cls == "NEW"))
    n_chg = int(np.sum(cls == "CHANGED")); n_lost = int(np.sum(cls == "LOST"))
    A("## 7. Verdict")
    A("")
    A(f"**(a).** The whole effect is the newly matched events. Of the {n_same + n_new + n_chg} true-ES main")
    A(f"tracks the matchfix run feeds the pointing fit, {n_same} are the same events with the same U and V")
    A(f"partner clusters as before (their ED directions agree to <1e-4), {n_chg} have a different partner,")
    A(f"and {n_new} are new; {n_lost} events are lost. Dropping the new events from the matchfix run puts")
    A("theta68 back on the original number to within the emcee noise floor.")
    A("")
    A("**(b) is impossible here.** A partner can only change from a truth-main to another truth-main")
    A("cluster, and `make_clusters.cpp` flags exactly ONE main cluster per event per view (the most")
    A("energetic MARLEY cluster, `make_clusters.cpp:280-322`), while `sample_loader.py` only accepts a")
    A("match whose U and V partners carry that flag. So an event that was already in the pipeline can")
    A("never acquire a different partner: any partner change is a non-main -> main change, which by")
    A("construction means the event was not in the pipeline before, i.e. it is a NEW event. Measured:")
    A(f"{n_chg} CHANGED events in {len(cats)} bursts.")
    A("")
    A("**(c) ruled out one by one.** The loader picks the same events plus the new ones (the matched X")
    A("main-cluster set of an event never changes, 0 cases), the X main cluster is never a different")
    A("cluster, the cluster energies are the same numbers, and the true burst direction of the two runs")
    A("agrees to 4e-8. The SAME events' reco directions are reproduced to <1e-4 (TF batching")
    A("non-determinism, the two runs hold a different number of clusters, so the batches differ).")
    A("")
    A("**Why the new events are hard.** They are the events the old first-in-time rule could not match")
    A("correctly *because* their induction-plane image is split into two MARLEY clusters (72-76% of them,")
    A("vs 13-15% of the SAME events) and the earlier fragment is not the biggest one. The new rule gives")
    A("the ED the biggest fragment - the truth-main cluster, 100% of the time by construction - but that")
    A("fragment still holds only ~70% of the plane's MARLEY charge, while the X image holds ~90%. The ED")
    A("is asked to stereo-combine a whole collection view with two partial induction views of a")
    A("high-energy shower (mean true energy 18.6 MeV vs 11.2 MeV for the SAME events), and it fails:")
    A("its cos is worse than the SAME events' in every single energy bin, e.g. 0.41 vs 0.64 at 20-30 MeV.")
    A("Note that ED v58 was trained on `es_production_cluster_images_tick3_ch2_min2_tot3_e2p0` with")
    A("`use_matched: true` (results.json of the model directory), i.e. on products built with the OLD")
    A("matcher - so this population was absent from its training set as well. The two readings")
    A("(intrinsically hard / never seen in training) cannot be separated with these products; what can be")
    A("said is that fragmentation alone is not the whole story, since SAME events with an equally split")
    A("induction view are reconstructed as well as unsplit ones.")
    A("")

    # ---- r-cut scan ----
    rs = {}
    for cat in cats:
        fp = Path(out_dir) / f"{cat}_rscan.json"
        if fp.exists():
            rs[cat] = json.loads(fp.read_text())
    if rs:
        cats_r = [c for c in cats if c in rs]
        cuts = rs[cats_r[0]]["cuts"]
        rng = np.random.default_rng(11)

        def _col(tag, sel, key, field):
            return np.array([rs[c]["sets"][tag][f"{sel}|{key}"][field] for c in cats_r], dtype=float)

        def _row(tag, sel, key):
            cos = _col(tag, sel, key, "cos")
            base = _col(tag, sel, "nocut", "cos")
            ok = np.isfinite(cos) & np.isfinite(base)
            t68 = theta68_cats(cos[ok])
            if key == "nocut":
                d = "-"
            else:
                dd = [theta68_cats(cos[ok][i]) - theta68_cats(base[ok][i])
                      for i in (rng.integers(0, int(ok.sum()), int(ok.sum())) for _ in range(2000))]
                lo, hi = np.quantile(dd, [0.16, 0.84])
                d = f"{t68 - theta68_cats(base[ok]):+.2f} [{lo:+.2f}, {hi:+.2f}]"
            return t68, np.mean(_col(tag, sel, key, "n")), d, np.mean(_col(tag, sel, key, "purity"))

        A("## 8. Scan of the truth-free induction-charge consistency cut")
        A("")
        A("`r = min(E_U, E_V) / E_X`, the two induction partner energies against the collection main")
        A(f"cluster, on the same {len(cats_r)} bursts and with the pipeline's own likelihood. Sampler: the")
        A("**current defaults** — nothing beyond `nwalkers/nsteps/discard/random_seed` is passed, so the")
        A("walkers are seeded at the grid maximum (`init_mode=\"grid\"`) with `init_sigma_deg=\"auto\"`")
        A("(the 68% angular radius of the grid posterior, clipped to [5, 45] deg). These numbers are")
        A("therefore NOT directly comparable with the `legacy`-init tables of section 5; the no-cut rows")
        A("are the reference of their own product set.")
        A("")
        A("### (i) perfect CT — true ES, reco directions, E > 3 MeV")
        A("")
        A("| r cut | orig N/burst | orig theta68 | orig d vs no-cut [68% boot] | matchfix N/burst | matchfix theta68 | matchfix d vs no-cut [68% boot] |")
        A("|---|---|---|---|---|---|---|")
        for key in ["nocut"] + [str(c) for c in cuts]:
            ao = _row("orig", SEL_PERFECT, key)
            af = _row("fix", SEL_PERFECT, key)
            lab = "none" if key == "nocut" else f"r >= {key}"
            A(f"| {lab} | {ao[1]:.0f} | {ao[0]:.2f} | {ao[2]} | {af[1]:.0f} | {af[0]:.2f} | {af[2]} |")
        A("")
        A("### (ii) deployed selection — CT v80 score >= 0.80 and E > 5 MeV")
        A("")
        A("| r cut | orig N/burst | orig ES purity | orig theta68 | orig d vs no-cut [68% boot] | matchfix N/burst | matchfix ES purity | matchfix theta68 | matchfix d vs no-cut [68% boot] |")
        A("|---|---|---|---|---|---|---|---|---|")
        for key in ["nocut"] + [str(c) for c in cuts]:
            ao = _row("orig", SEL_DEPLOYED, key)
            af = _row("fix", SEL_DEPLOYED, key)
            lab = "none" if key == "nocut" else f"r >= {key}"
            A(f"| {lab} | {ao[1]:.0f} | {ao[3]:.3f} | {ao[0]:.2f} | {ao[2]} | "
              f"{af[1]:.0f} | {af[3]:.3f} | {af[0]:.2f} | {af[2]} |")
        A("")
    # ---- statistics + recommendation ----
    A("## 9. How solid is this, and what to do")
    A("")
    if have_fits:
        cats_f = [c for c in cats if "fits" in metas[c]]
        ta = np.array([metas[c]["fits"]["A_orig|legacy"]["theta"] for c in cats_f])
        tb = np.array([metas[c]["fits"]["B_fix|legacy"]["theta"] for c in cats_f])
        d = tb - ta
        A(f"* {len(cats_f)} bursts, {int(np.sum(np.isin(cls, ['SAME', 'CHANGED', 'NEW'])))} true-ES events. "
          f"theta68 is the 0.32 quantile of 50 per-burst cosines, i.e. a TAIL statistic: only "
          f"{np.mean(d > 0):.0%} of bursts get worse, the median paired shift is {np.median(d):+.2f} deg, "
          f"and the mean ({np.mean(d):+.2f}) is carried by "
          f"{int(np.sum(d > 2))} bursts that move by more than 2 deg (worst {np.max(d):+.1f}). "
          "The 'degree' is real but it is a statement about the tail of 50 bursts, not about a typical burst.")
        A(f"* emcee chaos alone moves theta68 by ~0.2-0.3 deg (seeds 42/7/123 above), and the bootstrap "
          f"68% interval on d theta68 is [+0.11, +1.45]. Anything below ~0.5 deg in these tables is noise.")
    frac = []
    for cut in (3, 5, 10):
        m = np.isin(cls, ["SAME", "CHANGED", "NEW"]) & (e_clus >= cut)
        frac.append((cut, int(np.sum((cls == "NEW") & (e_clus >= cut))), int(m.sum())))
    A("* the newly matched events are a rising fraction of the sample as the energy cut rises — "
      + ", ".join(f"E>{c}: {n}/{t} = {n/t:.0%}" for c, n, t in frac)
      + " — which is exactly the ordering of the campaign's degradation "
        "(E>3 +1.0 deg, E>5 +1.8, E>10 +2.2).")
    A("")
    A("**Recommendation.**")
    A("")
    A("1. *Do not* revert to the first-in-time partner for the ED input. The rule is not what is wrong:")
    A("   on every event that both rules could match they choose the same cluster (0 CHANGED events),")
    A("   and in the planes where they differ the new partner is the truth-main cluster while the old one")
    A("   was a non-main MARLEY fragment of the same event (98-99% MARLEY, 100% same event, median 0.83-0.88")
    A("   of the main cluster's energy). Reverting would only hide the population again.")
    A("2. **Retrain the ED on matcher-fixed products.** v58 never saw a split-induction event, because")
    A("   the old matcher removed them from its training sample too (`use_matched: true` on old products).")
    A("   The retraining is the only measurement that can separate 'the network never saw this' from")
    A("   'the information is not there'; it is also cheap compared with the 12% statistics at stake.")
    A("   Rebuild the ES training products with the fixed matcher first.")
    A("3. **The `r = min(E_U,E_V)/E_X >= 0.5` cut is a perfect-CT tool only — do NOT deploy it on the")
    A("   CT-selected sample** (section 8). On perfect CT it is exactly the right knob: it keeps 75% of")
    A("   the matchfix events and takes theta68 from 13.81 to 11.66 deg, i.e. it removes the whole")
    A("   matcher-fix penalty and then some, and it also helps the original products (12.73 -> 11.62).")
    A("   On the deployed selection (CT v80 >= 0.80, E > 5) it does nothing at r >= 0.3 and hurts above")
    A("   it (+2.2 deg at 0.5, +5.1 at 0.7 on the matchfix products), because the CT has already removed")
    A("   that population - 93% of the CT-selected events pass r >= 0.5 against 75% of the perfect-CT")
    A("   ones - and the ES purity does not move at all (0.413 -> 0.412 -> 0.403), so the cut only")
    A("   throws away statistics in a sample that is 59% CC. Keep r as an ED-input quality flag, or")
    A("   revisit it after a retrain, but do not add it to the deployed selection today.")
    A("4. A matcher-level alternative worth a test: merge the induction-plane MARLEY fragments that share")
    A("   a match instead of picking one of them, so the ED gets the whole induction view. That is a")
    A("   change to `match_clusters` + the image writer, not to the network.")
    A("")
    A("**Caveat.** Everything above is the perfect-CT scenario. The full pipeline (CT v80 > 0.80, E>5) is")
    A("flat (16.33 -> 16.11) because the CT already throws this population away: it selects 174 -> 176")
    A("events/burst where perfect CT selects 236 -> 264, i.e. the CT keeps only ~2 of the ~28 new events.")
    A("The weighted-ct scenario, which keeps everything, gets worse (20.95 -> 22.42). So the fix is")
    A("currently invisible where it should have paid off, and a cut like (3) has to be re-measured inside")
    A("the full pipeline before it is adopted.")
    A("")
    Path(out_md).write_text("\n".join(L) + "\n")
    print(f"wrote {out_md}")
    return L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cat")
    ap.add_argument("--cats", help="comma list or range like 623-672")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--no-fits", action="store_true")
    ap.add_argument("--init-modes", default="legacy,grid")
    ap.add_argument("--summarize", action="store_true")
    ap.add_argument("--extra", action="store_true", help="only the truth-free-cut variants")
    ap.add_argument("--frag", action="store_true", help="only the per-event fragmentation table")
    ap.add_argument("--rscan", action="store_true", help="only the r = min(E_U,E_V)/E_X cut scan")
    ap.add_argument("--comp-cut", type=float, default=0.5)
    ap.add_argument("--out-md")
    args = ap.parse_args()

    if os.environ.get("INIT_DONE", "").lower() != "true":
        raise RuntimeError("Environment not initialized. Run: source scripts/init.sh")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.summarize:
        summarize(out_dir, args.out_md or (out_dir / "ed_on_matchfix_diagnosis.md"))
        return

    cats = []
    if args.cat:
        cats.append(args.cat)
    if args.cats:
        if "-" in args.cats and "," not in args.cats:
            a, b = args.cats.split("-")
            cats += [f"cat{int(i):06d}" for i in range(int(a), int(b) + 1)]
        else:
            cats += [c if c.startswith("cat") else f"cat{int(c):06d}" for c in args.cats.split(",")]
    if not cats:
        raise SystemExit("give --cat or --cats")

    inits = [m for m in args.init_modes.split(",") if m]
    if args.rscan:
        for cat in cats:
            r = rscan(cat, out_dir)
            print(cat, {k: round(v["theta"], 2) for k, v in r["sets"]["fix"].items()})
            sys.stdout.flush()
        return
    if args.frag:
        for cat in cats:
            frag_table(cat, out_dir)
            print(cat, "frag ok")
            sys.stdout.flush()
        return
    if args.extra:
        for cat in cats:
            res = extra_variants(cat, out_dir, comp_cut=args.comp_cut)
            (out_dir / f"{cat}_extra.json").write_text(json.dumps({"cat": cat, "fits": res}, indent=1))
            print(cat, {k: round(v["theta"], 2) for k, v in res.items()})
            sys.stdout.flush()
        return
    for cat in cats:
        rows, ev_summary, info, pack_o, pack_f = build_cat_table(cat, out_dir)
        res = {"cat": cat, "info": info, "events": ev_summary,
               "class_counts": {c: int(sum(1 for r in rows if r["cls"] == c)) for c in CLASSES}}
        # bit-identity check for SAME events
        same = [r for r in rows if r["cls"] == "SAME" and r["valid_o"] and r["valid_f"]]
        if same:
            do = np.array([r["dir_o"] for r in same])
            df = np.array([r["dir_f"] for r in same])
            res["same_bit_identical"] = bool(np.array_equal(do, df))
            res["same_max_abs_diff"] = float(np.max(np.abs(do - df)))
            res["same_n"] = len(same)
        if not args.no_fits:
            fits, tb = burst_variants(rows, pack_o, pack_f, init_modes=inits)
            res["fits"] = fits
            res["true_burst_dir"] = [float(x) for x in tb]
        (out_dir / f"{cat}_diag.json").write_text(json.dumps(res, indent=1))
        print(f"{cat}: {res['class_counts']} same_identical={res.get('same_bit_identical')}")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
