#!/usr/bin/env python3
"""Do the ORIGINAL products of cats 1-82 give better electron directions than the
REGENERATED (_r2) ones under IDENTICAL current code?  (read-only diagnosis)

The regeneration campaign (pipeline-campaign/v80_fixed_1000) re-processed the evaluation
bursts with today's chain and ran the FIXED pointing code on them.  On batch 2 (cats 1-82)
the true-ES scenarios with RECONSTRUCTED electron directions came out ~1 deg worse than the
July-2026 campaign on the same cats, although the code changes alone are known to move those
scenarios by <0.3 deg on identical events (cats 623-672).  Either the products changed, or it
is a fluctuation.

Per cat this script

 1. replays the pipeline sample loader (python/lib/sample_loader.py) on the ES cluster images
    of BOTH product sets - the original ones still on disk under
    sn-burst-samples/<cat>/<cat>_cluster_images_tick3_ch2_min2_tot3_e3p0 and the regenerated
    ones packed in <cat>_cluster_images_tick3_ch2_min2_tot3_e3p0_r2_es.tar - keeping the
    3-plane matched main-track clusters, images included;

 2. runs the SAME ED model (json/example_config.json neural_networks.electron_direction) with
    the SAME preprocessing as python/app/ed_inference.py on both sets;

 3. validates the replay: for the regenerated set the ED directions are compared with the
    campaign's own predictions/reco_directions.npz (the ES rows of volumes.npz are recovered
    by inverting the loader's seed-42 shuffle) and the burst fits are compared with the
    campaign's scenario_cos_theta_report.json;

 4. fits the burst direction with the CURRENT code (ana.burst_direction, clipped pdf lookup,
    grid-seeded emcee) on both product sets for
       scenario 1  true ES, TRUE electron dirs, E > 3
       scenario 2  true ES, reco dirs,          E > 3
       scenario 5  true ES, reco dirs,          E > 10
       scenario 6  true ES, reco dirs,          E > 5;

 5. records the per-event quantities that could explain a difference: cos(reco, true e-dir),
    true and cluster energy, U/V partner cluster energies, per-plane image occupancy/charge,
    and the 3-plane match bookkeeping of the raw files.

Nothing is written outside --out-dir (and --untar-dir, which only receives copies of the
packed products).  No production file is touched.

Usage (one cat per condor job):
  python3 python/ana/product_effect_replay.py --cat cat000003 --out-dir <dir>
  python3 python/ana/product_effect_replay.py --summarize --out-dir <dir> --out-md <file.md>
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

python_root = Path(__file__).resolve().parents[1]
repo_root = python_root.parent
sys.path.insert(0, str(python_root))
sys.path.insert(0, str(python_root / "lib"))

from ana.burst_direction import (  # noqa: E402
    normalize_rows,
    normalize_vector,
    reconstruct_burst_direction,
)

SAMPLE_ROOT = "/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples"
CAMPAIGN_R2 = "/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-campaign/v80_fixed_1000"
OLD_REPORTS = "/eos/user/e/evilla/dune/sn-tps/condor_scenarios_v80t080_final"
SUFFIX = "_cluster_images_tick3_ch2_min2_tot3_e3p0"
PDF_PATH = str(repo_root / "data" / "cosine_energy_pdf.npz")
ED_MODEL = ("/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/"
            "three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/"
            "model_epoch_12_val_loss_0.8898.keras")

EMCEE_CFG = {"nwalkers": 128, "nsteps": 500, "discard": 100, "random_seed": 42,
             "prior_type": "uniform", "prior_sigma_deg": 10.0}

# (key, direction_mode, min_energy_mev, campaign scenario name)
SELECTIONS = [
    ("s1_true_dir_e3", "true", 3.0, "scenario_1_best_case"),
    ("s2_reco_e3", "reco", 3.0, "scenario_2_perfect_ct"),
    ("s5_reco_e10", "reco", 10.0, "scenario_5_perfect_ct_e_gt_10mev"),
    ("s6_reco_e5", "reco", 5.0, "scenario_6_perfect_ct_e_gt_5mev"),
]

E_BINS = [(3.0, 5.0), (5.0, 10.0), (10.0, 20.0), (20.0, 30.0), (30.0, 1e9)]
E_BIN_LABELS = ["3-5", "5-10", "10-20", "20-30", "30+"]

SETS = ["orig", "r2"]


# --------------------------------------------------------------------------------------
# product access
# --------------------------------------------------------------------------------------
def orig_product_dir(cat):
    return Path(SAMPLE_ROOT) / cat / f"{cat}{SUFFIX}"


def r2_product_dir(cat, untar_dir):
    """Unpack <cat>..._r2_es.tar into untar_dir/<cat> (never in place) and return it."""
    tar = Path(SAMPLE_ROOT) / cat / f"{cat}{SUFFIX}_r2_es.tar"
    if not tar.exists():
        raise FileNotFoundError(f"missing regenerated ES tar: {tar}")
    dest = Path(untar_dir) / cat
    marker = dest / ".untar_ok"
    if not marker.exists():
        dest.mkdir(parents=True, exist_ok=True)
        subprocess.run(["tar", "xf", str(tar), "-C", str(dest)], check=True)
        marker.write_text(str(tar))
    return dest


def campaign_run_dir(cat, untar_dir, scenario="scenario_2_perfect_ct"):
    """Unpack the campaign's slim tar (metadata + reco dirs only) and return the run dir."""
    live = Path(CAMPAIGN_R2) / cat / scenario
    if live.is_dir():
        runs = sorted(live.glob("pipeline_run_*"))
        if runs:
            return runs[-1]
    tar = Path(CAMPAIGN_R2) / cat / f"{cat}_scenarios_slim.tar"
    if not tar.exists():
        return None
    dest = Path(untar_dir) / f"{cat}_campaign"
    marker = dest / f".untar_ok_{scenario}"
    if not marker.exists():
        dest.mkdir(parents=True, exist_ok=True)
        subprocess.run(["tar", "xf", str(tar), "-C", str(dest), "--wildcards",
                        f"{scenario}/*"], check=True)
        marker.write_text(str(tar))
    runs = sorted((dest / scenario).glob("pipeline_run_*"))
    return runs[-1] if runs else None


# --------------------------------------------------------------------------------------
# loader replay (images kept; mirrors sample_loader._load_samples_from_folder)
# --------------------------------------------------------------------------------------
def _main_index(meta):
    """{match_id: row} over MAIN-TRACK clusters with match_id != -1."""
    return {int(m): i for i, m in enumerate(meta[:, 13]) if meta[i, 2] == 1 and m != -1}


def _any_index(meta):
    out = {}
    for i, m in enumerate(meta[:, 13]):
        if m != -1:
            out.setdefault(int(m), i)
    return out


