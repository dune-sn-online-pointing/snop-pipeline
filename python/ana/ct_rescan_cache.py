#!/usr/bin/env python3
"""Per-event cache of the r3 campaign's scenario-3 rows, for the CT-threshold re-scan.

One pass over `<cat>/<cat>_scenarios_slim.tar` (scenario_3_full_pipeline, which holds ALL
loaded clusters with their CT v80 score and v63 reco direction) storing, for every cluster
with a VALID reco direction -- exactly the rows `select_electrons_from_run` can ever
select:

    cos_burst  cos(v63 reco electron dir, TRUE BURST dir)   <- what the likelihood queries
    energy     reco cluster energy, metadata col 10          <- what the lookup is passed
    proba      CT v80 P(ES)
    is_es      truth flag (metadata col 3)
    dirs       the reco direction itself (detector frame; for the CC direction map)
    cat        cat number

Everything downstream (purity vs threshold, per-threshold burst-axis ES tables, mixtures,
score calibration, CC map) is then computed in memory from the cache, so an arbitrary
selection rule costs nothing.  Tables must only ever be built from the TRAINING SLICE
(cats 673-900); the cache itself is just data and can also be made for the dev cats.

Usage:
  python3 python/ana/ct_rescan_cache.py --cat-min 673 --cat-max 900 --out <cache.npz>
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

CAMPAIGN = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-campaign/v63_matchfix_1000")
SCENARIO = "scenario_3_full_pipeline"


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


def read_cat(tar_path, scenario=SCENARIO):
    with tarfile.open(tar_path) as tf:
        names = tf.getnames()
        vol = [n for n in names if n.startswith(scenario + "/")
               and n.endswith("volume_images/volumes.npz")]
        if not vol:
            return None
        pre = vol[0].rsplit("/volume_images/", 1)[0]
        meta = np.asarray(np.load(io.BytesIO(tf.extractfile(vol[0]).read()),
                                  allow_pickle=True)["metadata"], dtype=np.float64)
        rn, pn = f"{pre}/predictions/reco_directions.npz", f"{pre}/predictions/channel_predictions.npz"
        if rn not in names or pn not in names:
            return None
        rec = np.load(io.BytesIO(tf.extractfile(rn).read()), allow_pickle=True)
        prd = np.load(io.BytesIO(tf.extractfile(pn).read()), allow_pickle=True)
        return (meta, np.asarray(rec["reco_dirs"], dtype=np.float64),
                np.asarray(rec["has_reco"]).astype(bool),
                np.asarray(prd["y_pred_proba"], dtype=np.float64))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cat-min", type=int, required=True)
    ap.add_argument("--cat-max", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--campaign", default=str(CAMPAIGN))
    args = ap.parse_args()
    assert not (args.cat_max >= 400 and args.cat_min <= 621), "cats 400-621 are off limits"

    camp = Path(args.campaign)
    cols = {k: [] for k in ("cos", "e", "p", "es", "cat")}
    dirs, per_cat, t0 = [], {}, time.time()
    for n in range(args.cat_min, args.cat_max + 1):
        cat = f"cat{n:06d}"
        tar = camp / cat / f"{cat}_scenarios_slim.tar"
        if not tar.exists():
            continue
        try:
            got = read_cat(tar)
        except Exception as e:  # noqa: BLE001
            print(f"  {cat}: {e!r}", flush=True)
            continue
        if got is None:
            continue
        meta, d, has, proba = got
        bd = burst_dir(meta)
        if bd is None or proba.shape[0] != meta.shape[0]:
            continue
        d = _norm(d)
        ok = has & np.isfinite(d).all(axis=1) & (np.linalg.norm(d, axis=1) > 0)
        if not ok.any():
            continue
        cols["cos"].append(np.clip(d[ok] @ bd, -1.0, 1.0))
        cols["e"].append(meta[ok, 10])
        cols["p"].append(proba[ok])
        cols["es"].append(meta[ok, 3].astype(int) == 1)
        cols["cat"].append(np.full(int(ok.sum()), n, dtype=np.int32))
        dirs.append(d[ok])
        per_cat[cat] = dict(n_loaded=int(meta.shape[0]), n_valid=int(ok.sum()),
                            n_true_es=int(((meta[:, 3].astype(int) == 1) & ok).sum()))
        if len(per_cat) % 50 == 0:
            print(f"  {len(per_cat)} cats, {time.time()-t0:.0f}s", flush=True)

    if not per_cat:
        raise SystemExit("no cats read")
    out = dict(cos_burst=np.concatenate(cols["cos"]).astype(np.float32),
               energy=np.concatenate(cols["e"]).astype(np.float32),
               proba=np.concatenate(cols["p"]).astype(np.float32),
               is_es=np.concatenate(cols["es"]),
               cat=np.concatenate(cols["cat"]),
               dirs=np.concatenate(dirs).astype(np.float32),
               cats=np.asarray(sorted(per_cat)),
               n_cats=np.int64(len(per_cat)),
               cat_range=np.asarray([args.cat_min, args.cat_max]),
               campaign=np.asarray(str(camp)), scenario=np.asarray(SCENARIO),
               per_cat=np.asarray(json.dumps(per_cat)))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.out, **out)
    nv = out["cos_burst"].shape[0]
    print(f"\n{len(per_cat)} cats, {nv} valid clusters ({nv/len(per_cat):.0f}/burst), "
          f"{out['is_es'].mean()*100:.2f}% true ES, {time.time()-t0:.0f}s")
    print(f"proba: min {out['proba'].min():.4f} max {out['proba'].max():.4f} "
          f"p99.9 {np.quantile(out['proba'], 0.999):.4f}")
    print(f"wrote {args.out} ({Path(args.out).stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
