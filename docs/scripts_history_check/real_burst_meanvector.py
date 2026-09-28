#!/usr/bin/env python3
"""Read-only: plain mean-vector burst direction on REAL per-cat true ES electrons.

Uses CT-training cats (400-...) only, never evaluation cats. Reproduces the
pipeline's best-case selection (true ES, true electron direction, E_cluster >=
3 MeV) but with the trivial estimator, to expose the statistical floor that the
emcee estimator should be reaching.
"""
import glob, os, sys
import numpy as np

BASE = "/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples"
SUB = "_cluster_images_tick3_ch2_min2_tot3_e3p0"
EMIN = float(os.environ.get("EMIN", "3.0"))
NSUB = int(os.environ.get("NSUB", "239"))
CATS = [f"cat{n:06d}" for n in range(int(os.environ.get("C0", "400")),
                                     int(os.environ.get("C1", "572")))]

rows = []
rng = np.random.default_rng(7)
for cat in CATS:
    pat = os.path.join(BASE, cat, cat + SUB, "X", "es_*.npz")
    fs = sorted(glob.glob(pat))
    if not fs:
        continue
    ue_l, e_l, un_l = [], [], []
    for f in fs:
        try:
            d = np.load(f, allow_pickle=True)
            m = np.asarray(d["metadata"], dtype=np.float64)
        except Exception:
            continue
        if m.ndim != 2 or m.shape[1] < 18:
            continue
        pe, pn = m[:, 7:10], m[:, 15:18]
        ne, nn = np.linalg.norm(pe, axis=1), np.linalg.norm(pn, axis=1)
        ok = (m[:, 3].astype(int) == 1) & (m[:, 2].astype(int) == 1) & (ne > 0) & (nn > 0) & (m[:, 10] >= EMIN)
        if not np.any(ok):
            continue
        ue_l.append(pe[ok] / ne[ok, None]); e_l.append(m[ok, 10]); un_l.append(pn[ok] / nn[ok, None])
    if not ue_l:
        continue
    U = np.concatenate(ue_l); E = np.concatenate(e_l); Un = np.concatenate(un_l)
    truth = Un.mean(axis=0); truth /= np.linalg.norm(truth)
    def ang(v):
        v = v / np.linalg.norm(v)
        return float(np.degrees(np.arccos(np.clip(np.dot(v, truth), -1, 1))))
    a_all = ang(U.sum(axis=0))
    n = len(U)
    if n >= NSUB:
        idx = rng.choice(n, NSUB, replace=False)
        a_sub = ang(U[idx].sum(axis=0))
    else:
        a_sub = np.nan
    rows.append((cat, n, a_all, a_sub))

if not rows:
    raise SystemExit("no cats found")

n = np.array([r[1] for r in rows])
a_all = np.array([r[2] for r in rows])
a_sub = np.array([r[3] for r in rows])
a_sub_f = a_sub[np.isfinite(a_sub)]

def cont68(a):
    return float(np.degrees(np.arccos(np.quantile(np.cos(np.radians(a)), 0.32))))

print(f"cats used: {len(rows)}  ({rows[0][0]} .. {rows[-1][0]})   E_cluster >= {EMIN} MeV")
print(f"events per burst: mean {n.mean():.1f}  min {n.min()}  max {n.max()}")
print()
print("PLAIN MEAN-VECTOR ESTIMATOR on true electron directions (best case, no MCMC):")
print(f"  all events/burst (<n>={n.mean():.0f}): 68% containment = {cont68(a_all):.3f} deg | "
      f"median {np.median(a_all):.3f} | mean {a_all.mean():.3f} | max {a_all.max():.3f}")
if a_sub_f.size:
    print(f"  subsampled to N={NSUB}:            68% containment = {cont68(a_sub_f):.3f} deg | "
          f"median {np.median(a_sub_f):.3f} | mean {a_sub_f.mean():.3f} | max {a_sub_f.max():.3f}")
print()
print("first 12 cats (cat, n, angle_all, angle_subsampled):")
for r in rows[:12]:
    print(f"  {r[0]}  n={r[1]:4d}  all={r[2]:6.3f} deg  sub={r[3]:6.3f} deg")
