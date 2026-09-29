#!/usr/bin/env python3
"""PART 2b/2c: closure and model-mismatch Monte Carlo as a function of the burst pole angle.

Two generators, the same fitter, the same measured R (l <= 6 from the slice's selected
true-CC reco directions), the same real ES table and the same real (E, CT score, truth)
event pool of the t = 0.50 selection:

  mode "accept"  (b)  the acceptance model is EXACTLY TRUE:
                      true-ES reco dirs ~ m(d.n|E) R(d) / Z(n)   (rejection sampling)
                      true-CC reco dirs ~ R(d) / (4 pi)
  mode "migrate" (c)  a MIGRATION mechanism with the SAME marginal density:
                      a direction is drawn from the kinematics only (ES: m(d0.n|E)/2pi,
                      CC: isotropic) and then DRAGGED along the great circle towards the
                      nearest detector axis by the 1-D optimal-transport map that pushes the
                      isotropic measure onto R inside each of the six axis cells.  No event
                      is thrown away, so the pile-up is a resolution effect, not an
                      efficiency -- and the multiplicative model is then wrong.

Each synthetic burst is fitted twice on the same grid:
  without:  L(n) = prod_i [ p_i m(d_i.n|E_i) + (1-p_i)/2 ]
  with:     L(n) = prod_i [ p_i m(d_i.n|E_i)/Z_i(n) + (1-p_i)/2 ]
(the second is the recommended model: with a common R the factor R(d_i) cancels, verified
in pole_derive.py G6).

Usage:
  python3 python/ana/pole_mc.py --out <dir> --modes accept,migrate --nburst 250 --nproc 6
"""
import argparse
import json
import sys
import time
from math import pi, sqrt
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from ana.pole_common import (POLES, band_density, fib_grid, legendre_moments,  # noqa: E402
                            load_collect, multipole_bands, p_es_from_calib, pole_angle,
                            sh_coeffs)
from ana.burst_direction import load_pdf_table, pdf_rows_for_energies  # noqa: E402

CD = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/combo_study")
BD = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/brems_study")
CALIB = CD / "tables" / "combo_p_es_given_score_e5_full.npz"
LMAX, PDF_FLOOR, CHUNK, GRID_N = 6, 1e-4, 2048, 12000
POLE_ANGLES = [0.0, 5.0, 10.0, 20.0, 30.0, 45.0, 54.0]

# pole -> (e1, e2) with e2 = p x e1; the cell of a pole is |d.p| largest
_E1 = np.array([[0, 1.0, 0], [0, 1.0, 0], [0, 0, 1.0], [0, 0, 1.0], [1.0, 0, 0], [1.0, 0, 0]])
_E2 = np.cross(POLES, _E1)

_G = {}


def setup():
    if _G:
        return _G
    S = load_collect(str(BD / "collect_673_900.npz"), 673, 900)
    sel = (S["ct"] >= 0.50) & (S["e_reco"] > 5.0)
    _G["pool"] = {"E": S["e_reco"][sel], "ct": S["ct"][sel], "es": (S["is_es"][sel] == 1)}
    _G["coeffs"] = sh_coeffs(S["dirs"][sel & (S["is_es"] != 1)], LMAX)
    _G["tab"] = load_pdf_table(str(CD / "tables" / "combo_slice_t050_full.npz"),
                               pdf_floor=PDF_FLOOR)
    g = fib_grid(GRID_N)
    _G["grid"] = g
    _G["rl_grid"] = multipole_bands(_G["coeffs"], g, LMAX)
    _G["Rmax"] = float(band_density(_G["coeffs"], fib_grid(400000), LMAX)[0].max()) * 1.02
    _G["mig"] = build_migration(_G["coeffs"])
    # R as the analysis would MEASURE it in a migration world: the migrated marginal of an
    # isotropic (true-CC) sample.  Used by mode "migself", which is therefore internally
    # consistent -- generator and fitted R come from the same world.
    rng = np.random.default_rng(5)
    d0 = rng.normal(size=(2000000, 3))
    d0 /= np.linalg.norm(d0, axis=1, keepdims=True)
    _G["coeffs_mig"] = sh_coeffs(migrate(d0, _G["mig"]), LMAX)
    _G["rl_grid_mig"] = multipole_bands(_G["coeffs_mig"], g, LMAX)
    return _G