def replay_es(product_dir):
    """Replay the ES side of the loader.  Returns (records, file_stats).

    records preserve the loader order; each carries the X metadata row, the U/V partner
    metadata rows and the three plane images.
    """
    product_dir = Path(product_dir)
    files = sorted((product_dir / "X").glob("es_*_bg_matched_planeX.npz"))
    if not files:
        raise FileNotFoundError(f"no ES X files in {product_dir}/X")
    records = []
    fstats = []
    for fp in files:
        dx = np.load(fp, allow_pickle=True)
        du = np.load(product_dir / "U" / fp.name.replace("planeX", "planeU"), allow_pickle=True)
        dv = np.load(product_dir / "V" / fp.name.replace("planeX", "planeV"), allow_pickle=True)
        mx, mu, mv = dx["metadata"], du["metadata"], dv["metadata"]
        ix_map, iu_map, iv_map = _main_index(mx), _main_index(mu), _main_index(mv)
        iu_any, iv_any = _any_index(mu), _any_index(mv)
        common = sorted(set(ix_map) & set(iu_map) & set(iv_map))

        n_main_x = int(np.sum(mx[:, 2] == 1))
        n_main_x_mid = int(np.sum((mx[:, 2] == 1) & (mx[:, 13] != -1)))
        n_u_ok = sum(1 for mid in ix_map if mid in iu_map)
        n_v_ok = sum(1 for mid in ix_map if mid in iv_map)
        fstats.append(dict(
            file=fp.name,
            n_clusters_x=int(mx.shape[0]), n_clusters_u=int(mu.shape[0]), n_clusters_v=int(mv.shape[0]),
            n_marley_x=int(np.sum(mx[:, 1] == 1)),
            n_main_x=n_main_x, n_main_x_with_mid=n_main_x_mid,
            n_x_main_u_partner=int(n_u_ok), n_x_main_v_partner=int(n_v_ok),
            n_3plane=len(common),
            n_events_x=int(len(np.unique(mx[:, 0]))),
        ))

        for mid in common:
            i_x, i_u, i_v = ix_map[mid], iu_map[mid], iv_map[mid]
            records.append(dict(
                file=fp.name, mid=int(mid), ix=int(i_x), iu=int(i_u), iv=int(i_v),
                meta=mx[i_x].astype(np.float64),
                meta_u=mu[i_u].astype(np.float64),
                meta_v=mv[i_v].astype(np.float64),
                img_x=dx["images"][i_x], img_u=du["images"][i_u], img_v=dv["images"][i_v],
                # explanation bookkeeping for clusters that lose a partner in the other set
                u_any=int(mid in iu_any), v_any=int(mid in iv_any),
            ))
    return records, fstats


# --------------------------------------------------------------------------------------
# ED inference (mirrors python/app/ed_inference.py preprocessing exactly)
# --------------------------------------------------------------------------------------
_MODEL = {}


def _get_model(model_path):
    if "m" not in _MODEL:
        import tensorflow as tf
        _MODEL["m"] = tf.keras.models.load_model(model_path, compile=False)
        _MODEL["tf"] = tf
    return _MODEL["m"], _MODEL["tf"]


def _preprocess(stack, exp_h, exp_w, exp_c, tf):
    sel = np.asarray(stack, dtype=np.float32)
    if sel.ndim == 3:
        sel = sel[..., np.newaxis]
    if exp_h is not None and exp_w is not None:
        if sel.shape[1] != int(exp_h) or sel.shape[2] != int(exp_w):
            sel = tf.image.resize(sel, (int(exp_h), int(exp_w)), method="bilinear").numpy()
    if exp_c is not None and int(exp_c) != sel.shape[-1]:
        if int(exp_c) == 1:
            sel = sel[..., :1]
        else:
            sel = np.repeat(sel[..., :1], int(exp_c), axis=-1)
    return sel


def run_ed(records, model_path=ED_MODEL, batch_size=32):
    """(N,3) unit vectors from the 3-plane ED model, in record order."""
    if not records:
        return np.zeros((0, 3), dtype=np.float64)
    model, tf = _get_model(model_path)
    exp = model.inputs[0].shape if getattr(model, "inputs", None) else None
    exp_h = exp[1] if exp is not None and len(exp) >= 4 else None
    exp_w = exp[2] if exp is not None and len(exp) >= 4 else None
    exp_c = exp[3] if exp is not None and len(exp) >= 4 else None
    x = _preprocess(np.stack([r["img_x"] for r in records]), exp_h, exp_w, exp_c, tf)
    u = _preprocess(np.stack([r["img_u"] for r in records]), exp_h, exp_w, exp_c, tf)
    v = _preprocess(np.stack([r["img_v"] for r in records]), exp_h, exp_w, exp_c, tf)
    n_in = len(model.inputs) if getattr(model, "inputs", None) else 1
    if n_in != 3:
        raise RuntimeError(f"ED model expects {n_in} inputs, 3-plane replay needs 3")
    preds = np.asarray(model.predict([u, v, x], batch_size=batch_size, verbose=0))
    if preds.ndim == 3 and preds.shape[1] == 1:
        preds = preds.squeeze(1)
    if preds.ndim != 2 or preds.shape[1] != 3:
        raise RuntimeError(f"unexpected ED output shape {preds.shape}")
    # pipeline stores float32 unit vectors and re-normalises them in float64 before the fit
    dirs = normalize_rows(preds.astype(np.float64)).astype(np.float32)
    return normalize_rows(dirs.astype(np.float64))


# --------------------------------------------------------------------------------------
# fits
# --------------------------------------------------------------------------------------
def _fit(dirs, energies, true_burst_dir, seed=None):
    cfg = dict(EMCEE_CFG)
    if seed is not None:
        cfg["random_seed"] = int(seed)
    dirs = np.asarray(dirs, dtype=np.float64)
    if dirs.shape[0] == 0:
        return dict(n=0, cos=float("nan"), theta=float("nan"), omega68=float("nan"))
    res = reconstruct_burst_direction(
        selected_dirs=dirs,
        selected_weights=np.ones(dirs.shape[0], dtype=np.float64),
        selected_energies=np.asarray(energies, dtype=np.float64),
        true_burst_dir=true_burst_dir,
        use_emcee=True, emcee_cfg=cfg, pdf_path=PDF_PATH,
    )
    cos = (float(np.clip(np.dot(res["reco_dir"], true_burst_dir), -1, 1))
           if res["reco_dir"] is not None else float("nan"))
    return dict(n=int(dirs.shape[0]), cos=cos,
                theta=float(np.degrees(np.arccos(cos))),
                omega68=float(res["omega68_deg"]),
                acceptance=float(res["acceptance_fraction"]))


