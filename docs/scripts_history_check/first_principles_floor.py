#!/usr/bin/env python3
"""Read-only first-principles check of the burst-pointing statistical floor.

Measures the true ES kinematic opening angle (true electron momentum vs true
neutrino momentum) directly from the cluster-image metadata of CT-training cats
(400-410 -- deliberately NOT evaluation cats), then estimates the achievable
68% containment of the burst direction as a function of N events for:
  (a) the plain mean-vector estimator,
  (b) a maximum-likelihood estimator using the true pdf(cos|E).

Nothing is written outside docs/scripts_history_check/ output printed to stdout.
"""
import glob
import os
import sys
import numpy as np

BASE = "/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples"
CATS = [f"cat{n:06d}" for n in range(400, 411)]
SUB = "_cluster_images_tick3_ch2_min2_tot3_e3p0"
EMIN = float(os.environ.get("EMIN", "3.0"))


def load_events():
    """Return (cos_true, E_cluster, E_true) for main-track true-ES clusters."""
    cos_l, ecl_l, etr_l = [], [], []
    nfiles = 0
    for cat in CATS:
        pat = os.path.join(BASE, cat, cat + SUB, "X", "es_*.npz")
        for f in sorted(glob.glob(pat)):
            try:
                d = np.load(f, allow_pickle=True)
                m = np.asarray(d["metadata"], dtype=np.float64)
            except Exception:
                continue
            if m.ndim != 2 or m.shape[1] < 18:
                continue
            nfiles += 1
            is_es = m[:, 3].astype(int) == 1
            is_main = m[:, 2].astype(int) == 1
            pe = m[:, 7:10]
            pn = m[:, 15:18]
            ne = np.linalg.norm(pe, axis=1)
            nn = np.linalg.norm(pn, axis=1)
            ok = is_es & is_main & (ne > 0) & (nn > 0)
            if not np.any(ok):
                continue
            c = np.sum(pe[ok] * pn[ok], axis=1) / (ne[ok] * nn[ok])
            cos_l.append(np.clip(c, -1.0, 1.0))
            ecl_l.append(m[ok, 10])
            etr_l.append(m[ok, 11])
    if not cos_l:
        raise SystemExit("no events found")
    return (np.concatenate(cos_l), np.concatenate(ecl_l),
            np.concatenate(etr_l), nfiles)


def rayleigh68(sigma_per_axis):
    """68% containment radius of a 2-D isotropic Gaussian."""
    return sigma_per_axis * np.sqrt(-2.0 * np.log(1.0 - 0.68))


def analytic_meanvec(cos, N):
    R = cos.mean()
    S2 = (cos ** 2).mean()
    sigma = np.sqrt((1.0 - S2) / (2.0 * N)) / R
    return np.degrees(rayleigh68(sigma)), R, S2


def build_pdf(cos, ecl, nE=6, nC=60):
    """Binned pdf(cos | E) with equal-count energy bins."""
    qs = np.linspace(0, 1, nE + 1)
    eedges = np.quantile(ecl, qs)
    eedges[0] -= 1e-6
    eedges[-1] += 1e-6
    cedges = np.linspace(-1.0, 1.0, nC + 1)
    cw = cedges[1] - cedges[0]
    pdf = np.zeros((nE, nC))
    for i in range(nE):
        sel = (ecl > eedges[i]) & (ecl <= eedges[i + 1])
        h, _ = np.histogram(cos[sel], bins=cedges)
        h = h.astype(float)
        h += 0.5                      # Laplace smoothing, avoids log(0)
        pdf[i] = h / (h.sum() * cw)
    return eedges, cedges, pdf


def analytic_mle(cos, ecl, N, nE=6, nC=60):
    """Fisher-information floor for the pdf(cos|E) likelihood.

    Per-event info about a transverse rotation eps:
        I = 1/2 * Integral  (p'(c)^2 / p(c)) * (1-c^2) dc
    averaged over the energy spectrum.
    """
    eedges, cedges, pdf = build_pdf(cos, ecl, nE, nC)
    ccen = 0.5 * (cedges[:-1] + cedges[1:])
    cw = cedges[1] - cedges[0]
    Itot = 0.0
    for i in range(pdf.shape[0]):
        p = pdf[i]
        dp = np.gradient(p, cw)
        integ = np.sum((dp ** 2 / np.maximum(p, 1e-12)) * (1 - ccen ** 2)) * cw
        frac = np.mean((ecl > eedges[i]) & (ecl <= eedges[i + 1]))
        Itot += frac * 0.5 * integ
    sigma = 1.0 / np.sqrt(N * Itot)
    return np.degrees(rayleigh68(sigma)), Itot