def gen_mode(mode):
    """"migself" generates like "migrate"; only the R used in the fit differs."""
    return "migrate" if mode == "migself" else mode


# ------------------------------------------------------------------ migration transport map
def psi_max(phi):
    """Boundary of the axis cell: tan(psi) <= 1/max(|cos phi|, |sin phi|)."""
    return np.arctan(1.0 / np.maximum(np.abs(np.cos(phi)), np.abs(np.sin(phi))))


def build_migration(coeffs, n_phi=144, n_psi=801, n_t=801):
    """s_of_t[k, j, :]: psi'/psi_max as a function of t = (1-cos psi)/(1-cos psi_max).

    Inside each axis cell and at fixed azimuth phi the map transports the isotropic measure
    sin(psi) dpsi onto R(psi, phi) sin(psi) dpsi, renormalised to the cell's isotropic mass
    (a transport map cannot move mass between cells; the residual is quantified by
    `check_marginal`).
    """
    phi_c = (np.arange(n_phi) + 0.5) * 2 * pi / n_phi
    t_grid = np.linspace(0.0, 1.0, n_t)
    s_of_t = np.empty((6, n_phi, n_t))
    for k in range(6):
        p, e1, e2 = POLES[k], _E1[k], _E2[k]
        for j, phi in enumerate(phi_c):
            pmax = psi_max(phi)
            psi = np.linspace(0.0, pmax, n_psi)
            d = (np.cos(psi)[:, None] * p[None, :]
                 + np.sin(psi)[:, None] * (np.cos(phi) * e1 + np.sin(phi) * e2)[None, :])
            R = band_density(coeffs, d, LMAX)[0]
            w = R * np.sin(psi)
            Fw = np.concatenate([[0.0], np.cumsum(0.5 * (w[1:] + w[:-1]) * np.diff(psi))])
            Fw /= Fw[-1]
            s_of_t[k, j] = np.interp(t_grid, Fw, psi) / pmax
    return {"phi_c": phi_c, "t_grid": t_grid, "s_of_t": s_of_t, "n_phi": n_phi}


def migrate(dirs, mig):
    """Drag each direction along the great circle towards its nearest axis."""
    d = np.asarray(dirs, dtype=np.float64)
    k = np.argmax(d @ POLES.T, axis=1)
    p, e1, e2 = POLES[k], _E1[k], _E2[k]
    cpsi = np.clip(np.einsum("ij,ij->i", d, p), -1.0, 1.0)
    psi = np.arccos(cpsi)
    phi = np.arctan2(np.einsum("ij,ij->i", d, e2), np.einsum("ij,ij->i", d, e1))
    pmax = psi_max(phi)
    t = np.clip((1.0 - cpsi) / np.maximum(1.0 - np.cos(pmax), 1e-300), 0.0, 1.0)
    j = np.minimum((phi % (2 * pi)) / (2 * pi / mig["n_phi"]), mig["n_phi"] - 1e-9).astype(int)
    # vectorised lookup of s_of_t[k, j, :] at t (the t-grid is uniform in [0, 1])
    tg = mig["t_grid"]
    nt = len(tg)
    u = np.clip(t * (nt - 1), 0.0, nt - 1 - 1e-12)
    i0 = u.astype(np.int64)
    fr = u - i0
    tabk = mig["s_of_t"][k, j]                                    # (N, n_t)
    s = (np.take_along_axis(tabk, i0[:, None], 1)[:, 0] * (1 - fr)
         + np.take_along_axis(tabk, (i0 + 1)[:, None], 1)[:, 0] * fr)
    psi2 = np.clip(s, 0.0, 1.0) * pmax
    _ = psi
    return (np.cos(psi2)[:, None] * p
            + np.sin(psi2)[:, None] * (np.cos(phi)[:, None] * e1 + np.sin(phi)[:, None] * e2))