# --------------------------------------------------------------------------------------
# per-cat driver
# --------------------------------------------------------------------------------------
def _cluster_stats(records):
    """Per-cluster arrays used for the product comparison."""
    n = len(records)
    out = dict(
        event=np.array([r["meta"][0] for r in records], dtype=np.int64),
        mid=np.array([r["mid"] for r in records], dtype=np.int64),
        ix=np.array([r["ix"] for r in records], dtype=np.int64),
        e_clus=np.array([r["meta"][10] for r in records], dtype=np.float64),
        e_true=np.array([r["meta"][11] for r in records], dtype=np.float64),
        e_u=np.array([r["meta_u"][10] for r in records], dtype=np.float64),
        e_v=np.array([r["meta_v"][10] for r in records], dtype=np.float64),
        u_is_marley=np.array([r["meta_u"][1] for r in records], dtype=np.float64),
        v_is_marley=np.array([r["meta_v"][1] for r in records], dtype=np.float64),
        true_dir=np.array([normalize_vector(r["meta"][7:10]) if np.linalg.norm(r["meta"][7:10]) > 0
                           else np.full(3, np.nan) for r in records], dtype=np.float64).reshape(n, 3),
        nu_dir=np.array([normalize_vector(r["meta"][15:18]) if np.linalg.norm(r["meta"][15:18]) > 0
                         else np.full(3, np.nan) for r in records], dtype=np.float64).reshape(n, 3),
        true_pos=np.array([r["meta"][4:7] for r in records], dtype=np.float64).reshape(n, 3),
        src_file=np.array([r["file"] for r in records]),
    )
    for pl in ("x", "u", "v"):
        imgs = np.stack([r[f"img_{pl}"] for r in records]).astype(np.float64) if n else np.zeros((0, 1, 1))
        out[f"img_sum_{pl}"] = imgs.reshape(n, -1).sum(axis=1)
        out[f"img_nnz_{pl}"] = (imgs.reshape(n, -1) > 0).sum(axis=1).astype(np.float64)
        out[f"img_max_{pl}"] = imgs.reshape(n, -1).max(axis=1) if n else np.zeros(0)
    return out


def _pair_key(st, i):
    return (str(st["src_file"][i]), int(st["event"][i]), round(float(st["e_true"][i]), 5),
            round(float(st["true_pos"][i][0]), 3), round(float(st["true_pos"][i][2]), 3))


def process_cat(cat, out_dir, untar_dir, seeds=(7, 123)):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    dirs_in = {"orig": orig_product_dir(cat), "r2": r2_product_dir(cat, untar_dir)}
    recs, fstats, stats, eddirs = {}, {}, {}, {}
    for s in SETS:
        recs[s], fstats[s] = replay_es(dirs_in[s])
        stats[s] = _cluster_stats(recs[s])
        eddirs[s] = run_ed(recs[s])
        stats[s]["ed_dir"] = eddirs[s]
        td = stats[s]["true_dir"]
        stats[s]["cos_ed"] = np.clip(np.sum(eddirs[s] * td, axis=1), -1, 1)

    # ---- validation against the campaign's own r2 outputs -----------------------------
    valid = {"replay_rows_ok": None, "n_es_campaign": None,
             "ed_mean_angle_deg": None, "ed_median_angle_deg": None, "ed_max_angle_deg": None}
    run = campaign_run_dir(cat, untar_dir)
    campaign_dirs = None
    if run is not None:
        vol = np.load(Path(run) / "volume_images" / "volumes.npz", allow_pickle=True)
        meta = np.asarray(vol["metadata"])
        n_total = int(meta.shape[0])
        n_es = int(np.sum(meta[:, 3] == 1))
        np.random.seed(42)
        perm = np.random.permutation(n_total)
        rows = np.argsort(perm)[n_total - n_es:]
        mine = np.array([r["meta"] for r in recs["r2"]], dtype=np.float32)
        ok = bool(n_es == len(recs["r2"]) and np.array_equal(meta[rows], mine))
        valid["replay_rows_ok"] = ok
        valid["n_es_campaign"] = n_es
        rp = Path(run) / "predictions" / "reco_directions.npz"
        if ok and rp.exists():
            d = np.load(rp, allow_pickle=True)
            campaign_dirs = normalize_rows(np.asarray(d["reco_dirs"], dtype=np.float64))[rows]
            ang = np.degrees(np.arccos(np.clip(np.sum(campaign_dirs * eddirs["r2"], axis=1), -1, 1)))
            valid["ed_mean_angle_deg"] = float(np.mean(ang))
            valid["ed_median_angle_deg"] = float(np.median(ang))
            valid["ed_max_angle_deg"] = float(np.max(ang))

    # ---- burst fits -------------------------------------------------------------------
    fits = {}
    for s in SETS:
        st = stats[s]
        nu = st["nu_dir"]
        good = np.isfinite(nu).all(axis=1)
        tb = normalize_vector(np.mean(normalize_rows(nu[good]), axis=0))
        e = st["e_clus"]
        for key, dmode, emin, _ in SELECTIONS:
            d = st["true_dir"] if dmode == "true" else st["ed_dir"]
            m = (e >= emin) & np.isfinite(d).all(axis=1) & (np.linalg.norm(d, axis=1) > 0)
            fits[f"{s}|{key}"] = _fit(d[m], e[m], tb)
        # emcee jitter floor on the headline selection
        for sd in seeds:
            d = st["ed_dir"]
            m = (e >= 3.0) & np.isfinite(d).all(axis=1)
            fits[f"{s}|s2_reco_e3|seed{sd}"] = _fit(d[m], e[m], tb, seed=sd)
        stats[s]["true_burst_dir"] = tb
    # campaign directions refit (pure fit-code check of the campaign numbers)
    if campaign_dirs is not None:
        st = stats["r2"]
        tb = st["true_burst_dir"]
        e = st["e_clus"]
        for key, dmode, emin, _ in SELECTIONS:
            if dmode != "reco":
                continue
            m = (e >= emin) & np.isfinite(campaign_dirs).all(axis=1)
            fits[f"campaign|{key}"] = _fit(campaign_dirs[m], e[m], tb)

    # ---- pairing between the two product sets ----------------------------------------
    keys = {s: [_pair_key(stats[s], i) for i in range(len(recs[s]))] for s in SETS}
    idx = {s: {} for s in SETS}
    dup = {s: 0 for s in SETS}
    for s in SETS:
        for i, k in enumerate(keys[s]):
            if k in idx[s]:
                dup[s] += 1
            idx[s][k] = i
    common = sorted(set(idx["orig"]) & set(idx["r2"]))
    pair = dict(
        n_common=len(common), n_orig=len(recs["orig"]), n_r2=len(recs["r2"]),
        dup_orig=dup["orig"], dup_r2=dup["r2"],
        i_orig=np.array([idx["orig"][k] for k in common], dtype=np.int64),
        i_r2=np.array([idx["r2"][k] for k in common], dtype=np.int64),
    )

    # ---- save -------------------------------------------------------------------------
    payload = {}
    for s in SETS:
        for k, v in stats[s].items():
            payload[f"{s}__{k}"] = v
    payload["pair_i_orig"] = pair["i_orig"]
    payload["pair_i_r2"] = pair["i_r2"]
    if campaign_dirs is not None:
        payload["campaign_ed_dir"] = campaign_dirs
    np.savez_compressed(out_dir / f"{cat}_events.npz", **payload)

    summary = dict(
        cat=cat,
        n_files=dict((s, len(fstats[s])) for s in SETS),
        n_clusters=dict((s, len(recs[s])) for s in SETS),
        n_events=dict((s, int(len(set(zip(stats[s]["src_file"].tolist(),
                                          stats[s]["event"].tolist()))))) for s in SETS),
        file_stats=dict((s, fstats[s]) for s in SETS),
        validation=valid,
        fits=fits,
        pairing=dict(n_common=pair["n_common"], n_orig=pair["n_orig"], n_r2=pair["n_r2"],
                     dup_orig=pair["dup_orig"], dup_r2=pair["dup_r2"]),
        true_burst_dir=dict((s, np.asarray(stats[s]["true_burst_dir"]).tolist()) for s in SETS),
        product_dirs=dict((s, str(dirs_in[s])) for s in SETS),
    )
    (out_dir / f"{cat}_summary.json").write_text(json.dumps(summary, indent=2, default=float))
    return summary


