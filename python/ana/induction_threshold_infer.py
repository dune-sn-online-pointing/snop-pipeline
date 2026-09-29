#!/usr/bin/env python3
"""Run CT v80 and ED v63 on the events RECOVERED by a lower induction energy_cut.

For every cat and a given clustering variant (indcut25 / indcut20) the script takes the
events that enter the pipeline only with the lower induction cut (3-plane main-track
match present in the variant products, absent in the reference e3p0 _matchfix products),
and produces for each of them
  * the ED v63 reconstructed electron direction, from the variant's NEW three-plane
    cluster images (X unchanged, U/V newly accepted),
  * the CT v80 P(ES) score, from the EXISTING reference X volume image of the same
    event (volume images are built for every X main-track cluster, matched or not, and
    the X accepted-cluster set is unchanged because the collection cut stays at 3.0 MeV).

It also checks, on the events common to reference and variant, that the X/U/V images are
byte-identical, i.e. that a lower induction cut only ADDS events.
"""
import argparse, json, os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))

NN = "/eos/project-e/ep-nu/evilla/sn-online-pointing/neural-networks"
ED_MODEL = f"{NN}/electron_direction/three_plane_v63_matchfix_ft58_20260921_132520/best_model.keras"
CT_MODEL = f"{NN}/channel_tagging/ct_volume_v80_20260706_224935/best_model.keras"
BASE = "/eos/user/e/evilla/dune/sn-tps/mixture_dev_samples"
COND = "tick3_ch2_min2_tot3_e3p0"


