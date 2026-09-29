#!/usr/bin/env python3
"""Independent re-implementation of the detector-acceptance machinery (pole_* review).

Written from scratch for the review of the claimed `-sum_i log Z_i(n)` term.  Nothing here
imports `combo_acceptance`; the only shared code is numpy/scipy.  `pole_derive.py` compares
this implementation against the previous agent's.

Conventions used throughout (stated explicitly, see pole_dependence.md section 1):

* a direction density on the sphere is written per unit solid angle and integrates to 1;
* the pipeline's pdf tables are densities per unit cos ("cos-density convention"),
  isotropic = 0.5, integral over cos in [-1, 1] equal to 1.  The solid-angle density of a
  table row is m(c)/(2 pi);
* R(d) is a dimensionless relative acceptance with sphere average 1 (isotropic -> R == 1),
  expanded in ORTHONORMAL real spherical harmonics:  R(d) = sum_{lm} c_lm Y_lm(d),
  so c_00 = sqrt(4 pi) and R_l(n) := sum_m c_lm Y_lm(n) has R_0 == 1.

Basis note: this module puts the Condon-Shortley phase (-1)^m into P_l^m (scipy.lpmv
convention); `combo_acceptance.real_sh` leaves it out.  Individual c_lm therefore differ in
sign for odd m, but every physical quantity (R(d), R_l(n), Z_i(n)) is basis independent and
is what gets compared.
"""
from math import pi, sqrt

import numpy as np
from scipy.special import eval_legendre, lpmv

__all__ = ["real_sh", "sh_coeffs", "multipole_bands", "band_density", "legendre_moments",
           "fib_grid", "load_collect", "p_es_from_calib", "ring_average_R", "rand_rot",
           "GOLDEN"]

GOLDEN = pi * (3.0 - sqrt(5.0))


def real_sh(dirs, lmax):
    """Orthonormal real spherical harmonics, shape (N, (lmax+1)^2), index l*l+l+m.

    Y_l0 = sqrt((2l+1)/4pi) P_l(cos t)
    Y_lm = sqrt(2) K_lm P_l^m(cos t) cos(m phi)   (m > 0)
    Y_l-m = sqrt(2) K_lm P_l^m(cos t) sin(m phi)  (m > 0)
    with K_lm = sqrt((2l+1)/(4 pi) (l-m)!/(l+m)!) and P_l^m from scipy (CS phase included).
    """
    d = np.asarray(dirs, dtype=np.float64)
    d = d / np.linalg.norm(d, axis=1, keepdims=True)
    ct = np.clip(d[:, 2], -1.0, 1.0)
    phi = np.arctan2(d[:, 1], d[:, 0])
    lmax = int(lmax)
    out = np.zeros((d.shape[0], (lmax + 1) ** 2))
    for l in range(lmax + 1):
        base = l * l + l
        out[:, base] = sqrt((2 * l + 1) / (4.0 * pi)) * eval_legendre(l, ct)
        for m in range(1, l + 1):
            # K_lm computed in log space to stay safe at l = 6 and beyond
            lg = 0.5 * (np.log(2 * l + 1) - np.log(4.0 * pi)
                        + _lgam(l - m + 1) - _lgam(l + m + 1))
            k = sqrt(2.0) * np.exp(lg)
            plm = lpmv(m, l, ct)
            out[:, base + m] = k * plm * np.cos(m * phi)
            out[:, base - m] = k * plm * np.sin(m * phi)
    return out


def _lgam(x):
    from scipy.special import gammaln
    return float(gammaln(x))


def sh_coeffs(dirs, lmax, weights=None):
    """c_lm = 4 pi <Y_lm(d)>_w for a sample drawn from R/(4 pi); gives c_00 = sqrt(4 pi)."""
    y = real_sh(dirs, lmax)
    if weights is None:
        c = y.mean(axis=0)
    else:
        w = np.asarray(weights, dtype=np.float64)
        c = (y * w[:, None]).sum(axis=0) / w.sum()
    return 4.0 * pi * c


def multipole_bands(coeffs, dirs, lmax):
    """R_l(dirs) for l = 0..lmax, shape (lmax+1, N)."""
    y = real_sh(dirs, lmax)
    out = np.empty((int(lmax) + 1, y.shape[0]))
    for l in range(int(lmax) + 1):
        s = slice(l * l, (l + 1) * (l + 1))
        out[l] = y[:, s] @ np.asarray(coeffs, dtype=np.float64)[s]
    return out


