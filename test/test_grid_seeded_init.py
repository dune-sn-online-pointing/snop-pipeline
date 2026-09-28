"""Check of the grid-seeded walker initialisation (2026-09-07).

- init_mode "grid" (default) starts the walkers at the likelihood maximum found on an
  equal-area grid: on a synthetic pure-ES burst with true directions the fit must land
  within 1 deg of the truth (the 45-deg init around the weighted mean gave ~1.5 deg on
  real bursts and could not collapse onto the ~0.5-deg posterior in 500 steps).
- init_mode "mean" reproduces the legacy behaviour (45-deg init around the weighted mean).
- Both are bit-repeatable, and on a contaminated burst the grid seed must not be worse
  than the legacy init by more than the sampler noise.

Run:  source scripts/init.sh && python3 test/test_grid_seeded_init.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python" / "ana"))
import burst_direction as bd  # noqa: E402

pdf_path = str(Path(__file__).resolve().parents[1] / "data" / "cosine_energy_pdf.npz")
interp = bd.load_pdf_interpolator(pdf_path)
rng = np.random.default_rng(11)
truth = np.array([0.1, -0.7, 0.7]); truth /= np.linalg.norm(truth)


def around(axis, cos_vals):
    a = np.cross(axis, [1, 0, 0]); a /= np.linalg.norm(a); b = np.cross(axis, a)
    phi = rng.uniform(0, 2 * np.pi, len(cos_vals))
    s = np.sqrt(1 - cos_vals**2)
    d = cos_vals[:, None] * axis[None, :] + s[:, None] * (np.cos(phi)[:, None] * a + np.sin(phi)[:, None] * b)
    return d / np.linalg.norm(d, axis=1, keepdims=True)


tbl = bd.load_pdf_table(pdf_path)
th = lambda r: float(np.degrees(np.arccos(np.clip(r["reco_dir"] @ truth, -1, 1))))  # noqa: E731

# (1) pure ES, TRUE directions (best case): cos to the neutrino ~ 0.973 with a tight spread
n = 240
cos_true = np.clip(rng.normal(0.973, 0.03, n), -1, 1)
dirs_true = around(truth, cos_true)
en = np.full(n, 10.0)
w = np.ones(n)
r_grid = bd._run_emcee(dirs_true, w, en, truth, {"nwalkers": 128, "nsteps": 500, "discard": 100, "random_seed": 42}, interp)
r_grid2 = bd._run_emcee(dirs_true, w, en, truth, {"nwalkers": 128, "nsteps": 500, "discard": 100, "random_seed": 42}, interp)
r_mean = bd._run_emcee(dirs_true, w, en, truth, {"nwalkers": 128, "nsteps": 500, "discard": 100, "random_seed": 42, "init_mode": "mean"}, interp)
print(f"(1) best case: grid-seeded {th(r_grid):.2f} deg (repeat identical={np.array_equal(r_grid['reco_dir'], r_grid2['reco_dir'])}), legacy 45-deg init {th(r_mean):.2f} deg")
assert np.array_equal(r_grid["reco_dir"], r_grid2["reco_dir"])
assert th(r_grid) < 1.0

# (2) contaminated: 90 ES (reco-like, cos from the 12 MeV pdf row) + 90 isotropic CC
row = tbl["pdf"][np.argmin(np.abs(tbl["energy_centers"] - 12.0))]
p = row / row.sum()
es = around(truth, np.clip(rng.choice(tbl["cos_centers"], 90, p=p) + rng.uniform(-0.01, 0.01, 90), -1, 1))
cc = rng.normal(size=(90, 3)); cc /= np.linalg.norm(cc, axis=1, keepdims=True)
dirs = np.vstack([es, cc]); en2 = np.full(180, 12.0); w2 = np.ones(180)
g = bd._run_emcee(dirs, w2, en2, truth, {"nwalkers": 128, "nsteps": 500, "discard": 100, "random_seed": 42}, interp)
m = bd._run_emcee(dirs, w2, en2, truth, {"nwalkers": 128, "nsteps": 500, "discard": 100, "random_seed": 42, "init_mode": "mean"}, interp)
print(f"(2) contaminated: grid-seeded {th(g):.2f} deg, legacy init {th(m):.2f} deg, acceptance {g['acceptance_fraction']:.2f} / {m['acceptance_fraction']:.2f}")
assert th(g) < th(m) + 3.0
print("GRID-SEEDED INIT OK")
