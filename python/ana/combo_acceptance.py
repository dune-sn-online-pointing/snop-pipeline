#!/usr/bin/env python3
"""Detector-frame acceptance machinery shared by the `combo_*` study.

Two independent studies found the same physics from opposite sides:

  * `ct_rescan_*` (r3 re-scan): the CC component of the mixture must be the measured
    DETECTOR-FRAME density of CC reco directions q(d), not a flat 1/2.  It is constant
    in the trial direction n, so it only re-weights events.
  * `brems_*` (purity study, sections 8-9): the ES component needs the acceptance
    NORMALISATION p_i(d|n) = m_i(d.n) R(d) / Z_i(n), with
    Z_i(n) = sum_l <P_l(cos)>_i R_l(n) and R_l(n) = (2l+1) <P_l(d.n)>_{d~R}.

This module provides the one representation that serves both: the real spherical-harmonic
coefficients c_lm of a measured reco-direction density R(d) up to l = lmax (49 numbers for
lmax = 6), from which

    R_l(n) = sum_m c_lm Y_lm(n)          (the l-th multipole band, == (2l+1) <P_l(d.n)>)
    R(n)   = sum_{l<=lmax} R_l(n)        (the band-limited density itself)

so the SAME 49 numbers give the per-event factor R(d_i) and the trial-direction
normalisation Z_i(n).  `check_addition_theorem` gates the two against each other.

Conventions
-----------
* R is a RELATIVE density: <R>_sphere = 1 (isotropic -> R == 1).
* The pipeline's pdf tables use the cos-density convention (uniform = 0.5,
  integral over cos in [-1,1] equal to 1).  A detector-frame density in that
  convention is q(d) = 0.5 * R(d), matching `build_cc_direction_map.py`.
* Sample directions d_j are drawn from R/(4 pi), hence c_lm = 4 pi <Y_lm(d)>.
"""
from math import factorial, pi, sqrt

import numpy as np

__all__ = ["real_sh", "sh_coeffs_from_dirs", "multipole_bands", "band_limited_density",
           "legendre_moments_of_rows", "check_addition_theorem", "vmf_density_map",
           "rotate_dirs"]


def real_sh(dirs, lmax):
    """Orthonormal real spherical harmonics Y_lm evaluated at `dirs`.

    Returns (N, (lmax+1)**2).  Index of (l, m) is l*l + l + m, so m = 0 sits at
    l*l + l, the cos(m phi) terms at +m and the sin(m phi) terms at -m.
    Normalisation is such that sum_m Y_lm(d) Y_lm(n) = (2l+1)/(4 pi) P_l(d.n).
    """
    d = np.asarray(dirs, dtype=np.float64)
    d = d / np.linalg.norm(d, axis=1, keepdims=True)
    ct = np.clip(d[:, 2], -1.0, 1.0)
    st = np.sqrt(np.maximum(0.0, 1.0 - ct * ct))
    phi = np.arctan2(d[:, 1], d[:, 0])
    n = d.shape[0]
    lmax = int(lmax)
    # associated Legendre P_l^m(ct) WITHOUT the Condon-Shortley phase
    P = {(0, 0): np.ones(n)}
    for m in range(1, lmax + 1):
        P[(m, m)] = P[(m - 1, m - 1)] * (2 * m - 1) * st
    for m in range(0, lmax):
        P[(m + 1, m)] = ct * (2 * m + 1) * P[(m, m)]
    for m in range(0, lmax + 1):
        for l in range(m + 2, lmax + 1):
            P[(l, m)] = ((2 * l - 1) * ct * P[(l - 1, m)] - (l + m - 1) * P[(l - 2, m)]) / (l - m)
    out = np.zeros((n, (lmax + 1) ** 2))
    cosm = [np.cos(m * phi) for m in range(lmax + 1)]
    sinm = [np.sin(m * phi) for m in range(lmax + 1)]
    for l in range(lmax + 1):
        base = l * l + l
        out[:, base] = sqrt((2 * l + 1) / (4.0 * pi)) * P[(l, 0)]
        for m in range(1, l + 1):
            k = sqrt((2 * l + 1) / (4.0 * pi) * factorial(l - m) / factorial(l + m)) * sqrt(2.0)
            out[:, base + m] = k * P[(l, m)] * cosm[m]
            out[:, base - m] = k * P[(l, m)] * sinm[m]
    return out


