#!/usr/bin/env python3
"""Closure test: re-run ED v63 and CT v80 with this study's own inference code on the
REFERENCE (e3p0 _matchfix) ES events of a few cats and compare with the values stored in
the R4_v63_ownpdf_matchfix dev-pipeline products. If they agree, the directions and CT
scores computed for the recovered events are on the same footing as the deployed ones."""
import argparse, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from induction_threshold_infer import ed_predict, ct_predict, ED_MODEL, CT_MODEL, BASE, COND  # noqa


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--cats", default="623-625")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    import tensorflow as tf
    ed = tf.keras.models.load_model(ED_MODEL, compile=False)
    ct = tf.keras.models.load_model(CT_MODEL, compile=False)
    P = np.load(a.scan, allow_pickle=True)["payload"][0]
    R = np.load(a.ref, allow_pickle=True)["payload"][0]
    lo, hi = (int(x) for x in a.cats.split("-"))
    out = {}
    for cat in range(lo, hi + 1):
        rows = [r for r in P["matchfix"]["rows"] if r["cat"] == cat]
        iu, iv, ix, ctimg = [], [], [], []
        cache = {}
        for r in rows:
            xf = r["xfile"]
            if xf not in cache:
                uf = xf.replace("/X/", "/U/").replace("planeX", "planeU")
                vf = xf.replace("/X/", "/V/").replace("planeX", "planeV")
                volf = (f"{BASE}/cat{cat:06d}/cat{cat:06d}_volume_images_{COND}_matchfix/X/"
                        + os.path.basename(xf).replace("_matched", ""))
                dvol = np.load(volf, allow_pickle=True)
                e2p = {}
                for pos, m in enumerate(dvol["metadata"]):
                    e2p.setdefault(int(m["event"]), pos)
                cache[xf] = (np.load(xf, allow_pickle=True), np.load(uf, allow_pickle=True),
                             np.load(vf, allow_pickle=True), dvol, e2p)
            dx, du, dv, dvol, e2p = cache[xf]
            ix.append(dx["images"][r["idx_x"]]); iu.append(du["images"][r["idx_u"]])
            iv.append(dv["images"][r["idx_v"]])
            ctimg.append(np.asarray(dvol["images"][e2p[r["event"]]], dtype=np.float32))
        mine = ed_predict(ed, np.asarray(iu), np.asarray(iv), np.asarray(ix), tf)
        theirs = R[cat]["es_dirs"]
        cos = np.sum(mine * theirs, axis=1)
        mp = ct_predict(ct, ctimg); tp = R[cat]["es_proba"]
        out[cat] = dict(n=len(cos), ed_min_cos=float(cos.min()), ed_mean_cos=float(cos.mean()),
                        ed_frac_gt_09999=float((cos > 0.9999).mean()),
                        ct_max_abs_d=float(np.abs(mp - tp).max()),
                        ct_agree_08=float(((mp >= 0.8) == (tp >= 0.8)).mean()))
        print(f"cat{cat:06d}", out[cat], flush=True)
    np.savez_compressed(a.out, payload=np.array([out], dtype=object))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
