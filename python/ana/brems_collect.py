#!/usr/bin/env python3
"""Collect per-event diagnostics for the bremsstrahlung / purity-conditioning study.

READ-ONLY on every production product.  For each cat it joins three sources, all keyed on
the true main-track momentum triple (float32, 6 decimals), which is unique per volume:

  1. r3 campaign slim tar, scenario_3 -> per-volume metadata (N,18), v63 reco directions,
     CT v80 scores.  This is exactly what `select_electrons_from_run` reads.
  2. the regenerated per-CLUSTER ES images tar (`*_r3_es.tar`, X plane) -> for every true-ES
     event, the number and reco energy of its secondary MARLEY clusters (the brems proxy).
  3. the per-cat volume-image metadata dicts (`*_volume_images_*`/X) -> n_marley_clusters,
     n_clusters_in_volume and the MARLEY-companion distances, available for ES *and* CC.

Output: one npz per cat range with a flat per-event table (all volumes with a valid reco
direction and reco cluster energy >= 4 MeV).  Merged and turned into tables by
`brems_report.py`.

Usage:
  python3 python/ana/brems_collect.py --cats 673-900 --out <dir>/collect_673_900.npz
"""
import argparse
import glob
import io
import sys
import tarfile
import time
from pathlib import Path

import numpy as np

CAMPAIGN = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-campaign/v63_matchfix_1000")
SAMPLES = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples")
STEM = "cluster_images_tick3_ch2_min2_tot3_e3p0"
E_MIN_KEEP = 4.0

COLS = ["cat", "is_es", "is_marley", "e_reco", "e_true", "e_nu", "ct", "cos_burst",
        "cos_true_burst", "dx", "dy", "dz", "n_sec_es", "e_sec_es", "n_marley_vol",
        "n_clus_vol", "n_nonmarley_vol", "d_avg_marley", "d_max_marley",
        "bx", "by", "bz"]


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


def mkey(arr):
    """(N,3) true momentum -> list of hashable float32 keys."""
    a = np.round(np.asarray(arr, dtype=np.float32), 6)
    return [tuple(r) for r in a]


def read_slim(tar_path, scenario="scenario_3_full_pipeline"):
    with tarfile.open(tar_path) as tf:
        names = tf.getnames()
        vol = [n for n in names if n.startswith(scenario + "/")
               and n.endswith("volume_images/volumes.npz")]
        if not vol:
            return None
        pre = vol[0].rsplit("/volume_images/", 1)[0]
        meta = np.asarray(np.load(io.BytesIO(tf.extractfile(vol[0]).read()),
                                  allow_pickle=True)["metadata"], dtype=np.float64)
        out = {"meta": meta}
        for key, fn in (("reco", "reco_directions.npz"), ("pred", "channel_predictions.npz")):
            n = f"{pre}/predictions/{fn}"
            if n not in names:
                return None
            z = np.load(io.BytesIO(tf.extractfile(n).read()), allow_pickle=True)
            out[key] = {k: z[k] for k in z.files}
    return out


def read_es_clusters(cat):
    """key -> (n secondary MARLEY clusters, summed reco energy of them)."""
    tar = SAMPLES / cat / f"{cat}_{STEM}_r3_es.tar"
    if not tar.exists():
        return {}
    rows = []
    with tarfile.open(tar) as tf:
        for n in tf.getnames():
            if n.startswith("X/") and n.endswith(".npz"):
                z = np.load(io.BytesIO(tf.extractfile(n).read()), allow_pickle=True)
                rows.append(np.asarray(z["metadata"], dtype=np.float64))
    if not rows:
        return {}
    C = np.vstack(rows)
    C = C[(C[:, 1] == 1) & (C[:, 3] == 1)]          # MARLEY, ES
    keys = mkey(C[:, 7:10])
    agg = {}
    for i, k in enumerate(keys):
        n_sec, e_sec, has_main = agg.get(k, (0, 0.0, False))
        if C[i, 2] == 1:
            has_main = True
        else:
            n_sec += 1
            e_sec += C[i, 10]
        agg[k] = (n_sec, e_sec, has_main)
    return {k: (v[0], v[1]) for k, v in agg.items() if v[2]}


