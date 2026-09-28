"""Unit checks for the 2026-09-04 burst_direction fixes: clipped pdf lookup + seeded emcee."""
import sys, time
import numpy as np
sys.path.insert(0, "/afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/python/ana")
sys.path.insert(0, "/afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/python")
import burst_direction as bd
from mixture_offline_variants import PdfLookup

pdf_path = "/afs/cern.ch/work/e/evilla/private/dune/refactor-snop-pipeline/data/cosine_energy_pdf.npz"
rng = np.random.default_rng(1)
N = 200000
E = rng.uniform(1.0, 70.0, N)          # deliberately beyond the table on both sides
cos = rng.uniform(-1.0, 1.0, N)
pts = np.column_stack([E, cos])

# (a) new default vs the validated offline clipped convention
new = bd.load_pdf_interpolator(pdf_path)
ref = PdfLookup(pdf_path, mode="clipped")
rows, _ = ref.rows(E)
# offline: rows linear in energy, then linear in cos on the centres (clipped)
c = np.clip(cos, ref.c_centers[0], ref.c_centers[-1])
ci = np.clip(np.searchsorted(ref.c_centers, c, side="right"), 1, ref.n_c - 1)
fc = (c - ref.c_centers[ci - 1]) / (ref.c_centers[ci] - ref.c_centers[ci - 1])
ref_vals = rows[np.arange(N), ci - 1] * (1 - fc) + rows[np.arange(N), ci] * fc
v_new = new(pts)
rel = np.abs(v_new - ref_vals) / np.maximum(ref_vals, 1e-12)
print(f"(a) clipped: max rel diff vs offline PdfLookup('clipped') = {rel.max():.2e}, min pdf = {v_new.min():.3e}")
assert rel.max() < 1e-9

# (b) old path preserved byte-for-byte (mode='hole' == old load_pdf_interpolator)
hole = bd.load_pdf_interpolator(pdf_path, mode="hole")
ref_h = PdfLookup(pdf_path, mode="hole")
rows_h, out_e = ref_h.rows(E)
c_in = (cos >= ref_h.c_centers[0]) & (cos <= ref_h.c_centers[-1])
ci_h = np.clip(np.searchsorted(ref_h.c_centers, np.clip(cos, ref_h.c_centers[0], ref_h.c_centers[-1]), side="right"), 1, ref_h.n_c - 1)
fc_h = (np.clip(cos, ref_h.c_centers[0], ref_h.c_centers[-1]) - ref_h.c_centers[ci_h - 1]) / (ref_h.c_centers[ci_h] - ref_h.c_centers[ci_h - 1])
ref_hv = rows_h[np.arange(N), ci_h - 1] * (1 - fc_h) + rows_h[np.arange(N), ci_h] * fc_h
ref_hv = np.where(c_in & ~out_e, ref_hv, 1e-10)
v_h = np.maximum(hole(pts), 1e-10)
rel_h = np.abs(v_h - ref_hv) / np.maximum(ref_hv, 1e-12)
print(f"(b) hole: max rel diff vs offline PdfLookup('hole') = {rel_h.max():.2e}; in-hole fraction of random points = {(~c_in).mean():.3f}")
assert rel_h.max() < 1e-6

# (c) synthetic burst: does the fixed likelihood peak at the truth, and is emcee repeatable?
truth = np.array([0.3, -0.5, 0.81]); truth /= np.linalg.norm(truth)
# draw ES-like directions: cos to truth from the table at ~10 MeV
tbl = bd.load_pdf_table(pdf_path)
row = tbl["pdf"][np.argmin(np.abs(tbl["energy_centers"] - 10.0))]
p = row / row.sum()
n_ev = 240
cos_t = rng.choice(tbl["cos_centers"], size=n_ev, p=p) + rng.uniform(-0.01, 0.01, n_ev)
cos_t = np.clip(cos_t, -1, 1)
# random azimuth around truth
a = np.cross(truth, [1, 0, 0]); a /= np.linalg.norm(a); b = np.cross(truth, a)
phi = rng.uniform(0, 2 * np.pi, n_ev)
dirs = (cos_t[:, None] * truth[None, :]
        + np.sqrt(1 - cos_t**2)[:, None] * (np.cos(phi)[:, None] * a[None, :] + np.sin(phi)[:, None] * b[None, :]))
dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
energies = np.full(n_ev, 10.0)
weights = np.ones(n_ev)
cfg = {"nwalkers": 128, "nsteps": 500, "discard": 100, "random_seed": 42}

def run(interp):
    t0 = time.time()
    r = bd._run_emcee(dirs, weights, energies, truth, cfg, interp)
    return r["reco_dir"], np.degrees(np.arccos(np.clip(r["reco_dir"] @ truth, -1, 1))), time.time() - t0

d1, th1, t1 = run(new)
d2, th2, t2 = run(new)
print(f"(c) fixed lookup: emcee theta to truth = {th1:.2f} deg (run 1), {th2:.2f} deg (run 2); identical = {np.array_equal(d1, d2)}; {t1:.1f}s per run")
assert np.array_equal(d1, d2), "emcee still not reproducible"
d3, th3, _ = run(hole)
print(f"    hole lookup, same events: emcee theta to truth = {th3:.2f} deg")
# likelihood at truth vs at the fixed-lookup MAP vs at the hole MAP
ll = lambda interp, d: bd._pdf_likelihood(dirs, energies, d, interp)
print(f"    logL(truth) - logL(reco): clipped {ll(new, truth) - ll(new, d1):+.2f}   hole {ll(hole, truth) - ll(hole, d3):+.2f}")
print("ALL CHECKS PASSED")
