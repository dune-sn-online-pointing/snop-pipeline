"""Regression check for the weighted likelihood (2026-09-07).

- weights None == weights of ones (hard-selection scenarios unchanged)
- weights 1 for true ES / 0 for CC == likelihood of the true-ES subset
- emcee with all-ones weights reproduces the unweighted run bit for bit
- emcee with P(ES)-like weights on a contaminated sample lands closer to the truth
  than the unweighted fit of the same events (sanity, not a guarantee)

Run:  source scripts/init.sh && python3 test/test_weighted_likelihood.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python" / "ana"))
import burst_direction as bd  # noqa: E402

pdf_path = str(Path(__file__).resolve().parents[1] / "data" / "cosine_energy_pdf.npz")
interp = bd.load_pdf_interpolator(pdf_path)
rng = np.random.default_rng(3)

truth = np.array([-0.2, 0.6, 0.77]); truth /= np.linalg.norm(truth)
tbl = bd.load_pdf_table(pdf_path)
row = tbl["pdf"][np.argmin(np.abs(tbl["energy_centers"] - 12.0))]
p = row / row.sum()


def around(axis, cos_vals):
    a = np.cross(axis, [1, 0, 0]); a /= np.linalg.norm(a); b = np.cross(axis, a)
    phi = rng.uniform(0, 2 * np.pi, len(cos_vals))
    s = np.sqrt(1 - cos_vals**2)
    d = cos_vals[:, None] * axis[None, :] + s[:, None] * (np.cos(phi)[:, None] * a + np.sin(phi)[:, None] * b)
    return d / np.linalg.norm(d, axis=1, keepdims=True)


n_es, n_cc = 200, 400
es_dirs = around(truth, np.clip(rng.choice(tbl["cos_centers"], n_es, p=p) + rng.uniform(-0.01, 0.01, n_es), -1, 1))
cc_dirs = rng.normal(size=(n_cc, 3)); cc_dirs /= np.linalg.norm(cc_dirs, axis=1, keepdims=True)
dirs = np.vstack([es_dirs, cc_dirs])
energies = np.full(len(dirs), 12.0)
is_es = np.r_[np.ones(n_es, bool), np.zeros(n_cc, bool)]

ll_none = bd._pdf_likelihood(dirs, energies, truth, interp)
ll_ones = bd._pdf_likelihood(dirs, energies, truth, interp, selected_weights=np.ones(len(dirs)))
ll_tags = bd._pdf_likelihood(dirs, energies, truth, interp, selected_weights=is_es.astype(float))
ll_es = bd._pdf_likelihood(es_dirs, energies[:n_es], truth, interp)
print(f"None vs ones: {ll_none:.6f} vs {ll_ones:.6f}; true-tag weights vs ES subset: {ll_tags:.6f} vs {ll_es:.6f}")
assert ll_none == ll_ones and abs(ll_tags - ll_es) < 1e-9

cfg = {"nwalkers": 128, "nsteps": 500, "discard": 100, "random_seed": 42}
r_unw = bd._run_emcee(dirs, np.ones(len(dirs)), energies, truth, cfg, interp)
r_ones = bd._run_emcee(dirs, np.ones(len(dirs)), energies, truth, cfg, interp)
assert np.array_equal(r_unw["reco_dir"], r_ones["reco_dir"])
# P(ES)-like weights: 0.85 +- noise for ES, 0.10 +- noise for CC
w = np.where(is_es, 0.85, 0.10) + rng.normal(0, 0.05, len(dirs))
w = np.clip(w, 0, 1)
r_w = bd._run_emcee(dirs, w, energies, truth, cfg, interp)
th = lambda r: np.degrees(np.arccos(np.clip(r["reco_dir"] @ truth, -1, 1)))  # noqa: E731
print(f"emcee theta to truth: unweighted {th(r_unw):.2f} deg, P(ES)-weighted {th(r_w):.2f} deg (200 ES + 400 isotropic CC)")
assert th(r_w) < th(r_unw)
print("WEIGHTED LIKELIHOOD OK")