def toy_mc(cos, ecl, N, ntoy=400, seed=1, use_pdf=True, nE=6, nC=60):
    """Draw N events per toy burst, estimate the direction, return angle errors.

    Truth is +z. Each event's electron direction is placed at the measured
    opening angle with uniform azimuth. Both estimators are evaluated on the
    same events.
    """
    rng = np.random.default_rng(seed)
    eedges, cedges, pdf = build_pdf(cos, ecl, nE, nC)
    ccen = 0.5 * (cedges[:-1] + cedges[1:])
    logpdf = np.log(pdf)

    # grid of trial directions around +z (fine enough for sub-degree work)
    ang = np.radians(np.arange(0.0, 25.0, 0.20))
    az = np.linspace(0, 2 * np.pi, 72, endpoint=False)
    trial = [np.array([0.0, 0.0, 1.0])]
    for a in ang[1:]:
        for b in az:
            trial.append(np.array([np.sin(a) * np.cos(b), np.sin(a) * np.sin(b), np.cos(a)]))
    trial = np.asarray(trial)

    err_mean = np.empty(ntoy)
    err_mle = np.full(ntoy, np.nan)
    ntot = cos.size
    for t in range(ntoy):
        idx = rng.integers(0, ntot, N)
        c = cos[idx]
        E = ecl[idx]
        phi = rng.random(N) * 2 * np.pi
        s = np.sqrt(np.maximum(0.0, 1 - c ** 2))
        u = np.stack([s * np.cos(phi), s * np.sin(phi), c], axis=1)

        m = u.sum(axis=0)
        m /= np.linalg.norm(m)
        err_mean[t] = np.degrees(np.arccos(np.clip(m[2], -1, 1)))

        if use_pdf:
            ebin = np.clip(np.searchsorted(eedges, E) - 1, 0, pdf.shape[0] - 1)
            cosgrid = u @ trial.T                      # (N, ntrial)
            cbin = np.clip(np.searchsorted(cedges, cosgrid) - 1, 0, pdf.shape[1] - 1)
            ll = logpdf[ebin[:, None], cbin].sum(axis=0)
            best = trial[np.argmax(ll)]
            err_mle[t] = np.degrees(np.arccos(np.clip(best[2], -1, 1)))
    return err_mean, err_mle


def q68(x):
    x = x[np.isfinite(x)]
    return float(np.quantile(x, 0.68))


if __name__ == "__main__":
    cos, ecl, etr, nfiles = load_events()
    print(f"Loaded {cos.size} true-ES main-track clusters from {nfiles} files "
          f"(cats {CATS[0]}..{CATS[-1]}, plane X)")
    print(f"cluster-energy range {ecl.min():.2f}-{ecl.max():.2f} MeV, "
          f"median {np.median(ecl):.2f}")
    sel = ecl >= EMIN
    print(f"\nEnergy cut E_cluster >= {EMIN} MeV keeps {sel.sum()}/{cos.size} "
          f"({100*sel.mean():.1f}%)")
    c = cos[sel]; e = ecl[sel]
    print(f"  <cos>            R  = {c.mean():.4f}   -> mean opening angle "
          f"{np.degrees(np.arccos(c.mean())):.2f} deg")
    print(f"  <cos^2>          S2 = {(c**2).mean():.4f}")
    print(f"  median opening angle = {np.degrees(np.arccos(np.median(c))):.2f} deg")
    print(f"  frac(cos<0) = {np.mean(c<0):.4f}")

    print("\nEnergy dependence (equal-count bins):")
    print(f"  {'E range [MeV]':>18} {'n':>7} {'<cos>':>8} {'<cos^2>':>9} {'<theta> [deg]':>14}")
    qs = np.quantile(e, np.linspace(0, 1, 9))
    for i in range(len(qs) - 1):
        m = (e >= qs[i]) & (e < qs[i + 1] if i < len(qs) - 2 else e <= qs[i + 1])
        if m.sum() < 5:
            continue
        print(f"  {qs[i]:7.2f}-{qs[i+1]:7.2f} {m.sum():7d} {c[m].mean():8.4f} "
              f"{(c[m]**2).mean():9.4f} {np.degrees(np.arccos(c[m].mean())):14.2f}")

    print("\n" + "=" * 88)
    print("STATISTICAL FLOOR: 68% containment of the burst direction vs N events")
    print("(analytic = Fisher/Rayleigh; toy = 400 simulated bursts, empirical 68% quantile)")
    print("=" * 88)
    an_mle_1, Itot = analytic_mle(c, e, 1)
    print(f"per-event Fisher information of the pdf(cos|E) likelihood: I = {Itot:.4f} rad^-2")
    hdr = (f"{'N':>6} {'meanvec analytic':>18} {'meanvec toy68':>15} "
           f"{'MLE analytic':>14} {'MLE toy68':>11}")
    print(hdr); print("-" * len(hdr))
    for N in [50, 100, 150, 200, 239, 300, 330, 400, 500, 1000]:
        a_mv, R, S2 = analytic_meanvec(c, N)
        a_ml, _ = analytic_mle(c, e, N)
        em, el = toy_mc(c, e, N, ntoy=400, seed=100 + N)
        print(f"{N:6d} {a_mv:18.2f} {q68(em):15.2f} {a_ml:14.2f} {q68(el):11.2f}")

    print("\nN needed for a 3.00 deg 68% containment (analytic scaling ~ 1/sqrt(N)):")
    a_mv, R, S2 = analytic_meanvec(c, 239)
    a_ml, _ = analytic_mle(c, e, 239)
    print(f"  mean-vector estimator: N = {239 * (a_mv / 3.0) ** 2:.0f}")
    print(f"  pdf-MLE estimator:     N = {239 * (a_ml / 3.0) ** 2:.0f}")