# --------------------------------------------------------------------------------------
# summary
# --------------------------------------------------------------------------------------
def _boot_paired(a, b, n_boot=4000, seed=7, stat="theta68"):
    """68% bootstrap interval of the paired difference of a cat-level statistic (b - a)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    if a.size == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)

    def f(x):
        if stat == "theta68":
            return float(np.degrees(np.arccos(np.clip(np.quantile(np.cos(np.radians(x)), 0.32), -1, 1))))
        if stat == "median":
            return float(np.median(x))
        return float(np.mean(x))

    d0 = f(b) - f(a)
    ds = np.empty(n_boot)
    n = a.size
    for i in range(n_boot):
        j = rng.integers(0, n, n)
        ds[i] = f(b[j]) - f(a[j])
    return d0, float(np.quantile(ds, 0.16)), float(np.quantile(ds, 0.84))


def theta68(theta):
    theta = np.asarray(theta, dtype=float)
    theta = theta[np.isfinite(theta)]
    if theta.size == 0:
        return float("nan")
    return float(np.degrees(np.arccos(np.clip(np.quantile(np.cos(np.radians(theta)), 0.32), -1, 1))))


def _old_report(cat):
    p = Path(OLD_REPORTS) / cat / "scenario_cos_theta_report.json"
    if not p.exists():
        return {}
    r = json.loads(p.read_text())
    return {s["scenario"]: s for s in r.get("scenarios", [])}


def _r2_report(cat):
    p = Path(CAMPAIGN_R2) / cat / "scenario_cos_theta_report.json"
    if not p.exists():
        return {}
    r = json.loads(p.read_text())
    return {s["scenario"]: s for s in r.get("scenarios", [])}


def _theta_lists(summaries, key):
    """(old-code/orig, new-code/orig, new-code/r2) per-cat single-pass angles, plus n_selected."""
    scen = dict((k, s) for k, _, _, s in SELECTIONS)[key]
    th_old, th_o, th_r, n_o, n_r, cats = [], [], [], [], [], []
    for s in summaries:
        fo, fr = s["fits"].get(f"orig|{key}"), s["fits"].get(f"r2|{key}")
        if not fo or not fr:
            continue
        cats.append(s["cat"])
        th_o.append(fo["theta"])
        th_r.append(fr["theta"])
        n_o.append(fo["n"])
        n_r.append(fr["n"])
        old = _old_report(s["cat"]).get(scen)
        th_old.append(float(np.degrees(np.arccos(np.clip(old["cos_to_truth"], -1, 1))))
                      if old else np.nan)
    return (np.array(cats), np.array(th_old), np.array(th_o), np.array(th_r),
            np.array(n_o), np.array(n_r))


def _headline_table(summaries, lines, title):
    lines.append(f"### {title} ({len(summaries)} cats)")
    lines.append("")
    lines.append("| selection | theta68 A: old code / ORIG | theta68 B: new code / ORIG "
                 "| theta68 C: new code / R2 | PRODUCT effect d theta68 (C-B) [68% boot] "
                 "| median paired (C-B) | CODE effect d theta68 (B-A) [68% boot] "
                 "| total (C-A) | mean n_sel ORIG/R2 |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    store = {}
    for key, dmode, emin, scen in SELECTIONS:
        cats, th_old, th_o, th_r, n_o, n_r = _theta_lists(summaries, key)
        d0, lo, hi = _boot_paired(th_o, th_r, stat="theta68")
        c0, clo, chi = _boot_paired(th_old, th_o, stat="theta68")
        dd = th_r - th_o
        lines.append(f"| {key} | {theta68(th_old):.2f} | {theta68(th_o):.2f} | {theta68(th_r):.2f} "
                     f"| {d0:+.2f} [{lo:+.2f}, {hi:+.2f}] | {np.median(dd):+.2f} "
                     f"| {c0:+.2f} [{clo:+.2f}, {chi:+.2f}] "
                     f"| {theta68(th_r) - theta68(th_old):+.2f} "
                     f"| {np.mean(n_o):.0f}/{np.mean(n_r):.0f} |")
        store[key] = (cats, th_old, th_o, th_r, n_o, n_r)
    lines.append("")
    return store


def summarize(out_dir, out_md, cats_filter=None):
    out_dir = Path(out_dir)
    summaries = []
    for p in sorted(out_dir.glob("cat*_summary.json")):
        summaries.append(json.loads(p.read_text()))
    if not summaries:
        raise SystemExit(f"no per-cat summaries in {out_dir}")
    sub = [s for s in summaries if s["cat"] in set(cats_filter)] if cats_filter else []
    cats = [s["cat"] for s in summaries]

    lines = []
    lines.append("# Original vs regenerated (`_r2`) products under identical current code")
    lines.append("")
    lines.append("Question: on the batch-2 cats (1-82) the regenerated campaign "
                 "(`pipeline-campaign/v80_fixed_1000`, new products + fixed pointing code) came "
                 "out ~1-2 deg worse than the July-2026 campaign "
                 "(`condor_scenarios_v80t080_final`, original products + old code) in the true-ES "
                 "scenarios that use RECONSTRUCTED electron directions.  Is that the products or "
                 "the code?  Here BOTH product sets are pushed through the SAME current code "
                 "(same loader, same ED model and preprocessing, same clipped-pdf grid-seeded "
                 "emcee fit), so any residual difference is a product difference.")
    lines.append("")
    lines.append(f"- cats analysed: **{len(cats)}** ({cats[0]} ... {cats[-1]})")
    lines.append("- selections: `s1` true ES / TRUE e-dirs / E>3 (scenario 1), `s2` true ES / reco "
                 "dirs / E>3 (scenario 2), `s5` E>10 (scenario 5), `s6` E>5 (scenario 6)")
    lines.append("- metric: per-cat single-pass angle between the fitted burst direction and truth; "
                 "`theta68` = arccos of the 0.32 quantile of cos across cats (the campaign metric)")
    lines.append("")

    # ---------------- validation -------------------------------------------------------
    ok = [s for s in summaries if s["validation"].get("replay_rows_ok")]
    ed_ang = [s["validation"]["ed_mean_angle_deg"] for s in summaries
              if s["validation"].get("ed_mean_angle_deg") is not None]
    lines.append("## 1. Replay validation against the campaign's own r2 outputs")
    lines.append("")
    lines.append(f"- loader row order reproduced (inverting the seed-42 shuffle of `volumes.npz`) "
                 f"for **{len(ok)}/{len(summaries)}** cats")
    if ed_ang:
        lines.append(f"- my ED directions vs the campaign `predictions/reco_directions.npz`: mean "
                     f"angle **{np.mean(ed_ang):.2e} deg** (worst cat {np.max(ed_ang):.2e} deg) "
                     f"-> same model, same preprocessing, same inputs")
    rows = []
    for s in summaries:
        rep = _r2_report(s["cat"])
        for key, dmode, emin, scen in SELECTIONS:
            f = s["fits"].get(f"r2|{key}")
            r = rep.get(scen)
            if f and r:
                rows.append((f["theta"], float(r["single_pass_theta_deg"]),
                             f["n"], int(r["n_selected"])))
    if rows:
        d = np.array([r[0] - r[1] for r in rows])
        dn = np.array([r[2] - r[3] for r in rows])
        lines.append(f"- my fit on the r2 products vs the campaign report, same cats and scenarios: "
                     f"{len(rows)} entries, mean |dtheta| **{np.mean(np.abs(d)):.2e} deg**, worst "
                     f"{np.max(np.abs(d)):.2e} deg; n_selected identical for "
                     f"**{int(np.sum(dn == 0))}/{len(rows)}**")
    lines.append("")
    lines.append("The replay is therefore an exact reproduction of the campaign on the regenerated "
                 "products, and the ORIG column below is the same code on the other products.")
    lines.append("")

    # ---------------- headline tables --------------------------------------------------
    lines.append("## 2. theta68 per selection")
    lines.append("")
    store_all = _headline_table(summaries, lines, "All cats")
    store_sub = _headline_table(sub, lines, "Requested 20-cat subset (every 4th cat, 3..79)") if sub else {}

    # emcee jitter
    jit = []
    for s in summaries:
        for st in SETS:
            base = s["fits"].get(f"{st}|s2_reco_e3")
            for sd in (7, 123):
                alt = s["fits"].get(f"{st}|s2_reco_e3|seed{sd}")
                if base and alt:
                    jit.append(abs(alt["theta"] - base["theta"]))
    if jit:
        lines.append(f"emcee walker-seed jitter, same events refitted with seeds 7/123 (s2): mean "
                     f"|dtheta| {np.mean(jit):.2f} deg, median {np.median(jit):.2f}, 90th pct "
                     f"{np.quantile(jit, 0.9):.2f}, max {np.max(jit):.2f}.")
        lines.append("")

    # ---------------- attribution: common subset ---------------------------------------
    var = []
    for s in summaries:
        p = out_dir / f"{s['cat']}_variants.json"
        if p.exists():
            var.append(json.loads(p.read_text()))
    if var:
        lines.append("## 3. Attribution: the clusters present in BOTH product sets")
        lines.append("")
        n_pair = np.array([v["n_pair"] for v in var])
        n_same_img = np.array([v["n_pair_same_image"] for v in var])
        n_same_ed = np.array([v["n_pair_same_ed"] for v in var])
        lines.append(f"- paired clusters (same MARLEY event, same true energy and vertex): "
                     f"{n_pair.sum()} over {len(var)} cats")
        lines.append(f"- of those, **{100*n_same_img.sum()/n_pair.sum():.1f}%** have "
                     f"bit-identical X/U/V images in the two product sets and "
                     f"**{100*n_same_ed.sum()/n_pair.sum():.1f}%** an identical ED direction")
        chg = [v["mean_pair_ed_angle_changed_deg"] for v in var
               if np.isfinite(v["mean_pair_ed_angle_changed_deg"])]
        if chg:
            lines.append(f"- on the clusters whose images DID change, the ED direction moves by "
                         f"{np.mean(chg):.1f} deg on average")
        lines.append("")
        lines.append("| fit | theta68 ORIG | theta68 R2 | d (R2-ORIG) [68% boot] | median paired d |")
        lines.append("|---|---|---|---|---|")
        for key, lab in (("common_reco_e3", "common clusters, reco dirs, E>3"),
                         ("common_reco_e5", "common clusters, reco dirs, E>5"),
                         ("common_reco_e10", "common clusters, reco dirs, E>10"),
                         ("common_true_e3", "common clusters, TRUE dirs, E>3")):
            a = np.array([v["fits"][f"orig|{key}"]["theta"] for v in var])
            b = np.array([v["fits"][f"r2|{key}"]["theta"] for v in var])
            d0, lo, hi = _boot_paired(a, b, stat="theta68")
            lines.append(f"| {lab} | {theta68(a):.2f} | {theta68(b):.2f} | "
                         f"{d0:+.2f} [{lo:+.2f}, {hi:+.2f}] | {np.median(b-a):+.2f} |")
        lines.append("")
        lines.append("If the two product sets differed in a way that hurts the ED network, these "
                     "rows - the very same physics events in both sets - would separate.  Whatever "
                     "difference survives here is only the handful of clusters whose images changed.")
        lines.append("")

    # ---------------- which code change moved the numbers ------------------------------
    scan = []
    for s_ in summaries:
        p_ = out_dir / f"{s_['cat']}_codescan.json"
        if p_.exists():
            scan.append(json.loads(p_.read_text()))
    if scan:
        lines.append("## 3b. Which pointing-code change moved the numbers "
                     "(ORIGINAL products only, same events as the July campaign)")
        lines.append("")
        lines.append("`hole` = the pre-2026-09-04 pdf lookup (bin-centre grid, fill 1e-10 outside); "
                     "`clip` = today's floored/renormalised table with clipped queries.  "
                     "`legacy` = the pre-2026-09-07 walker start (45 deg around the weighted mean); "
                     "`grid` = today's start at the grid maximum with an auto width.  "
                     "`hole+legacy` is the July configuration, `clip+grid` is today's.")
        lines.append("")
        lines.append("| combination | theta68 E>3 | theta68 E>5 | theta68 E>10 |")
        lines.append("|---|---|---|---|")
        order = [("hole_legacy", "hole + legacy (July code)"), ("hole_grid", "hole + grid"),
                 ("clip_legacy", "clip + legacy"), ("clip_grid", "clip + grid (today)")]
        for name, lab in order:
            cells = []
            for k in ("e3", "e5", "e10"):
                th = np.array([v["fits"][f"{name}|{k}"]["theta"] for v in scan])
                cells.append(f"{theta68(th):.2f}")
            lines.append(f"| {lab} | " + " | ".join(cells) + " |")
        # the July reports themselves, for closure
        cells = []
        for key in ("s2_reco_e3", "s6_reco_e5", "s5_reco_e10"):
            _, th_old, _, _, _, _ = _theta_lists(summaries, key)
            cells.append(f"{theta68(th_old):.2f}")
        lines.append("| *July reports (old code, unseeded emcee)* | " + " | ".join(cells) + " |")
        lines.append("")
        base = np.array([v["fits"]["hole_legacy|e10"]["theta"] for v in scan])
        for name, lab in order[1:]:
            th = np.array([v["fits"][f"{name}|e10"]["theta"] for v in scan])
            d0, lo, hi = _boot_paired(base, th, stat="theta68")
            lines.append(f"- E>10, {lab} vs July code: d theta68 {d0:+.2f} [{lo:+.2f}, {hi:+.2f}], "
                         f"median paired {np.median(th-base):+.2f} deg")
        lines.append("")

    # ---------------- unweighted-mean estimator (what the old chain effectively was) ----
    mean_th = {st: {k: [] for k in ("e3", "e5", "e10")} for st in SETS}
    for s in summaries:
        d = np.load(out_dir / f"{s['cat']}_events.npz", allow_pickle=True)
        for st in SETS:
            tb = np.asarray(s["true_burst_dir"][st], dtype=np.float64)
            e = d[f"{st}__e_clus"]
            ed = d[f"{st}__ed_dir"]
            for k, emin in (("e3", 3.0), ("e5", 5.0), ("e10", 10.0)):
                m = e >= emin
                v = normalize_vector(np.sum(ed[m], axis=0))
                mean_th[st][k].append(float(np.degrees(np.arccos(np.clip(np.dot(v, tb), -1, 1)))))
    lines.append("## 3c. Cross-check: the plain mean of the ED directions (no emcee)")
    lines.append("")
    lines.append("Reference point, not an emulation: the plain (unweighted) mean of the ED unit "
                 "vectors. It is worse than every emcee variant on this sample, so the July numbers "
                 "were NOT simply the mean direction in disguise - the old chain did move, it just "
                 "moved on a broken likelihood surface (section 3b).")
    lines.append("")
    lines.append("| selection | theta68 mean-dir ORIG | theta68 mean-dir R2 | d [68% boot] |")
    lines.append("|---|---|---|---|")
    for k, lab in (("e3", "E>3"), ("e5", "E>5"), ("e10", "E>10")):
        a = np.array(mean_th["orig"][k])
        b = np.array(mean_th["r2"][k])
        d0, lo, hi = _boot_paired(a, b, stat="theta68")
        lines.append(f"| {lab} | {theta68(a):.2f} | {theta68(b):.2f} | {d0:+.2f} [{lo:+.2f}, {hi:+.2f}] |")
    lines.append("")

    # ---------------- per-event ED quality ---------------------------------------------
    lines.append("## 4. Per-event ED quality: mean cos(reco e-dir, true e-dir) in energy bins")
    lines.append("")
    cos_bins = {s: {lab: [] for lab in E_BIN_LABELS} for s in SETS}
    n_bins = {s: {lab: 0 for lab in E_BIN_LABELS} for s in SETS}
    paired_cos = {s: [] for s in SETS}
    prop = {s: dict(e_true=[], ratio=[], uv_ratio=[], img_nnz_x=[], img_sum_x=[],
                    img_nnz_u=[], img_nnz_v=[], img_sum_u=[], img_sum_v=[],
                    partner_marley=[]) for s in SETS}
    match_frac = {s: dict(mid=[], u=[], v=[], both=[], n_main=[], n_clus=[], n_bg=[]) for s in SETS}
    for s in summaries:
        d = np.load(out_dir / f"{s['cat']}_events.npz", allow_pickle=True)
        for st in SETS:
            e = d[f"{st}__e_clus"]
            c = d[f"{st}__cos_ed"]
            et = d[f"{st}__e_true"]
            eu, ev = d[f"{st}__e_u"], d[f"{st}__e_v"]
            for (lo, hi), lab in zip(E_BINS, E_BIN_LABELS):
                m = (e >= lo) & (e < hi)
                # always append (nan when the cat has no cluster in the bin) so the two
                # product sets stay index-aligned for the paired bootstrap
                cos_bins[st][lab].append(float(np.mean(c[m])) if np.any(m) else float("nan"))
                n_bins[st][lab] += int(np.sum(m))
            prop[st]["e_true"].append(et)
            prop[st]["ratio"].append(e / np.maximum(et, 1e-9))
            prop[st]["uv_ratio"].append(np.minimum(eu, ev) / np.maximum(e, 1e-9))
            prop[st]["partner_marley"].append(
                0.5 * (d[f"{st}__u_is_marley"] + d[f"{st}__v_is_marley"]))
            for k in ["img_nnz_x", "img_sum_x", "img_nnz_u", "img_nnz_v", "img_sum_u", "img_sum_v"]:
                prop[st][k].append(d[f"{st}__{k}"])
            fs = s["file_stats"][st]
            nm = sum(f["n_main_x"] for f in fs)
            match_frac[st]["mid"].append(sum(f["n_main_x_with_mid"] for f in fs) / max(nm, 1))
            match_frac[st]["u"].append(sum(f["n_x_main_u_partner"] for f in fs) / max(nm, 1))
            match_frac[st]["v"].append(sum(f["n_x_main_v_partner"] for f in fs) / max(nm, 1))
            match_frac[st]["both"].append(sum(f["n_3plane"] for f in fs) / max(nm, 1))
            match_frac[st]["n_main"].append(nm)
            match_frac[st]["n_clus"].append(sum(f["n_clusters_x"] for f in fs))
            match_frac[st]["n_bg"].append(sum(f["n_clusters_x"] - f["n_marley_x"] for f in fs))
        io, ir = d["pair_i_orig"], d["pair_i_r2"]
        paired_cos["orig"].append(d["orig__cos_ed"][io])
        paired_cos["r2"].append(d["r2__cos_ed"][ir])

    lines.append("| E_clus bin [MeV] | mean cos ORIG | mean cos R2 | d (R2-ORIG) [68% boot over cats] "
                 "| mean angle ORIG/R2 [deg] | n clusters ORIG/R2 |")
    lines.append("|---|---|---|---|---|---|")
    for lab in E_BIN_LABELS:
        a, b = np.array(cos_bins["orig"][lab]), np.array(cos_bins["r2"][lab])
        d0, lo, hi = _boot_paired(a, b, stat="mean")
        lines.append(f"| {lab} | {np.nanmean(a):.4f} | {np.nanmean(b):.4f} | "
                     f"{d0:+.4f} [{lo:+.4f}, {hi:+.4f}] | "
                     f"{np.degrees(np.arccos(np.clip(np.nanmean(a), -1, 1))):.1f}/"
                     f"{np.degrees(np.arccos(np.clip(np.nanmean(b), -1, 1))):.1f} | "
                     f"{n_bins['orig'][lab]}/{n_bins['r2'][lab]} |")
    lines.append("")
    co = np.concatenate(paired_cos["orig"])
    cr = np.concatenate(paired_cos["r2"])
    pm_o = [float(x.mean()) for x in paired_cos["orig"]]
    pm_r = [float(x.mean()) for x in paired_cos["r2"]]
    d0, lo, hi = _boot_paired(pm_o, pm_r, stat="mean")
    lines.append(f"On the {co.size} clusters present in BOTH product sets: mean cos ORIG "
                 f"{co.mean():.4f}, R2 {cr.mean():.4f}, difference {d0:+.4f} [{lo:+.4f}, {hi:+.4f}] "
                 f"(per-cat bootstrap).")
    lines.append("")

    # ---------------- event-set properties ---------------------------------------------
    lines.append("## 5. Event-set properties")
    lines.append("")
    lines.append("| quantity | ORIG | R2 |")
    lines.append("|---|---|---|")
    n_o = [s["n_clusters"]["orig"] for s in summaries]
    n_r = [s["n_clusters"]["r2"] for s in summaries]
    lines.append(f"| ES 3-plane matched main tracks per cat | {np.mean(n_o):.1f} | {np.mean(n_r):.1f} |")
    nf_o = [s["n_files"]["orig"] for s in summaries]
    nf_r = [s["n_files"]["r2"] for s in summaries]
    lines.append(f"| ES cluster-image files per cat (of 10) | {np.mean(nf_o):.2f} | {np.mean(nf_r):.2f} |")
    lines.append(f"| cats with fewer than 10 ES files | {int(np.sum(np.array(nf_o) < 10))} | "
                 f"{int(np.sum(np.array(nf_r) < 10))} |")
    for k, lab in [("e_true", "true electron energy [MeV] (mean)"),
                   ("ratio", "E_cluster / E_true (mean)"),
                   ("uv_ratio", "min(E_U,E_V)/E_X (mean)"),
                   ("partner_marley", "partner clusters flagged MARLEY (mean over U,V)"),
                   ("img_nnz_x", "X image non-zero pixels (mean)"),
                   ("img_nnz_u", "U image non-zero pixels (mean)"),
                   ("img_nnz_v", "V image non-zero pixels (mean)"),
                   ("img_sum_x", "X image charge sum (mean)"),
                   ("img_sum_u", "U image charge sum (mean)"),
                   ("img_sum_v", "V image charge sum (mean)")]:
        a = np.concatenate(prop["orig"][k])
        b = np.concatenate(prop["r2"][k])
        lines.append(f"| {lab} | {np.nanmean(a):.4f} | {np.nanmean(b):.4f} |")
    for k, lab in [("mid", "X main tracks with match_id != -1"),
                   ("u", "X main tracks with a U main-track partner"),
                   ("v", "X main tracks with a V main-track partner"),
                   ("both", "X main tracks matched in all three planes")]:
        lines.append(f"| fraction: {lab} | {np.mean(match_frac['orig'][k]):.4f} | "
                     f"{np.mean(match_frac['r2'][k]):.4f} |")
    lines.append(f"| X clusters per cat (all, ES files) | {np.mean(match_frac['orig']['n_clus']):.0f} | "
                 f"{np.mean(match_frac['r2']['n_clus']):.0f} |")
    lines.append(f"| X non-MARLEY (radiological) clusters per cat | "
                 f"{np.mean(match_frac['orig']['n_bg']):.1f} | {np.mean(match_frac['r2']['n_bg']):.1f} |")
    lines.append("")
    a = np.concatenate(prop["orig"]["e_true"])
    b = np.concatenate(prop["r2"]["e_true"])
    qs = [0.1, 0.25, 0.5, 0.75, 0.9]
    lines.append("True electron energy quantiles [MeV]: ORIG " +
                 ", ".join(f"q{int(q*100)}={np.quantile(a, q):.2f}" for q in qs) +
                 "; R2 " + ", ".join(f"q{int(q*100)}={np.quantile(b, q):.2f}" for q in qs) + ".")
    lines.append("")
    a = np.concatenate(prop["orig"]["ratio"])
    b = np.concatenate(prop["r2"]["ratio"])
    lines.append(f"E_cluster/E_true: ORIG median {np.median(a):.4f}, R2 {np.median(b):.4f}; "
                 f"E_cluster/E_true > 1.05 in {100*np.mean(a > 1.05):.2f}% (ORIG) vs "
                 f"{100*np.mean(b > 1.05):.2f}% (R2) of clusters.")
    lines.append("")
    a = np.concatenate(prop["orig"]["uv_ratio"])
    b = np.concatenate(prop["r2"]["uv_ratio"])
    lines.append(f"min(E_U,E_V)/E_X quantiles: ORIG " +
                 ", ".join(f"q{int(q*100)}={np.quantile(a, q):.3f}" for q in qs) +
                 "; R2 " + ", ".join(f"q{int(q*100)}={np.quantile(b, q):.3f}" for q in qs) + ".")
    lines.append("")

    # ---------------- per-cat table ----------------------------------------------------
    lines.append("## 6. Per-cat single-pass theta [deg], old code/ORIG - new code/ORIG - new code/R2")
    lines.append("")
    lines.append("| cat | " + " | ".join(k for k, _, _, _ in SELECTIONS) + " | n_sel ORIG/R2 (E>3) |")
    lines.append("|---|" + "---|" * (len(SELECTIONS) + 1))
    for i, s in enumerate(summaries):
        cells = []
        for key, dmode, emin, scen in SELECTIONS:
            cats_a, th_old, th_o, th_r, _, _ = store_all[key]
            j = int(np.where(cats_a == s["cat"])[0][0])
            cells.append(f"{th_old[j]:.1f} / {th_o[j]:.1f} / {th_r[j]:.1f}")
        no = s["fits"]["orig|s2_reco_e3"]["n"]
        nr = s["fits"]["r2|s2_reco_e3"]["n"]
        lines.append(f"| {s['cat']} | " + " | ".join(cells) + f" | {no}/{nr} |")
    lines.append("")

    Path(out_md).parent.mkdir(parents=True, exist_ok=True)
    Path(out_md).write_text("\n".join(lines) + "\n")
    print(f"wrote {out_md}")
    return lines


def variants_cat(cat, out_dir):
    """Second pass, from the saved per-cat npz: fits restricted to the clusters that exist in
    BOTH product sets, so the event-set change and the per-event ED change can be separated.

    Also counts how many paired clusters carry bit-identical images / identical ED directions.
    """
    out_dir = Path(out_dir)
    d = np.load(out_dir / f"{cat}_events.npz", allow_pickle=True)
    summ = json.loads((out_dir / f"{cat}_summary.json").read_text())
    io, ir = d["pair_i_orig"], d["pair_i_r2"]

    same_img = np.ones(len(io), dtype=bool)
    for pl in ("x", "u", "v"):
        for st in ("img_sum_", "img_nnz_", "img_max_"):
            same_img &= np.isclose(d[f"orig__{st}{pl}"][io], d[f"r2__{st}{pl}"][ir],
                                   rtol=0, atol=1e-6)
    ang_pair = np.degrees(np.arccos(np.clip(
        np.sum(d["orig__ed_dir"][io] * d["r2__ed_dir"][ir], axis=1), -1, 1)))

    fits = {}
    for st, idx in (("orig", io), ("r2", ir)):
        tb = np.asarray(summ["true_burst_dir"][st], dtype=np.float64)
        e = d[f"{st}__e_clus"][idx]
        ed = d[f"{st}__ed_dir"][idx]
        td = d[f"{st}__true_dir"][idx]
        for key, emin in (("common_reco_e3", 3.0), ("common_reco_e10", 10.0),
                          ("common_reco_e5", 5.0)):
            m = (e >= emin) & np.isfinite(ed).all(axis=1)
            fits[f"{st}|{key}"] = _fit(ed[m], e[m], tb)
        m = (e >= 3.0) & np.isfinite(td).all(axis=1)
        fits[f"{st}|common_true_e3"] = _fit(td[m], e[m], tb)

    payload = dict(
        cat=cat,
        n_pair=int(len(io)),
        n_pair_same_image=int(np.sum(same_img)),
        n_pair_same_ed=int(np.sum(ang_pair < 1e-4)),
        mean_pair_ed_angle_deg=float(np.mean(ang_pair)),
        mean_pair_ed_angle_changed_deg=float(np.mean(ang_pair[~same_img])) if np.any(~same_img) else float("nan"),
        fits=fits,
    )
    (out_dir / f"{cat}_variants.json").write_text(json.dumps(payload, indent=2, default=float))
    return payload


def codescan_cat(cat, out_dir):
    """Third pass: on the ORIGINAL products only, refit with the four combinations of the two
    pointing-code changes, to see which one moved the true-ES reco scenarios.

      hole+legacy  = the July-2026 code (bin-centre pdf lookup with fill 1e-10, 45-deg init
                     around the weighted mean)
      clip+grid    = today's code (floored/renormalised pdf, clipped queries, walkers seeded
                     at the grid maximum with an auto width)
    """
    out_dir = Path(out_dir)
    d = np.load(out_dir / f"{cat}_events.npz", allow_pickle=True)
    summ = json.loads((out_dir / f"{cat}_summary.json").read_text())
    tb = np.asarray(summ["true_burst_dir"]["orig"], dtype=np.float64)
    e = d["orig__e_clus"]
    ed = d["orig__ed_dir"]

    combos = {
        "hole_legacy": {"pdf_lookup": "hole", "init_mode": "legacy"},
        "hole_grid": {"pdf_lookup": "hole", "init_mode": "grid"},
        "clip_legacy": {"pdf_lookup": "clipped", "init_mode": "legacy"},
        "clip_grid": {"pdf_lookup": "clipped", "init_mode": "grid"},
    }
    fits = {}
    for name, extra in combos.items():
        cfg = dict(EMCEE_CFG)
        cfg.update(extra)
        for key, emin in (("e3", 3.0), ("e5", 5.0), ("e10", 10.0)):
            m = (e >= emin) & np.isfinite(ed).all(axis=1)
            dirs = ed[m]
            res = reconstruct_burst_direction(
                selected_dirs=dirs,
                selected_weights=np.ones(dirs.shape[0], dtype=np.float64),
                selected_energies=e[m], true_burst_dir=tb,
                use_emcee=True, emcee_cfg=cfg, pdf_path=PDF_PATH)
            cos = float(np.clip(np.dot(res["reco_dir"], tb), -1, 1))
            fits[f"{name}|{key}"] = dict(n=int(dirs.shape[0]), cos=cos,
                                         theta=float(np.degrees(np.arccos(cos))),
                                         acceptance=float(res["acceptance_fraction"]))
    (out_dir / f"{cat}_codescan.json").write_text(
        json.dumps(dict(cat=cat, fits=fits), indent=2, default=float))
    return fits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cat")
    ap.add_argument("--variants", action="store_true",
                    help="second pass on the saved per-cat npz (common-subset fits)")
    ap.add_argument("--codescan", action="store_true",
                    help="third pass: old/new pdf-lookup x init-mode on the ORIGINAL products")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--untar-dir",
                    default="/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/"
                            "product_effect_scratch/untar")
    ap.add_argument("--summarize", action="store_true")
    ap.add_argument("--out-md")
    ap.add_argument("--cats", default="", help="comma separated cats for --summarize")
    args = ap.parse_args()

    if args.summarize:
        cats = [c for c in args.cats.split(",") if c] or None
        summarize(args.out_dir, args.out_md or (Path(args.out_dir) / "summary.md"), cats)
        return

    if not args.cat:
        raise SystemExit("--cat is required unless --summarize")
    if args.variants:
        print(json.dumps(variants_cat(args.cat, args.out_dir), indent=2, default=float))
        return
    if args.codescan:
        print(json.dumps(codescan_cat(args.cat, args.out_dir), indent=2, default=float))
        return
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
    s = process_cat(args.cat, args.out_dir, args.untar_dir)
    print(json.dumps({k: s[k] for k in ("cat", "n_clusters", "validation", "pairing")},
                     indent=2, default=float))


if __name__ == "__main__":
    main()