def norm_rows(a):
    a = np.asarray(a, dtype=np.float64)
    n = np.linalg.norm(a, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return a / n


def ed_predict(model, imgs_u, imgs_v, imgs_x, tf, batch_size=64):
    sh = model.inputs[0].shape
    eh, ew = int(sh[1]), int(sh[2])
    ec = int(sh[3]) if len(sh) > 3 else 1

    def prep(a):
        a = np.asarray(a, dtype=np.float32)
        if a.ndim == 3:
            a = a[..., np.newaxis]
        if a.shape[1] != eh or a.shape[2] != ew:
            a = tf.image.resize(a, (eh, ew), method="bilinear").numpy()
        if a.shape[-1] != ec:
            a = a[..., :1] if ec == 1 else np.repeat(a[..., :1], ec, axis=-1)
        return a
    p = model.predict([prep(imgs_u), prep(imgs_v), prep(imgs_x)],
                      batch_size=batch_size, verbose=0)
    p = np.asarray(p)
    if p.ndim == 3 and p.shape[1] == 1:
        p = p[:, 0, :]
    return norm_rows(norm_rows(p).astype(np.float32))


def ct_predict(model, images, batch_size=32):
    """CT v80: log1p preprocessing (results.json preprocessing.image == 'log1p'),
    label convention ES=0 / CC=1 -> class-0 output is P(ES)."""
    out = np.zeros(len(images), dtype=np.float32)
    for i0 in range(0, len(images), 64):
        chunk = images[i0:i0 + 64]
        arr = np.asarray([np.asarray(c, dtype=np.float32) for c in chunk], dtype=np.float32)
        arr = np.log1p(arr)
        if arr.ndim == 3:
            arr = arr[..., np.newaxis]
        pr = np.asarray(model.predict(arr, batch_size=batch_size, verbose=0))
        if pr.ndim == 2 and pr.shape[1] >= 2:
            pr = pr[:, 0]
        elif pr.ndim == 2 and pr.shape[1] == 1:
            pr = 1.0 - pr[:, 0]
        else:
            pr = pr.ravel()
        out[i0:i0 + 64] = pr
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", required=True)
    ap.add_argument("--suffix", required=True, choices=["indcut25", "indcut20"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--cats", default="623-672")
    ap.add_argument("--check-common", type=int, default=3,
                    help="verify image identity of common events on the first N cats")
    a = ap.parse_args()

    import tensorflow as tf
    ed = tf.keras.models.load_model(ED_MODEL, compile=False)
    ct = tf.keras.models.load_model(CT_MODEL, compile=False)
    print("ED inputs", [tuple(i.shape) for i in ed.inputs])
    print("CT input", tuple(ct.inputs[0].shape))

    P = np.load(a.scan, allow_pickle=True)["payload"][0]
    ref = {}
    var = {}
    for r in P["matchfix"]["rows"]:
        ref.setdefault(r["cat"], {})[(r["file_idx"], r["event"])] = r
    for r in P[a.suffix]["rows"]:
        var.setdefault(r["cat"], {})[(r["file_idx"], r["event"])] = r

    lo, hi = (int(x) for x in a.cats.split("-"))
    out = {}
    checks = []
    for ci, cat in enumerate(range(lo, hi + 1)):
        rec = [var[cat][k] for k in sorted(var[cat]) if k not in ref[cat]]
        com = [k for k in sorted(var[cat]) if k in ref[cat]]
        if not rec:
            out[cat] = None
            continue
        # group by X file to load each npz once
        by_file = {}
        for r in rec:
            by_file.setdefault(r["xfile"], []).append(r)
        iu_, iv_, ix_, meta_, ctimg_, rows_ = [], [], [], [], [], []
        for xf, rr in sorted(by_file.items()):
            uf = xf.replace("/X/", "/U/").replace("planeX", "planeU")
            vf = xf.replace("/X/", "/V/").replace("planeX", "planeV")
            dx, du, dv = (np.load(p, allow_pickle=True) for p in (xf, uf, vf))
            # reference volume image of the same input file, keyed by event
            volf = (f"{BASE}/cat{cat:06d}/cat{cat:06d}_volume_images_{COND}_matchfix/X/"
                    + os.path.basename(xf).replace("_matched", ""))
            dvol = np.load(volf, allow_pickle=True)
            ev2pos = {}
            for pos, m in enumerate(dvol["metadata"]):
                ev2pos.setdefault(int(m["event"]), pos)
            for r in rr:
                ix_.append(dx["images"][r["idx_x"]])
                iu_.append(du["images"][r["idx_u"]])
                iv_.append(dv["images"][r["idx_v"]])
                meta_.append(dx["metadata"][r["idx_x"]])
                pos = ev2pos.get(r["event"])
                ctimg_.append(np.asarray(dvol["images"][pos], dtype=np.float32)
                              if pos is not None else None)
                rows_.append((cat, r["file_idx"], r["event"], r["match_id"]))
        meta_ = np.asarray(meta_, dtype=np.float32)
        dirs = ed_predict(ed, np.asarray(iu_), np.asarray(iv_), np.asarray(ix_), tf)
        ok = np.array([c is not None for c in ctimg_])
        proba = np.zeros(len(ctimg_), dtype=np.float32)
        if ok.any():
            proba[ok] = ct_predict(ct, [c for c in ctimg_ if c is not None])
        out[cat] = dict(md=meta_, dirs=dirs, proba=proba, ct_ok=ok,
                        keys=np.array(rows_, dtype=np.int64))
        print(f"cat{cat:06d}: recovered {len(rec)}  ct_ok {int(ok.sum())}", flush=True)

        # --- consistency check: common events must have identical images ----------
        if ci < a.check_common:
            bad = 0
            for k in com[:40]:
                rv, rf = var[cat][k], ref[cat][k]
                for pl, key in (("X", "idx_x"), ("U", "idx_u"), ("V", "idx_v")):
                    pv = rv["xfile"].replace("/X/", f"/{pl}/").replace("planeX", f"plane{pl}")
                    pf = rf["xfile"].replace("/X/", f"/{pl}/").replace("planeX", f"plane{pl}")
                    av = np.load(pv, allow_pickle=True)["images"][rv[key]]
                    af = np.load(pf, allow_pickle=True)["images"][rf[key]]
                    if not np.array_equal(av, af):
                        bad += 1
            checks.append((cat, len(com[:40]), bad))
            print(f"   image-identity check on {len(com[:40])} common events: "
                  f"{bad} mismatching planes", flush=True)

    np.savez_compressed(a.out, payload=np.array([out], dtype=object),
                        checks=np.array(checks, dtype=object))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