def check_marginal(coeffs, mig, n=2000000, seed=3):
    """SH bands of the migrated marginal vs the target R (isotropic input)."""
    rng = np.random.default_rng(seed)
    d0 = rng.normal(size=(n, 3))
    d0 /= np.linalg.norm(d0, axis=1, keepdims=True)
    c_mig = sh_coeffs(migrate(d0, mig), LMAX)
    probe = fib_grid(4000)
    rl_t = multipole_bands(coeffs, probe, LMAX)
    rl_m = multipole_bands(c_mig, probe, LMAX)
    r_t = rl_t.sum(axis=0)
    r_m = rl_m.sum(axis=0)
    pa = pole_angle(probe)
    prof = {}
    for lo, hi in [(0, 10), (10, 20), (20, 30), (30, 40), (40, 54.8)]:
        m = (pa >= lo) & (pa < hi)
        prof[f"{lo}-{hi}"] = [float(r_t[m].mean()), float(r_m[m].mean())]
    return {"rms_R_l_target": [float(v) for v in rl_t.std(axis=1)],
            "rms_R_l_migrated": [float(v) for v in rl_m.std(axis=1)],
            "rms_band_difference": [float(v) for v in (rl_m - rl_t).std(axis=1)],
            "corr_R_target_migrated": float(np.corrcoef(r_t, r_m)[0, 1]),
            "R_range_target": [float(r_t.min()), float(r_t.max())],
            "R_range_migrated": [float(r_m.min()), float(r_m.max())],
            "mean_R_vs_pole_angle_target_migrated": prof,
            "n_sampled": int(n)}


# ------------------------------------------------------------------------------- generation
def sample_cos_from_rows(rows, edges, rng):
    """One cos per row, drawn from that row's histogram (uniform inside the chosen bin)."""
    w = rows * np.diff(edges)[None, :]
    cdf = np.cumsum(w, axis=1)
    cdf /= cdf[:, -1:]
    u = rng.random(rows.shape[0])
    b = np.clip((cdf < u[:, None]).sum(axis=1), 0, rows.shape[1] - 1)
    return edges[b] + rng.random(rows.shape[0]) * (edges[b + 1] - edges[b])