def read_volume_dicts(cat):
    """key -> (n_marley, n_clusters, n_non_marley, d_avg, d_max) from the X-plane volumes."""
    d = SAMPLES / cat / f"{cat}_volume_images_tick3_ch2_min2_tot3_e3p0" / "X"
    out = {}
    for p in sorted(glob.glob(str(d / "*.npz"))):
        try:
            z = np.load(p, allow_pickle=True)
            md = z["metadata"]
        except Exception:
            continue
        for m in md:
            k = (np.round(np.float32(m["main_track_momentum_x"]), 6),
                 np.round(np.float32(m["main_track_momentum_y"]), 6),
                 np.round(np.float32(m["main_track_momentum_z"]), 6))
            out[k] = (m.get("n_marley_clusters", -1), m.get("n_clusters_in_volume", -1),
                      m.get("n_non_marley_clusters", -1),
                      m.get("avg_marley_cluster_distance_cm", -1.0),
                      m.get("max_marley_cluster_distance_cm", -1.0))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cats", required=True, help="ranges, e.g. 673-900 or 2-399,901-1224")
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-volume-dicts", action="store_true")
    ap.add_argument("--no-es-clusters", action="store_true")
    args = ap.parse_args()

    ranges = [tuple(int(x) for x in r.split("-")) for r in args.cats.split(",")]
    for lo, hi in ranges:
        assert not (hi >= 400 and lo <= 621), f"{lo}-{hi} touches the off-limits cats 400-621"

    blocks, cats_done, t0 = [], [], time.time()
    for lo, hi in ranges:
        for n in range(lo, hi + 1):
            cat = f"cat{n:06d}"
            tar = CAMPAIGN / cat / f"{cat}_scenarios_slim.tar"
            if not tar.exists():
                continue
            try:
                s = read_slim(tar)
            except Exception as e:                                       # noqa: BLE001
                print(f"  {cat}: slim read failed {e!r}", flush=True)
                continue
            if s is None:
                continue
            m = s["meta"]
            bd = burst_dir(m)
            if bd is None:
                continue
            d = _norm(np.asarray(s["reco"]["reco_dirs"], dtype=np.float64))
            has = np.asarray(s["reco"]["has_reco"]).astype(bool)
            ok = has & np.isfinite(d).all(axis=1) & (np.linalg.norm(
                np.asarray(s["reco"]["reco_dirs"], dtype=np.float64), axis=1) > 0)
            ok &= m[:, 10] >= E_MIN_KEEP
            if not ok.any():
                continue
            idx = np.where(ok)[0]
            keys = mkey(m[:, 7:10])
            esc = {} if args.no_es_clusters else read_es_clusters(cat)
            vdd = {} if args.no_volume_dicts else read_volume_dicts(cat)

            nsel = len(idx)
            T = np.full((nsel, len(COLS)), np.nan, dtype=np.float32)
            te = _norm(np.where(np.linalg.norm(m[:, 7:10], axis=1, keepdims=True) > 0,
                                m[:, 7:10], np.array([[1.0, 0.0, 0.0]])))
            T[:, 0] = n
            T[:, 1] = m[idx, 3]
            T[:, 2] = m[idx, 1]
            T[:, 3] = m[idx, 10]
            T[:, 4] = np.linalg.norm(m[idx, 7:10], axis=1) * 1000.0
            T[:, 5] = m[idx, 14]
            T[:, 6] = np.asarray(s["pred"]["y_pred_proba"], dtype=np.float64)[idx]
            T[:, 7] = np.clip(d[idx] @ bd, -1.0, 1.0)
            T[:, 8] = np.clip(te[idx] @ bd, -1.0, 1.0)
            T[:, 9:12] = d[idx]
            for j, i in enumerate(idx):
                k = keys[i]
                if k in esc:
                    T[j, 12], T[j, 13] = esc[k]
                if k in vdd:
                    T[j, 14:19] = vdd[k]
            T[:, 19:22] = bd
            blocks.append(T)
            cats_done.append(n)
            if len(cats_done) % 20 == 0:
                print(f"  {len(cats_done)} cats, {time.time()-t0:.0f}s", flush=True)

    A = np.vstack(blocks) if blocks else np.zeros((0, len(COLS)), np.float32)
    np.savez_compressed(args.out, table=A, cols=np.asarray(COLS),
                        cats=np.asarray(cats_done, dtype=np.int32))
    print(f"wrote {args.out}: {A.shape[0]} events, {len(cats_done)} cats, "
          f"{time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