def band_density(coeffs, dirs, lmax, floor=None):
    """R(dirs) = sum_{l<=lmax} R_l(dirs); optional floor for the truncated expansion."""
    r = multipole_bands(coeffs, dirs, lmax).sum(axis=0)
    if floor is None:
        return r, 0
    return np.maximum(r, float(floor)), int(np.sum(r < floor))


def legendre_moments(rows, cos_centers, lmax):
    """lambda_l = int m(c) P_l(c) dc, midpoint rule on the table bins; shape (N, lmax+1).

    The pipeline's tables satisfy sum(pdf * width) = 1, so lambda_0 = 1 exactly and the
    identity Z = sum_l lambda_l R_l reduces to Z = 1 for R == 1.
    """
    rows = np.atleast_2d(np.asarray(rows, dtype=np.float64))
    c = np.asarray(cos_centers, dtype=np.float64)
    dc = c[1] - c[0]
    lam = np.empty((rows.shape[0], int(lmax) + 1))
    for l in range(int(lmax) + 1):
        lam[:, l] = (rows * eval_legendre(l, c)[None, :]).sum(axis=1) * dc
    return lam


def ring_average_R(coeffs, n, cos_vals, lmax):
    """Azimuthal average of R over the ring at angle arccos(c) around n:
    Rbar(c; n) = sum_l R_l(n) P_l(c).  (Used as an independent cross-check.)"""
    rl = multipole_bands(coeffs, np.asarray(n, dtype=np.float64).reshape(1, 3), lmax)[:, 0]
    c = np.asarray(cos_vals, dtype=np.float64)
    return np.sum([rl[l] * eval_legendre(l, c) for l in range(int(lmax) + 1)], axis=0)


def fib_grid(n):
    """Equal-area Fibonacci lattice on the sphere (same construction as the pipeline)."""
    i = np.arange(int(n), dtype=np.float64)
    z = 1.0 - 2.0 * (i + 0.5) / int(n)
    r = np.sqrt(np.maximum(0.0, 1.0 - z * z))
    ph = i * GOLDEN
    return np.column_stack([r * np.cos(ph), r * np.sin(ph), z])


def load_collect(path, cat_lo=None, cat_hi=None):
    z = np.load(path, allow_pickle=True)
    a = np.asarray(z["table"], dtype=np.float64)
    cols = [str(c) for c in z["cols"]]
    D = {c: a[:, i] for i, c in enumerate(cols)}
    if cat_lo is not None:
        m = (D["cat"] >= cat_lo) & (D["cat"] <= cat_hi)
        D = {k: v[m] for k, v in D.items()}
    d = np.column_stack([D["dx"], D["dy"], D["dz"]])
    D["dirs"] = d / np.linalg.norm(d, axis=1, keepdims=True)
    return D


def p_es_from_calib(path, ct):
    """p_i = P(ES | CT score), monotone calibration on the slice (as stored by combo_tables)."""
    z = np.load(path, allow_pickle=True)
    s = np.asarray(z["score_center"], dtype=np.float64)
    p = np.asarray(z["p_es_mono"], dtype=np.float64)
    return np.clip(np.interp(np.clip(ct, 0.0, 1.0), s, p, left=p[0], right=p[-1]), 0.0, 1.0)


def rand_rot(seed):
    rr = np.random.RandomState(int(seed))
    m, _ = np.linalg.qr(rr.normal(size=(3, 3)))
    if np.linalg.det(m) < 0:
        m[:, 0] = -m[:, 0]
    return m


# --------------------------------------------------------------------------- pole geometry
POLES = np.array([[1.0, 0, 0], [-1.0, 0, 0], [0, 1.0, 0], [0, -1.0, 0],
                  [0, 0, 1.0], [0, 0, -1.0]])


def pole_angle(dirs):
    """Angle in degrees to the NEAREST of the six detector poles (+-x, +-y, +-z), 0-54.7356."""
    d = np.atleast_2d(np.asarray(dirs, dtype=np.float64))
    c = np.abs(d @ POLES[::2].T).max(axis=1)          # |x|, |y|, |z| -> nearest of the six
    return np.degrees(np.arccos(np.clip(c, -1.0, 1.0)))


def nearest_pole(dirs):
    d = np.atleast_2d(np.asarray(dirs, dtype=np.float64))
    return POLES[np.argmax(d @ POLES.T, axis=1)]
