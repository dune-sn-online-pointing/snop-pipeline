#!/usr/bin/env python3
"""Read-only: refined statistical floor with a proper (optimizer-based) MLE.

Same measured ES kinematics as first_principles_floor.py, but the likelihood
estimator is maximised with Nelder-Mead over the two transverse angles instead
of a coarse direction grid, and the pdf(cos|E) is finely binned, so the MLE
number is not resolution-limited.
"""
import glob, os
import numpy as np
from scipy.optimize import minimize
from scipy.interpolate import RegularGridInterpolator

BASE = "/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples"
SUB = "_cluster_images_tick3_ch2_min2_tot3_e3p0"
CATS = [f"cat{n:06d}" for n in range(400, 421)]
EMIN = 3.0


def load():
    c_l, e_l = [], []
    for cat in CATS:
        for f in sorted(glob.glob(os.path.join(BASE, cat, cat + SUB, "X", "es_*.npz"))):
            try:
                m = np.asarray(np.load(f, allow_pickle=True)["metadata"], float)
            except Exception:
                continue
            if m.ndim != 2 or m.shape[1] < 18:
                continue
            pe, pn = m[:, 7:10], m[:, 15:18]
            ne, nn = np.linalg.norm(pe, axis=1), np.linalg.norm(pn, axis=1)
            ok = ((m[:, 3].astype(int) == 1) & (m[:, 2].astype(int) == 1) &
                  (ne > 0) & (nn > 0) & (m[:, 10] >= EMIN))
            if np.any(ok):
                c_l.append(np.clip(np.sum(pe[ok]*pn[ok], 1)/(ne[ok]*nn[ok]), -1, 1))
                e_l.append(m[ok, 10])
    return np.concatenate(c_l), np.concatenate(e_l)


cos, ecl = load()
print(f"{cos.size} true-ES clusters, cats {CATS[0]}..{CATS[-1]}, E>= {EMIN} MeV")
print(f"R=<cos>={cos.mean():.4f}  S2=<cos^2>={(cos**2).mean():.4f}  "
      f"mean opening angle={np.degrees(np.arccos(cos.mean())):.2f} deg")

# --- finely binned log pdf(cos|E), bins uniform in the opening ANGLE ---
nE, nA = 8, 240
eedges = np.quantile(ecl, np.linspace(0, 1, nE + 1)); eedges[0] -= 1e-9; eedges[-1] += 1e-9
aedges = np.linspace(0.0, np.pi, nA + 1)
acen = 0.5*(aedges[:-1] + aedges[1:])
aw = aedges[1] - aedges[0]
logp = np.zeros((nE, nA))
for i in range(nE):
    s = (ecl > eedges[i]) & (ecl <= eedges[i+1])
    h, _ = np.histogram(np.arccos(cos[s]), bins=aedges)
    h = h.astype(float) + 0.3
    # density in cos: p(cos) = p(alpha)/sin(alpha)
    dens = h/(h.sum()*aw)/np.maximum(np.sin(acen), 1e-6)
    logp[i] = np.log(np.maximum(dens, 1e-12))
ecen = 0.5*(eedges[:-1] + eedges[1:])
itp = RegularGridInterpolator((ecen, acen), logp, method="linear",
                              bounds_error=False, fill_value=None)


def mle_error(u, E, e1, e2, t):
    """Maximise sum log p(alpha_i | E_i); return angle of the maximiser from t."""
    def nll(x):
        d = t + x[0]*e1 + x[1]*e2
        d = d/np.linalg.norm(d)
        a = np.arccos(np.clip(u @ d, -1, 1))
        return -float(np.sum(itp(np.column_stack([E, a]))))
    m = u.sum(0); m /= np.linalg.norm(m)
    x0 = np.array([np.dot(m, e1), np.dot(m, e2)])
    r = minimize(nll, x0, method="Nelder-Mead",
                 options=dict(xatol=1e-6, fatol=1e-6, maxiter=4000))
    d = t + r.x[0]*e1 + r.x[1]*e2; d /= np.linalg.norm(d)
    return float(np.degrees(np.arccos(np.clip(np.dot(d, t), -1, 1))))


def cont68(a):
    a = np.asarray(a, float)
    return float(np.degrees(np.arccos(np.quantile(np.cos(np.radians(a)), 0.32))))


t = np.array([0., 0., 1.]); e1 = np.array([1., 0., 0.]); e2 = np.array([0., 1., 0.])
rng = np.random.default_rng(11)
print(f"\n{'N':>6} {'meanvec toy68':>14} {'MLE toy68':>11} {'meanvec analytic':>17}")
print("-" * 52)
R, S2 = cos.mean(), (cos**2).mean()
for N in [50, 100, 150, 200, 239, 300, 330, 400, 500, 1000]:
    em, el = [], []
    for _ in range(300):
        idx = rng.integers(0, cos.size, N)
        c, E = cos[idx], ecl[idx]
        phi = rng.random(N)*2*np.pi
        s = np.sqrt(np.maximum(0, 1-c**2))
        u = np.stack([s*np.cos(phi), s*np.sin(phi), c], 1)
        m = u.sum(0); m /= np.linalg.norm(m)
        em.append(np.degrees(np.arccos(np.clip(m[2], -1, 1))))
        el.append(mle_error(u, E, e1, e2, t))
    an = np.degrees(np.sqrt((1-S2)/(2*N))/R*np.sqrt(-2*np.log(0.32)))
    print(f"{N:6d} {cont68(em):14.2f} {cont68(el):11.2f} {an:17.2f}")

print("\nN required for a given 68% containment (mean-vector estimator, ~1/sqrt(N)):")
for target in [1.0, 2.0, 3.0, 6.06]:
    an239 = np.degrees(np.sqrt((1-S2)/(2*239))/R*np.sqrt(-2*np.log(0.32)))
    print(f"  {target:5.2f} deg -> N = {239*(an239/target)**2:8.1f}")