def frame(n0, rng=None):
    a = np.array([0.0, 0.0, 1.0]) if abs(n0[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    e1 = np.cross(n0, a)
    e1 /= np.linalg.norm(e1)
    return e1, np.cross(n0, e1)


def gen_burst(mode, n0, E, ct, es, rng, G):
    tab, centers, edges = G["tab"], G["tab"]["cos_centers"], G["tab"]["cos_edges"]
    rows = pdf_rows_for_energies(tab, E)
    e1, e2 = frame(n0)
    n_ev = len(E)
    out = np.empty((n_ev, 3))
    n_try = 0
    todo = np.arange(n_ev)
    _ = centers
    while len(todo):
        n_try += len(todo)
        d = np.empty((len(todo), 3))
        isses = es[todo]
        # ES: cos from the kinematic row, azimuth uniform about n0
        if isses.any():
            ii = np.where(isses)[0]
            c = sample_cos_from_rows(rows[todo[ii]], edges, rng)
            ph = rng.random(len(ii)) * 2 * pi
            s = np.sqrt(np.maximum(0.0, 1 - c * c))
            d[ii] = (c[:, None] * n0[None, :]
                     + s[:, None] * (np.cos(ph)[:, None] * e1[None, :]
                                     + np.sin(ph)[:, None] * e2[None, :]))
        if (~isses).any():
            jj = np.where(~isses)[0]
            v = rng.normal(size=(len(jj), 3))
            d[jj] = v / np.linalg.norm(v, axis=1, keepdims=True)
        if mode == "accept":
            r = band_density(G["coeffs"], d, LMAX)[0]
            keep = rng.random(len(todo)) < (r / G["Rmax"])
        else:
            d = migrate(d, G["mig"])
            keep = np.ones(len(todo), bool)
        out[todo[keep]] = d[keep]
        todo = todo[~keep]
    return out, n_try


# ---------------------------------------------------------------------------------- fitting
def fit_pair(d, E, p, G, rl=None):
    tab, centers = G["tab"], G["tab"]["cos_centers"]
    rows = pdf_rows_for_energies(tab, E)
    log_rows = np.log(np.maximum(rows, 1e-300))
    lam = legendre_moments(rows, centers, LMAX)
    grid = G["grid"]
    rl = G["rl_grid"] if rl is None else rl
    c0, dc, nc = centers[0], centers[1] - centers[0], len(centers)
    ll_no = np.zeros(grid.shape[0])
    ll_wi = np.zeros(grid.shape[0])
    for st in range(0, grid.shape[0], CHUNK):
        cosg = d @ grid[st:st + CHUNK].T
        t = (np.clip(cosg, c0, centers[-1]) - c0) / dc
        idx = np.minimum(t.astype(np.int64), nc - 2)
        fr = t - idx
        v0 = np.take_along_axis(log_rows, idx, axis=1)
        v1 = np.take_along_axis(log_rows, idx + 1, axis=1)
        g_es = np.exp(v0 + (v1 - v0) * fr)
        ll_no[st:st + CHUNK] = np.log(np.maximum(p[:, None] * g_es
                                                 + (1 - p)[:, None] * 0.5, 1e-300)).sum(axis=0)
        z = np.maximum(lam @ rl[:, st:st + CHUNK], 1e-3)
        ll_wi[st:st + CHUNK] = np.log(np.maximum(p[:, None] * g_es / z
                                                 + (1 - p)[:, None] * 0.5, 1e-300)).sum(axis=0)
    return post_mean(grid, ll_no), post_mean(grid, ll_wi)


def post_mean(grid, ll):
    w = np.exp(ll - ll.max())
    v = (w[:, None] * grid).sum(axis=0)
    nv = np.linalg.norm(v)
    return (v / nv if nv > 0 else grid[int(np.argmax(ll))])


def one_burst(job):
    mode, ipole, pa_deg, seed, n_ev = job
    G = setup()
    rng = np.random.default_rng(seed)
    # burst direction at pa_deg from a random pole, random azimuth around it
    p = POLES[ipole]
    e1, e2 = frame(p)
    ph = rng.random() * 2 * pi
    a = np.radians(pa_deg)
    n0 = np.cos(a) * p + np.sin(a) * (np.cos(ph) * e1 + np.sin(ph) * e2)
    n0 /= np.linalg.norm(n0)
    pool = G["pool"]
    k = rng.integers(0, len(pool["E"]), size=n_ev)
    E, ct, es = pool["E"][k], pool["ct"][k], pool["es"][k]
    p_i = p_es_from_calib(str(CALIB), ct)
    d, _ = gen_burst(gen_mode(mode), n0, E, ct, es, rng, G)
    rl = G["rl_grid_mig"] if mode == "migself" else G["rl_grid"]
    r_no, r_wi = fit_pair(d, E, p_i, G, rl=rl)
    return dict(mode=mode, pole_angle=pa_deg, ipole=int(ipole), n0=n0.tolist(),
                nes=int(es.sum()), n_ev=int(n_ev),
                reco_no=r_no.tolist(), reco_wi=r_wi.tolist(),
                cos_no=float(np.clip(r_no @ n0, -1, 1)),
                cos_wi=float(np.clip(r_wi @ n0, -1, 1)))


# ---------------------------------------------------------------------------------- summary
def signed_radial(truth, reco):
    """angle(reco, p) - angle(truth, p) with p = the pole nearest the TRUTH, in degrees."""
    t = np.atleast_2d(truth)
    r = np.atleast_2d(reco)
    k = np.argmax(t @ POLES.T, axis=1)
    p = POLES[k]
    at = np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", t, p), -1, 1)))
    ar = np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", r, p), -1, 1)))
    return ar - at


def geometric_bias(truth, theta_deg, rng, nrep=40):
    """Radial bias expected from an UNBIASED isotropic error of the same size per burst."""
    t = np.atleast_2d(truth)
    out = []
    for i in range(t.shape[0]):
        e1, e2 = frame(t[i])
        a = np.radians(theta_deg[i])
        ph = rng.random(nrep) * 2 * pi
        r = (np.cos(a) * t[i][None, :]
             + np.sin(a) * (np.cos(ph)[:, None] * e1[None, :] + np.sin(ph)[:, None] * e2[None, :]))
        out.append(signed_radial(np.repeat(t[i][None, :], nrep, 0), r).mean())
    return np.asarray(out)


def summarise(res):
    S = {}
    rng = np.random.default_rng(99)
    for mode in ("accept", "migrate", "migself"):
        if not any(r["mode"] == mode for r in res):
            continue
        S[mode] = {}
        for pa in POLE_ANGLES:
            sub = [r for r in res if r["mode"] == mode and r["pole_angle"] == pa]
            if not sub:
                continue
            t = np.array([r["n0"] for r in sub])
            row = {"n_bursts": len(sub), "mean_nes": float(np.mean([r["nes"] for r in sub]))}
            for key, tag in (("no", "without"), ("wi", "with")):
                c = np.array([r[f"cos_{key}"] for r in sub])
                rc = np.array([r[f"reco_{key}"] for r in sub])
                th = np.degrees(np.arccos(np.clip(c, -1, 1)))
                sr = signed_radial(t, rc)
                gb = geometric_bias(t, th, rng)
                row[tag] = {
                    "theta68": float(np.degrees(np.arccos(np.quantile(c, 0.32)))),
                    "median": float(np.median(th)), "mean": float(th.mean()),
                    "radial_bias_mean": float(sr.mean()),
                    "radial_bias_sem": float(sr.std(ddof=1) / sqrt(len(sr))),
                    "radial_bias_geom_expected": float(gb.mean()),
                    "radial_bias_excess": float(sr.mean() - gb.mean())}
            thn = np.degrees(np.arccos(np.clip(np.array([r["cos_no"] for r in sub]), -1, 1)))
            thw = np.degrees(np.arccos(np.clip(np.array([r["cos_wi"] for r in sub]), -1, 1)))
            row["d_theta68"] = row["with"]["theta68"] - row["without"]["theta68"]
            row["d_mean"] = float((thw - thn).mean())
            row["d_mean_sem"] = float((thw - thn).std(ddof=1) / sqrt(len(thw)))
            row["frac_improved"] = float(np.mean(thw < thn))
            S[mode][str(pa)] = row
    return S



def crosscheck(n_bursts, out_json=None):
    """Gate: fit a few synthetic bursts with this script's fitter and with one built directly
    on the previous agent's `combo_acceptance` helpers (the exact calls `combo_gridfit.py`
    makes), and report the angle between the two posterior means."""
    from ana.combo_acceptance import legendre_moments_of_rows, multipole_bands as cm_bands
    G = setup()
    grid = G["grid"]
    rl_prev = cm_bands(np.load(CD / "tables" / "combo_slice_t050_full.npz",
                               allow_pickle=True)["coeffs_cc"], grid, LMAX)[:LMAX + 1]
    centers = G["tab"]["cos_centers"]
    worst_no = worst_wi = 0.0
    worst_z = 0.0
    for b in range(n_bursts):
        rng = np.random.default_rng(7000 + b)
        n0 = rng.normal(size=3)
        n0 /= np.linalg.norm(n0)
        k = rng.integers(0, len(G["pool"]["E"]), size=640)
        E, ct, es = (G["pool"]["E"][k], G["pool"]["ct"][k], G["pool"]["es"][k])
        p_i = p_es_from_calib(str(CALIB), ct)
        d, _ = gen_burst("accept", n0, E, ct, es, rng, G)
        a, c = fit_pair(d, E, p_i, G)
        rows = pdf_rows_for_energies(G["tab"], E)
        lam_prev = legendre_moments_of_rows(rows, centers, LMAX)
        worst_z = max(worst_z, float(np.max(np.abs(
            (lam_prev @ rl_prev) - (legendre_moments(rows, centers, LMAX) @ G["rl_grid"]))
            / np.maximum(lam_prev @ rl_prev, 1e-6))))
        a2, c2 = fit_pair(d, E, p_i, G, rl=rl_prev)
        worst_no = max(worst_no, float(np.degrees(np.arccos(np.clip(a @ a2, -1, 1)))))
        worst_wi = max(worst_wi, float(np.degrees(np.arccos(np.clip(c @ c2, -1, 1)))))
    res = {"n_bursts": int(n_bursts),
           "max_rel_dZ_mine_vs_combo_acceptance": worst_z,
           "max_dangle_without_term_deg": worst_no,
           "max_dangle_with_term_deg": worst_wi}
    print("crosscheck vs combo_acceptance:", json.dumps(res), flush=True)
    if out_json:
        Path(out_json).write_text(json.dumps(res, indent=1))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--modes", default="accept,migrate")
    ap.add_argument("--nburst", type=int, default=250)
    ap.add_argument("--nev", type=int, default=640)
    ap.add_argument("--nproc", type=int, default=6)
    ap.add_argument("--check-marginal", type=int, default=2000000)
    ap.add_argument("--crosscheck-only", type=int, default=0,
                    help="fit N synthetic bursts with both implementations and exit")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if args.crosscheck_only:
        crosscheck(args.crosscheck_only, out / 'pole_mc_crosscheck.json')
        return
    G = setup()
    print(f"pool {len(G['pool']['E'])} events, purity {G['pool']['es'].mean():.4f}, "
          f"Rmax {G['Rmax']:.4f}", flush=True)
    J = {"config": {"nburst": args.nburst, "nev": args.nev, "grid_n": GRID_N, "lmax": LMAX,
                    "pole_angles": POLE_ANGLES,
                    "pool_purity": float(G["pool"]["es"].mean()),
                    "pool_n": int(len(G["pool"]["E"])),
                    "mean_p_i": float(p_es_from_calib(str(CALIB), G["pool"]["ct"]).mean())}}
    if args.check_marginal:
        J["migration_marginal_check"] = check_marginal(G["coeffs"], G["mig"],
                                                      n=args.check_marginal)
        print("marginal check:", json.dumps(J["migration_marginal_check"], indent=1),
              flush=True)
    jobs = []
    s = 1000
    for mode in args.modes.split(","):
        for pa in POLE_ANGLES:
            for b in range(args.nburst):
                jobs.append((mode, b % 6, pa, s, args.nev))
                s += 1
    print(f"{len(jobs)} synthetic bursts", flush=True)
    import multiprocessing as mp
    res = []
    with mp.Pool(args.nproc) as pool:
        for i, r in enumerate(pool.imap_unordered(one_burst, jobs, chunksize=4)):
            res.append(r)
            if (i + 1) % 200 == 0:
                print(f"  {i+1}/{len(jobs)}, {time.time()-t0:.0f}s", flush=True)
    J["results"] = summarise(res)
    for mode in J["results"]:
        print(f"\n== {mode} ==")
        print(f"{'pole_ang':>8} {'th68_no':>8} {'th68_wi':>8} {'d68':>7} {'bias_no':>8} "
              f"{'bias_wi':>8} {'geom':>7} {'excess_wi':>9} {'frac_imp':>8}")
        for pa, row in J["results"][mode].items():
            print(f"{pa:>8} {row['without']['theta68']:8.2f} {row['with']['theta68']:8.2f} "
                  f"{row['d_theta68']:7.2f} {row['without']['radial_bias_mean']:8.2f} "
                  f"{row['with']['radial_bias_mean']:8.2f} "
                  f"{row['with']['radial_bias_geom_expected']:7.2f} "
                  f"{row['with']['radial_bias_excess']:9.2f} {row['frac_improved']:8.2f}")
    (out / "pole_mc.json").write_text(json.dumps(J, indent=1))
    np.savez(out / "pole_mc.npz",
             mode=np.array([r["mode"] for r in res]),
             pole_angle=np.array([r["pole_angle"] for r in res]),
             n0=np.array([r["n0"] for r in res]),
             reco_no=np.array([r["reco_no"] for r in res]),
             reco_wi=np.array([r["reco_wi"] for r in res]),
             cos_no=np.array([r["cos_no"] for r in res]),
             cos_wi=np.array([r["cos_wi"] for r in res]),
             nes=np.array([r["nes"] for r in res]))
    print(f"\nwrote {out/'pole_mc.json'} ({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