def sh_coeffs_from_dirs(dirs, lmax, chunk=200000):
    """c_lm = 4 pi <Y_lm(d)> of an empirical reco-direction sample; c_00*Y_00 == 1."""
    dirs = np.asarray(dirs, dtype=np.float64)
    acc = np.zeros(((lmax + 1) ** 2,))
    n = 0
    for s in range(0, dirs.shape[0], chunk):
        y = real_sh(dirs[s:s + chunk], lmax)
        acc += y.sum(axis=0)
        n += y.shape[0]
    return 4.0 * pi * acc / max(n, 1)


def multipole_bands(coeffs, dirs, lmax):
    """R_l(dirs) for l = 0..lmax, shape (lmax+1, N)."""
    y = real_sh(dirs, lmax)
    out = np.empty((lmax + 1, dirs.shape[0]))
    for l in range(lmax + 1):
        sl = slice(l * l, (l + 1) * (l + 1))
        out[l] = y[:, sl] @ coeffs[sl]
    return out


def band_limited_density(coeffs, dirs, lmax, floor=0.05):
    """R(dirs) = sum_{l<=lmax} R_l(dirs), floored (a truncated expansion can dip below 0)."""
    r = multipole_bands(coeffs, dirs, lmax).sum(axis=0)
    n_floored = int(np.sum(r < floor))
    return np.maximum(r, floor), n_floored


def legendre_moments_of_rows(rows, cos_centers, lmax):
    """lambda_l = integral row(c) P_l(c) dc for each row; shape (N, lmax+1).

    `rows` are pdf tables in the cos-density convention (integral over c = 1), so
    lambda_0 = 1 and Z_i(n) = sum_l lambda_l^(i) R_l(n) reduces to 1 for R == 1.
    """
    rows = np.asarray(rows, dtype=np.float64)
    c = np.asarray(cos_centers, dtype=np.float64)
    dc = c[1] - c[0]
    lam = np.empty((rows.shape[0], lmax + 1))
    pm1 = np.ones_like(c)
    pl = c.copy()
    lam[:, 0] = (rows * pm1[None, :]).sum(axis=1) * dc
    if lmax >= 1:
        lam[:, 1] = (rows * pl[None, :]).sum(axis=1) * dc
    for l in range(2, lmax + 1):
        pm1, pl = pl, ((2 * l - 1) * c * pl - (l - 1) * pm1) / l
        lam[:, l] = (rows * pl[None, :]).sum(axis=1) * dc
    return lam


def check_addition_theorem(dirs_sample, probe_dirs, lmax, coeffs=None):
    """Gate: R_l from the harmonic coefficients == (2l+1) <P_l(d.n)> measured directly.

    Returns max |difference| over l and probe directions.
    """
    dirs_sample = np.asarray(dirs_sample, dtype=np.float64)
    probe_dirs = np.asarray(probe_dirs, dtype=np.float64)
    if coeffs is None:
        coeffs = sh_coeffs_from_dirs(dirs_sample, lmax)
    rl_sh = multipole_bands(coeffs, probe_dirs, lmax)
    rl_dir = np.zeros_like(rl_sh)
    x = dirs_sample @ probe_dirs.T
    pm1 = np.ones_like(x)
    pl = x.copy()
    rl_dir[0] = 1.0
    if lmax >= 1:
        rl_dir[1] = 3.0 * pl.mean(axis=0)
    for l in range(2, lmax + 1):
        pm1, pl = pl, ((2 * l - 1) * x * pl - (l - 1) * pm1) / l
        rl_dir[l] = (2 * l + 1) * pl.mean(axis=0)
    return float(np.max(np.abs(rl_sh - rl_dir))), rl_sh, rl_dir


def vmf_density_map(dirs, grid, kappa=30.0, chunk=5000):
    """von Mises-Fisher kernel density on `grid`, normalised to mean 1 (same as
    build_cc_direction_map.py).  Returns the relative density (isotropic == 1)."""
    dirs = np.asarray(dirs, dtype=np.float64)
    dens = np.zeros(grid.shape[0])
    for s in range(0, dirs.shape[0], chunk):
        dens += np.exp(kappa * (grid @ dirs[s:s + chunk].T) - kappa).sum(axis=1)
    return dens / dens.mean()


def rotate_dirs(dirs, seed):
    """NULL CONTROL: rigid rotation of a direction sample by a fixed random rotation."""
    rr = np.random.RandomState(int(seed))
    m, _ = np.linalg.qr(rr.normal(size=(3, 3)))
    if np.linalg.det(m) < 0:
        m[:, 0] = -m[:, 0]
    return np.asarray(dirs, dtype=np.float64) @ m.T
