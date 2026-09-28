#!/usr/bin/env python3
"""Read-only: how much of the best-case number is emcee sampling noise?

Imports the SHIPPED reconstruct_burst_direction() from python/ana/burst_direction.py
(no modification) and runs it on real CT-training cats (400+, never evaluation
cats) with the production emcee config, several times. emcee's EnsembleSampler
is not seeded, so repeated runs on identical inputs expose the sampler noise.

The plain mean-vector estimator on the same events is printed for reference.
"""
import glob, os, sys
import numpy as np

REPO = "/afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline"
sys.path.insert(0, os.path.join(REPO, "python"))
sys.path.insert(0, os.path.join(REPO, "local_packages"))
from ana.burst_direction import reconstruct_burst_direction, angular_error_deg

BASE = "/eos/project-e/ep-nu/evilla/sn-online-pointing/sn-burst-samples"
SUB = "_cluster_images_tick3_ch2_min2_tot3_e3p0"
PDF = os.path.join(REPO, "data", "cosine_energy_pdf.npz")
EMIN = 3.0
NCAT = int(os.environ.get("NCAT", "30"))
NREP = int(os.environ.get("NREP", "3"))
PRIOR = os.environ.get("PRIOR", "gaussian_around_mean")

CFG = {"enabled": True, "nwalkers": 128, "nsteps": 500, "discard": 100,
       "random_seed": 42, "prior_type": PRIOR, "prior_sigma_deg": 10.0,
       "likelihood_kappa": 25.0}


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
        ok = ((m[:, 3].astype(int) == 1) & (m[:, 2].astype(int) == 1) &
              (ne > 0) & (nn > 0) & (m[:, 10] >= EMIN))
        if np.any(ok):
            ue.append(pe[ok] / ne[ok, None]); en.append(m[ok, 10]); un.append(pn[ok] / nn[ok, None])
    if not ue:
        return None
    U = np.concatenate(ue); E = np.concatenate(en); Un = np.concatenate(un)
    t = Un.mean(axis=0); t /= np.linalg.norm(t)
    return U, E, t


def cont68(a):
    a = np.asarray(a, float); a = a[np.isfinite(a)]
    return float(np.degrees(np.arccos(np.quantile(np.cos(np.radians(a)), 0.32))))


cats = [f"cat{n:06d}" for n in range(400, 400 + NCAT)]
data = {}
for c in cats:
    r = load_cat(c)
    if r is not None:
        data[c] = r
print(f"cats loaded: {len(data)}  prior={PRIOR}  nwalkers={CFG['nwalkers']} "
      f"nsteps={CFG['nsteps']} discard={CFG['discard']}  pdf={os.path.basename(PDF)}")

mv = []
for c, (U, E, t) in data.items():
    m = U.sum(axis=0); m /= np.linalg.norm(m)
    mv.append(angular_error_deg(m, t))
print(f"\nmean-vector estimator (no MCMC): 68% cont = {cont68(mv):.3f} deg, "
      f"median = {np.median(mv):.3f}, mean = {np.mean(mv):.3f}")

allrep = []
for rep in range(NREP):
    np.random.seed(1000 + rep)          # emcee uses the numpy global state
    ang, q68 = [], []
    for c, (U, E, t) in data.items():
        w = np.ones(len(U))
        res = reconstruct_burst_direction(U, w, E, t, use_emcee=True,
                                          emcee_cfg=CFG, pdf_path=PDF)
        ang.append(res["single_pass_theta_deg"])
        q68.append(res["omega68_deg"])
    allrep.append(np.array(ang))
    print(f"emcee repetition {rep}: 68% cont = {cont68(ang):8.3f} deg  "
          f"median = {np.median(ang):7.3f}  mean = {np.mean(ang):7.3f}  "
          f"per-burst posterior q68 median = {np.nanmedian(q68):6.2f} deg  "
          f"method = {res['method']}  accept = {res['acceptance_fraction']:.3f}")

A = np.vstack(allrep)
print(f"\nper-cat spread over {NREP} independent emcee runs on IDENTICAL inputs:")
print(f"  mean per-cat std  = {A.std(axis=0, ddof=1).mean():.3f} deg")
print(f"  max  per-cat std  = {A.std(axis=0, ddof=1).max():.3f} deg")
print(f"  mean per-cat range= {(A.max(axis=0)-A.min(axis=0)).mean():.3f} deg")
print(f"  campaign-level 68% containment varies "
      f"{min(cont68(a) for a in allrep):.2f} - {max(cont68(a) for a in allrep):.2f} deg")
print("\nfirst 10 cats, angle per repetition (deg), then mean-vector:")
for i, c in enumerate(list(data)[:10]):
    print(f"  {c}  " + "  ".join(f"{A[r, i]:6.2f}" for r in range(NREP)) + f"   | mv={mv[i]:5.2f}")
