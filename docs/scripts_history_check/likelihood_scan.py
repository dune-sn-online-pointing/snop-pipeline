#!/usr/bin/env python3
"""Read-only: scan the pipeline's PDF log-likelihood vs angular offset from truth,
for the best-case inputs (true ES, TRUE electron directions, E>=3 MeV).

Imports nothing from the pipeline; it re-implements load_pdf_interpolator and
_pdf_likelihood exactly as python/ana/burst_direction.py does, so the numbers
are the ones the campaign actually optimised.
"""
import glob, os
import numpy as np
from scipy.interpolate import RegularGridInterpolator

BASE = "/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples"
SUB = "_cluster_images_tick3_ch2_min2_tot3_e3p0"
PDF = "/afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/data/cosine_energy_pdf.npz"
EMIN = 3.0

d = np.load(PDF, allow_pickle=True)
pdf_2d = d["pdf_2d"]
ecen = d["energy_bins"].mean(axis=1)
ccen = d["cosine_bin_centers"]
interp = RegularGridInterpolator((ecen, ccen), pdf_2d, method="linear",
                                 bounds_error=False, fill_value=1e-10)
interp_clip = RegularGridInterpolator((ecen, ccen), pdf_2d, method="linear",
                                      bounds_error=False, fill_value=None)


def load_cat(cat):
    ue, en, un = [], [], []
    for f in sorted(glob.glob(os.path.join(BASE, cat, cat + SUB, "X", "es_*.npz"))):
        try:
            m = np.asarray(np.load(f, allow_pickle=True)["metadata"], float)
        except Exception:
            continue
        if m.ndim != 2 or m.shape[1] < 18:
            continue
        pe, pn = m[:, 7:10], m[:, 15:18]
        ne, nn = np.linalg.norm(pe, axis=1), np.linalg.norm(pn, axis=1)
        ok = (m[:, 3].astype(int) == 1) & (m[:, 2].astype(int) == 1) & (ne > 0) & (nn > 0) & (m[:, 10] >= EMIN)
        if np.any(ok):
            ue.append(pe[ok] / ne[ok, None]); en.append(m[ok, 10]); un.append(pn[ok] / nn[ok, None])
    U = np.concatenate(ue); E = np.concatenate(en); Un = np.concatenate(un)
    t = Un.mean(axis=0); t /= np.linalg.norm(t)
    return U, E, t


def ll(U, E, direction, itp, clip=False):
    c = np.clip(U @ direction, -1.0, 1.0)
    if clip:
        c = np.clip(c, ccen[0], ccen[-1])
    v = np.maximum(itp(np.column_stack([E, c])), 1e-10)
    return float(np.sum(np.log(v)))


def perp(t):
    a = np.array([1.0, 0.0, 0.0])
    if abs(np.dot(a, t)) > 0.9:
        a = np.array([0.0, 1.0, 0.0])
    e1 = np.cross(t, a); e1 /= np.linalg.norm(e1)
    e2 = np.cross(t, e1)
    return e1, e2


print(f"PDF: {PDF}")
print(f"cosine grid covers [{ccen[0]}, {ccen[-1]}]  ->  any |cos| > {ccen[-1]} is OUT OF BOUNDS")
print(f"fill_value used by the pipeline for out-of-bounds points: 1e-10  (log = {np.log(1e-10):.2f})")
print()

for cat in ["cat000400", "cat000401", "cat000402", "cat000403"]:
    U, E, t = load_cat(cat)
    e1, e2 = perp(t)
    frac_hole = np.mean(np.abs(U @ t) > ccen[-1])
    mv = U.sum(axis=0); mv /= np.linalg.norm(mv)
    print(f"--- {cat}: n={len(U)}  <cos to truth>={np.mean(U@t):.4f}  "
          f"frac(|cos|>0.99) at truth = {frac_hole:.3f}  mean-vector error = "
          f"{np.degrees(np.arccos(np.clip(np.dot(mv,t),-1,1))):.3f} deg")
    offs = np.arange(0, 26, 1.0)
    best_a, best_v = None, -1e30
    best_ac, best_vc = None, -1e30
    rows = []
    for a in offs:
        ra = np.radians(a)
        vals, valsc = [], []
        for b in np.linspace(0, 2 * np.pi, 24, endpoint=False):
            dvec = np.cos(ra) * t + np.sin(ra) * (np.cos(b) * e1 + np.sin(b) * e2)
            vals.append(ll(U, E, dvec, interp))
            valsc.append(ll(U, E, dvec, interp_clip, clip=True))
        v, vc = float(np.mean(vals)), float(np.mean(valsc))
        rows.append((a, v, vc))
        if v > best_v: best_v, best_a = v, a
        if vc > best_vc: best_vc, best_ac = vc, a
    print(f"    offset:  " + "".join(f"{r[0]:8.0f}" for r in rows[:14]))
    print(f"    logL  :  " + "".join(f"{r[1]-rows[0][1]:8.0f}" for r in rows[:14]))
    print(f"    logL* :  " + "".join(f"{r[2]-rows[0][2]:8.0f}" for r in rows[:14]))
    print(f"    -> as-shipped likelihood peaks at offset {best_a:.0f} deg from truth; "
          f"with the out-of-bounds hole removed it peaks at {best_ac:.0f} deg")
    print()
print("logL  = pipeline's likelihood (fill_value=1e-10 outside the cosine grid)")
print("logL* = same PDF but cos clipped into the grid (no out-of-bounds hole)")
print("Both are shown relative to the value at zero offset (i.e. at the true burst direction).")
