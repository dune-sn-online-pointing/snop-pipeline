#!/usr/bin/env python3
"""Two-orientation (Phase I: one HD + one VD module) pointing emulation from the r3 campaign.

ALL campaign numbers assume ONE horizontal-drift geometry, so the detector-frame anisotropy of
the reconstruction is common to every module.  In DUNE Phase I the two 10 kt modules have
perpendicular drift directions.  The VD readout cannot be simulated here; this script EMULATES
the second module as the HD response ROTATED by a fixed rotation R_rot (an estimate, not a VD
simulation), for two bracketing choices:

  rotz90 : 90 deg about z (beam axis): x (HD drift) -> y (vertical = VD drift).  Geometric choice.
  rotx90 : 90 deg about x: y -> z, i.e. swaps a "bad" direction with the good +-z.  Optimistic.

Per evaluation cat c (true direction n_c):
  module A = the cat's own events trimmed to keep fraction F (10 kt at 10 kpc: F = 0.25), by
             event identity with seed s, exactly as replay_scenario_from_slim.py --keep-fraction
             (trim_keep_mask, ES and CC separately, before the unchanged selection);
  module B = the events of a PARTNER cat c' != c (any campaign cat, never 400-621) whose true
             direction is closest to R_rot^-1 n_c, trimmed to F with an independent seed
             (s + 100), rotated into the lab frame by R' = Q R_rot, Q the smallest rotation taking
             R_rot n_c' onto n_c (so R' n_c' = n_c exactly; |Q| is the partner distance).
Joint fit = the deployed grid-mixture likelihood (scenario_8_full_pipeline_acc_t030: CT >= 0.30,
E > 5 MeV, p_i from the slice calibration with pi fixed, flat CC, ES table ct030_r3, acceptance
l <= 6, 12000-point Fibonacci grid, posterior mean) with module-B events seen through module B's
frame:  ES kernel evaluated at (R' d_i).n and Z_i(n) = sum_l lambda_l^(i) R_l(R'^-1 n).
Events of the two modules are independent, so log L = log L_A(n) + log L_B(n).

Arms:  same20   : the cat trimmed to 2F (same-orientation 20 kt; the Phase I curve)
       samepair : module A + partner nearest n_c with R_rot = identity (partner effect only)
       rotz90   : module A + partner, R_rot = 90 deg about z
       rotx90   : module A + partner, R_rot = 90 deg about x

Gate: partner = the cat itself, R' = identity, module A = trimmed half (F = 0.5, seed 1) and
module B = its complement -> must equal the production fit of the untrimmed cat.

Subcommands:
  cache   --cats ...           per-cat selected-event cache (npz, scratch), with a per-cat
                               bitwise check against select_electrons_from_run
  gate    --cats 2-6           the correctness gate
  run     --procs 12           all fits -> <out>/two_orientation_fits.json
  report                       summary md/json + maps figure
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from ana.burst_direction import (Z_FLOOR, calibrated_p_es, fibonacci_sphere_grid,  # noqa: E402
                                 grid_mixture_posterior, flat_pdf_table, load_ct_calibration,
                                 load_pdf_table, load_reco_acceptance, normalize_rows,
                                 normalize_vector, pdf_rows_for_energies,
                                 reconstruct_burst_direction_grid_mixture,
                                 select_electrons_from_run)
from ana.combo_acceptance import legendre_moments_of_rows, multipole_bands  # noqa: E402
from ana.replay_scenario_from_slim import (extract_run, reporting_from_catalog,  # noqa: E402
                                           trim_keep_mask)

REPO = _HERE.parents[1]
PC = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-campaign")
CAMPAIGN = PC / "v63_matchfix_1000"
DEPLOYED = PC / "v63_matchfix_1000_acc_t030"
CATALOG = REPO / "json" / "eight_scenarios_v63_acceptance.json"
SCENARIO = "scenario_8_full_pipeline_acc_t030"
SOURCE_SCENARIO = "scenario_3_full_pipeline"
TRUTH_CACHE = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/combo_study/"
                   "resolution_maps/true_burst_dirs_1000.npz")
OUT = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/combo_study/two_orientation")
N_GEN_ES, N_GEN_CC = 330, 3300
CAMPAIGN_CATS = [n for n in list(range(1, 400)) + list(range(623, 1225)) if n != 701]
EVAL_CATS = [n for n in CAMPAIGN_CATS if 2 <= n <= 399 or 901 <= n <= 1224]
SEEDS = [1, 2, 3]
SEED_B_OFFSET = 100

ROT = {
    "identity": np.eye(3),
    "rotz90": np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]]),   # x -> y, y -> -x
    "rotx90": np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]),   # y -> z, z -> -y
}


# ----------------------------------------------------------------------------- configuration
def deployed_cfg():
    cat = json.loads(CATALOG.read_text())
    entry = next(s for s in cat["scenarios"] if s["name"] == SCENARIO)
    rep = reporting_from_catalog(entry)
    m = rep["mixture"]
    assert rep["selection_mode"] == "mixture-ct" and m.get("cc_pdf_mode") == "flat"
    assert m.get("pi_mode") == "fixed" and m.get("ct_source", "ct") == "ct"
    assert m.get("s_min") is None and float(m.get("p_floor", 0.0)) == 0.0
    return rep


class Model:
    """Deployed ES table, calibration, acceptance and grid (loaded once per process)."""

    def __init__(self):
        self.rep = deployed_cfg()
        m = self.rep["mixture"]
        self.pdf_floor = float(m.get("pdf_floor", 1e-4))
        self.table = load_pdf_table(m.get("pdf_es_path", self.rep.get("pdf_path")),
                                    pdf_floor=self.pdf_floor)
        self.acc = load_reco_acceptance(m.get("acceptance_path", self.rep.get("acceptance_path")))
        self.calib = load_ct_calibration(m["calibration_path"])
        self.pi = float(m["pi_fixed"])
        self.ct_cut = float(m["ct_hard_cut"])
        self.emin = float(self.rep["min_energy_mev"])
        self.grid_n = int(m.get("grid_n", 41253))
        self.grid = fibonacci_sphere_grid(self.grid_n)
        self.grid32 = self.grid.astype(np.float32)
        self.lmax = int(self.acc["lmax"])
        self.rl_lab = multipole_bands(self.acc["coeffs"], self.grid, self.lmax)

    def rl_rotated(self, rprime):
        """R_l(R'^-1 n) on the lab grid: rows of grid @ R' are R'^T n = R'^-1 n."""
        if np.allclose(rprime, np.eye(3), atol=0, rtol=0):
            return self.rl_lab
        return multipole_bands(self.acc["coeffs"], self.grid @ rprime, self.lmax)


# ----------------------------------------------------------------------------- per-cat cache
def cache_path(cache_dir, n):
    return Path(cache_dir) / f"cat{n:06d}_sel.npz"


def build_cache_one(args):
    n, cache_dir, scratch = args
    out = cache_path(cache_dir, n)
    if out.is_file():
        return n, "exists"
    model = MODEL
    tar = CAMPAIGN / f"cat{n:06d}" / f"cat{n:06d}_scenarios_slim.tar"
    work = Path(tempfile.mkdtemp(prefix=f"twoori_{n}_", dir=scratch))
    try:
        got = extract_run(tar, SOURCE_SCENARIO, work)
        if got is None:
            return n, "no run"
        run_dir = got[0]
        meta = np.asarray(np.load(run_dir / "volume_images" / "volumes.npz",
                                  allow_pickle=True)["metadata"], dtype=np.float64)
        rd = np.load(run_dir / "predictions" / "reco_directions.npz", allow_pickle=True)
        reco = normalize_rows(np.asarray(rd["reco_dirs"], dtype=np.float64))
        valid = np.isfinite(reco).all(axis=1) & (np.linalg.norm(reco, axis=1) > 0)
        if "has_reco" in rd:
            valid &= np.asarray(rd["has_reco"]).astype(bool)
        ct = np.asarray(np.load(run_dir / "predictions" / "channel_predictions.npz",
                                allow_pickle=True)["y_pred_proba"], dtype=np.float64)
        energy = meta[:, 10]
        p_all = np.clip(calibrated_p_es(ct, model.calib, model.pi), 0.0, 1.0)
        mask = (ct >= model.ct_cut) & (energy >= model.emin) & valid
        idx = np.flatnonzero(mask)
        # bitwise check against the production selection
        sel = select_electrons_from_run(run_dir, selection_mode="mixture-ct",
                                        direction_mode=model.rep["direction_mode"],
                                        min_energy_mev=model.emin,
                                        ct_threshold=model.rep.get("ct_threshold"),
                                        mixture_cfg=model.rep["mixture"])
        ok = (np.array_equal(sel["selected_dirs"], reco[idx])
              and np.array_equal(sel["selected_energy"], energy[idx])
              and np.array_equal(sel["mixture"]["p_es"], p_all[idx]))
        if not ok:
            raise RuntimeError(f"cat {n}: own selection differs from select_electrons_from_run")
        np.savez(out, meta=meta, idx=idx, dirs=reco[idx], energy=energy[idx], p=p_all[idx],
                 is_es=(meta[idx, 3].astype(int) == 1), truth=sel["true_burst_dir"])
        return n, f"ok {idx.size}"
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _init_worker():
    global MODEL
    MODEL = Model()


class CatEvents:
    def __init__(self, path, model):
        z = np.load(path)
        self.meta = z["meta"]
        self.idx = z["idx"]
        self.dirs = z["dirs"]
        self.energy = z["energy"]
        self.p = z["p"]
        self.is_es = z["is_es"]
        self.truth = z["truth"]
        rows = pdf_rows_for_energies(model.table, self.energy)
        self.lam = legendre_moments_of_rows(rows, model.table["cos_centers"], model.lmax)
        self.log_rows = np.log(np.maximum(rows, 1e-300)).astype(np.float32)

    def keep(self, frac, seed, cat_number):
        """Selected-event mask of the --keep-fraction draw (trim_keep_mask, unchanged)."""
        if frac >= 1.0:
            return np.ones(self.idx.size, dtype=bool)
        k, _ = trim_keep_mask(self.meta, frac, seed, cat_number, N_GEN_ES, N_GEN_CC)
        return k[self.idx]


# ----------------------------------------------------------------------------- likelihood
def module_loglike(model, ev, sel, rprime, rl, chunk=4096):
    """log L of one module's events on the lab grid (the acceptance branch of
    grid_mixture_posterior, with the module's frame rotation R')."""
    dirs = ev.dirs[sel]
    if rprime is not None:
        dirs = dirs @ rprime.T
    dirs = dirs.astype(np.float32)
    lam = ev.lam[sel]
    log_rows = ev.log_rows[sel]
    p = ev.p[sel][:, None]
    q_cc = np.full(dirs.shape[0], 0.5)
    cos_centers = model.table["cos_centers"]
    c0 = np.float32(cos_centers[0])
    c_last = np.float32(cos_centers[-1])
    inv_dc = np.float32(1.0 / (cos_centers[1] - cos_centers[0]))
    n_c = cos_centers.shape[0]
    ll = np.empty(model.grid_n, dtype=np.float64)
    for start in range(0, model.grid_n, chunk):
        g = model.grid32[start:start + chunk]
        t = (np.clip(dirs @ g.T, c0, c_last) - c0) * inv_dc
        idx = np.minimum(t.astype(np.int32), n_c - 2)
        frac = t - idx
        v0 = np.take_along_axis(log_rows, idx, axis=1)
        v1 = np.take_along_axis(log_rows, idx + 1, axis=1)
        g_es = np.exp(v0 + (v1 - v0) * frac)
        z = np.maximum(lam @ rl[:, start:start + chunk], Z_FLOOR)
        m = p * g_es / z + (1.0 - p) * q_cc[:, None]
        ll[start:start + chunk] = np.sum(np.log(np.maximum(m, 1e-300)), axis=0, dtype=np.float64)
    return ll


def posterior_mean(model, log_like):
    post = np.exp(log_like - np.max(log_like))
    post /= np.sum(post)
    return normalize_vector(np.sum(post[:, None] * model.grid, axis=0))


def ang(a, b):
    return float(np.degrees(np.arccos(np.clip(np.dot(a, b), -1.0, 1.0))))


def smallest_rotation(a, b):
    """Rotation matrix taking unit vector a onto unit vector b about a x b."""
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    v = np.cross(a, b)
    s = np.linalg.norm(v)
    c = float(np.dot(a, b))
    if s < 1e-15:
        if c > 0:
            return np.eye(3)
        raise ValueError("antiparallel")
    k = v / s
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + s * K + (1 - c) * (K @ K)


# ----------------------------------------------------------------------------- partners
def load_truth():
    z = np.load(TRUTH_CACHE)
    return {int(c): np.asarray(t, dtype=np.float64) for c, t in zip(z["cats"], z["truth"])}


def choose_partners(truth, rot_name):
    rr = ROT[rot_name]
    pool = np.array(CAMPAIGN_CATS)
    P = np.array([truth[c] for c in pool])
    out = {}
    for c in EVAL_CATS:
        target = rr.T @ truth[c]                       # R_rot^-1 n_c
        cos = P @ target
        cos[pool == c] = -2.0                          # never the cat itself
        j = int(np.argmax(cos))
        cp = int(pool[j])
        a = rr @ truth[cp]
        q = smallest_rotation(a, truth[c])
        rprime = q @ rr
        assert np.allclose(rprime @ truth[cp], truth[c], atol=1e-12)
        out[c] = {"partner": cp, "dist_deg": ang(a, truth[c]), "rprime": rprime}
    return out


# ----------------------------------------------------------------------------- fits
TASK = {}


def fit_cat(c):
    model = MODEL
    cfg = TASK
    ev_cache = {}

    def get(n):
        if n not in ev_cache:
            ev_cache[n] = CatEvents(cache_path(cfg["cache"], n), model)
        return ev_cache[n]

    A = get(c)
    rows = []
    for fA, fsame, label in cfg["fractions"]:
        for s in SEEDS:
            # (i) same orientation 20 kt: the cat trimmed to fsame
            if fsame is not None:
                sel = A.keep(fsame, s, c)
                ll = module_loglike(model, A, sel, None, model.rl_lab)
                mu = posterior_mean(model, ll)
                rows.append({"arm": "same20", "dist": label, "seed": s, "cat": c,
                             "theta": ang(mu, A.truth), "cos": float(np.dot(mu, A.truth)),
                             "n_sel": int(sel.sum()), "n_true_es": int(A.is_es[sel].sum())})
            selA = A.keep(fA, s, c)
            llA = module_loglike(model, A, selA, None, model.rl_lab)
            for arm in cfg["arms"][label]:
                pinfo = cfg["partners"][arm][c]
                cp = pinfo["partner"]
                B = get(cp)
                selB = B.keep(fA, s + SEED_B_OFFSET, cp)
                rp = np.asarray(pinfo["rprime"])
                llB = module_loglike(model, B, selB, rp, model.rl_rotated(rp))
                mu = posterior_mean(model, llA + llB)
                rows.append({"arm": arm, "dist": label, "seed": s, "cat": c, "partner": cp,
                             "partner_dist_deg": pinfo["dist_deg"],
                             "theta": ang(mu, A.truth), "cos": float(np.dot(mu, A.truth)),
                             "n_sel": int(selA.sum() + selB.sum()),
                             "n_sel_A": int(selA.sum()), "n_sel_B": int(selB.sum()),
                             "n_true_es": int(A.is_es[selA].sum() + B.is_es[selB].sum())})
    return rows


def _init_fit(task):
    global TASK
    _init_worker()
    TASK = task


# ----------------------------------------------------------------------------- report helpers
def theta68(cos):
    return float(np.degrees(np.arccos(np.clip(np.quantile(np.asarray(cos), 0.32), -1, 1))))


def draw_stats(cos_by_seed, rng, n_boot=2000):
    """cos_by_seed: (n_seeds, n_cats).  theta68 = mean over draws of the per-draw theta68;
    68% interval from resampling the CATS (same resample for every draw)."""
    C = np.asarray(cos_by_seed)
    th = np.degrees(np.arccos(np.clip(C, -1, 1)))
    per = np.array([theta68(c) for c in C])
    n = C.shape[1]
    boots = np.empty(n_boot)
    for b in range(n_boot):
        ii = rng.integers(0, n, n)
        boots[b] = np.mean([theta68(c[ii]) for c in C])
    lo, hi = np.percentile(boots, [16, 84])
    return {"N": int(n), "theta68": float(per.mean()), "theta68_per_draw": per.tolist(),
            "draw_spread_std": float(per.std(ddof=1)) if per.size > 1 else 0.0,
            "theta68_lo": float(lo), "theta68_hi": float(hi), "theta68_err": float(0.5 * (hi - lo)),
            "median": float(np.mean([np.median(t) for t in th])),
            "frac_gt30": float(np.mean(th > 30)), "_boots": boots}


def paired_gain(C_ref, C_arm, rng, n_boot=2000):
    """theta68(ref) - theta68(arm), draw-averaged, paired bootstrap over cats."""
    C_ref, C_arm = np.asarray(C_ref), np.asarray(C_arm)
    d0 = np.mean([theta68(c) for c in C_ref]) - np.mean([theta68(c) for c in C_arm])
    n = C_ref.shape[1]
    bs = np.empty(n_boot)
    for b in range(n_boot):
        ii = rng.integers(0, n, n)
        bs[b] = (np.mean([theta68(c[ii]) for c in C_ref]) - np.mean([theta68(c[ii]) for c in C_arm]))
    lo, hi = np.percentile(bs, [16, 84])
    return float(d0), float(lo), float(hi)


# ----------------------------------------------------------------------------- commands
def cmd_cache(args):
    cats = parse_cats(args.cats) if args.cats else None
    if cats is None:
        truth = load_truth()
        need = set(EVAL_CATS)
        for r in ("identity", "rotz90", "rotx90"):
            need |= {v["partner"] for v in choose_partners(truth, r).values()}
        cats = sorted(need)
    Path(args.cache).mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with Pool(args.procs, initializer=_init_worker) as pool:
        for k, (n, msg) in enumerate(pool.imap_unordered(
                build_cache_one, [(n, args.cache, args.scratch) for n in cats])):
            if k % 50 == 0 or not msg.startswith(("ok", "exists")):
                print(f"  [{k + 1}/{len(cats)}] cat {n}: {msg} ({time.time() - t0:.0f}s)", flush=True)
    print(f"cache done: {len(cats)} cats in {time.time() - t0:.0f}s")


def cmd_gate(args):
    global MODEL
    MODEL = Model()
    model = MODEL
    res = []
    for c in parse_cats(args.cats):
        ev = CatEvents(cache_path(args.cache, c), model)
        # production: the deployed fitter on the untrimmed cat
        reco = reconstruct_burst_direction_grid_mixture(
            ev.dirs, ev.energy, ev.p, ev.truth,
            pdf_es_path=model.table["path"], cc_pdf_mode="flat", grid_n=model.grid_n,
            pdf_floor=model.pdf_floor, acceptance_path=model.acc["path"])
        prod_theta = reco["single_pass_theta_deg"]
        stored = None
        f = DEPLOYED / f"cat{c:06d}" / "scenario_cos_theta_report.json"
        if f.is_file():
            for s in json.loads(f.read_text())["scenarios"]:
                if s.get("scenario") == SCENARIO:
                    stored = float(s["single_pass_theta_deg"])
        # joint fit: half A (F = 0.5, seed 1) + its complement as module B, partner = self,
        # R' = identity (passed explicitly through the rotated-frame code path)
        selA = ev.keep(0.5, 1, c)
        llA = module_loglike(model, ev, selA, None, model.rl_lab)
        eye = np.eye(3)
        llB = module_loglike(model, ev, ~selA, eye,
                             multipole_bands(model.acc["coeffs"], model.grid @ eye, model.lmax))
        mu = posterior_mean(model, llA + llB)
        joint_theta = ang(mu, ev.truth)
        # a non-trivial rotation check: rotate EVERYTHING (both halves) by a random R' with
        # the truth rotated too -> theta must be unchanged up to grid discretisation
        res.append({"cat": c, "n_sel": int(ev.idx.size), "n_A": int(selA.sum()),
                    "production_theta": prod_theta, "stored_campaign_theta": stored,
                    "joint_theta": joint_theta,
                    "joint_minus_production_deg": joint_theta - prod_theta,
                    "angle_between_means_deg": ang(mu, reco["reco_dir"]),
                    "max_abs_dloglike": float(np.max(np.abs((llA + llB) - reco["log_like"])))})
        print(json.dumps(res[-1]), flush=True)
    return res


def cmd_run(args):
    truth = load_truth()
    partners = {r if r != "identity" else "samepair": choose_partners(truth, r)
                for r in ("identity", "rotz90", "rotx90")}
    task = {"cache": args.cache,
            "partners": {k: {c: {"partner": v["partner"], "dist_deg": v["dist_deg"],
                                 "rprime": v["rprime"].tolist()} for c, v in d.items()}
                         for k, d in partners.items()},
            # (fraction per module, same-orientation fraction, label)
            "fractions": [(0.25, 0.5, "10kpc"), (0.25 * (10 / 15) ** 2, 0.5 * (10 / 15) ** 2, "15kpc")],
            "arms": {"10kpc": ["samepair", "rotz90", "rotx90"], "15kpc": ["rotz90", "rotx90"]}}
    cats = parse_cats(args.cats) if args.cats else EVAL_CATS
    rows = []
    t0 = time.time()
    with Pool(args.procs, initializer=_init_fit, initargs=(task,)) as pool:
        for k, r in enumerate(pool.imap_unordered(fit_cat, cats, chunksize=2)):
            rows.extend(r)
            if k % 25 == 0:
                print(f"  {k + 1}/{len(cats)} cats ({time.time() - t0:.0f}s)", flush=True)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    payload = {"driver": "python/ana/two_orientation_emulation.py run",
               "scenario": SCENARIO, "catalog": str(CATALOG), "campaign": str(CAMPAIGN),
               "rotations": {k: v.tolist() for k, v in ROT.items()},
               "seeds_A": SEEDS, "seed_B_offset": SEED_B_OFFSET,
               "fractions": task["fractions"], "arms": task["arms"],
               "partners": task["partners"], "rows": rows,
               "elapsed_s": time.time() - t0}
    fname = out / (args.tag or "two_orientation_fits.json")
    tmp = fname.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload) + "\n")
    os.replace(tmp, fname)
    print(f"wrote {fname}: {len(rows)} fits, {time.time() - t0:.0f}s")


def cmd_report(args):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize
    from ana.resolution_sky_map import (AXIS_BINS, SCHEME_722, axis_angle, draw_mollweide,
                                        igloo_assign)
    out = Path(args.out)
    d = json.loads((out / "two_orientation_fits.json").read_text())
    rows = d["rows"]
    truth = load_truth()
    cats = EVAL_CATS
    rng = np.random.default_rng(12345)

    def cosmat(arm, dist):
        m = {(r["seed"], r["cat"]): r["cos"] for r in rows if r["arm"] == arm and r["dist"] == dist}
        if not m:
            return None
        return np.array([[m[(s, c)] for c in cats] for s in SEEDS])

    def meanfield(arm, dist, key):
        v = [r[key] for r in rows if r["arm"] == arm and r["dist"] == dist]
        return float(np.mean(v))

    arms = [("same20", "10kpc", "(i) same orientation, 20 kt (cat trimmed to 0.5)"),
            ("samepair", "10kpc", "(ii) same orientation, 2 x 10 kt from different bursts"),
            ("rotz90", "10kpc", "(iii) two orientations, 90 deg about z (VD drift = vertical)"),
            ("rotx90", "10kpc", "(iv) two orientations, 90 deg about x (optimistic)"),
            ("same20", "15kpc", "(i) same orientation, 20 kt, 15 kpc"),
            ("rotz90", "15kpc", "(iii) 90 deg about z, 15 kpc"),
            ("rotx90", "15kpc", "(iv) 90 deg about x, 15 kpc")]
    C = {(a, dd): cosmat(a, dd) for a, dd, _ in arms}
    summary = {}
    for a, dd, lab in arms:
        if C[(a, dd)] is None:
            continue
        st = draw_stats(C[(a, dd)], rng)
        st.pop("_boots")
        st["mean_n_sel"] = meanfield(a, dd, "n_sel")
        st["mean_true_es"] = meanfield(a, dd, "n_true_es")
        summary[f"{a}_{dd}"] = {"label": lab, **st}
    gains = {}
    for dd in ("10kpc", "15kpc"):
        for a in ("samepair", "rotz90", "rotx90"):
            if C.get((a, dd)) is not None and C.get(("same20", dd)) is not None:
                gains[f"{a}_{dd}"] = dict(zip(("d_theta68", "lo", "hi"),
                                              paired_gain(C[("same20", dd)], C[(a, dd)], rng)))

    # sky cells / axis profile (lab frame = module A frame)
    dirs = np.array([truth[c] for c in cats])
    cell, geo = igloo_assign(dirs, SCHEME_722)
    aang = axis_angle(dirs)
    maps, prof, cellgain = {}, {}, {}
    for a in ("same20", "rotz90", "rotx90", "samepair"):
        M = C[(a, "10kpc")]
        cells = []
        for k, g in enumerate(geo):
            m = cell == k
            st = draw_stats(M[:, m], rng)
            st.pop("_boots")
            cells.append({"cell": k, **g, **st,
                          "lat_lo": float(np.degrees(np.arcsin(g["z_lo"]))),
                          "lat_hi": float(np.degrees(np.arcsin(g["z_hi"])))})
        maps[a] = cells
        pr = []
        for lo, hi in AXIS_BINS:
            m = (aang >= lo) & (aang < hi)
            st = draw_stats(M[:, m], rng)
            st.pop("_boots")
            pr.append({"bin": [lo, hi], "mean_axis_angle": float(aang[m].mean()), **st})
        prof[a] = pr
    for a in ("rotz90", "rotx90", "samepair"):
        cg = []
        for k in range(len(geo)):
            m = cell == k
            g0, lo, hi = paired_gain(C[("same20", "10kpc")][:, m], C[(a, "10kpc")][:, m], rng)
            cg.append({"cell": k, "d_theta68": g0, "lo": lo, "hi": hi})
        cellgain[a] = cg

    # partner distance statistics
    pstats = {}
    for a, pd in d["partners"].items():
        dist = np.array([pd[str(c)]["dist_deg"] for c in cats])
        pcats = np.array([pd[str(c)]["partner"] for c in cats])
        uniq, cnt = np.unique(pcats, return_counts=True)
        pstats[a] = {"mean": float(dist.mean()), "median": float(np.median(dist)),
                     "p90": float(np.percentile(dist, 90)), "max": float(dist.max()),
                     "n_distinct_partners": int(uniq.size), "max_reuse": int(cnt.max()),
                     "frac_partner_eval": float(np.mean([(2 <= p <= 399) or (901 <= p <= 1224)
                                                         for p in pcats])),
                     "frac_partner_dev_623_672": float(np.mean((pcats >= 623) & (pcats <= 672))),
                     "frac_partner_slice_673_900": float(np.mean((pcats >= 673) & (pcats <= 900))),
                     "n_partner_cat1": int(np.sum(pcats == 1))}

    # figure
    cmap = plt.get_cmap("viridis")
    allt = [c["theta68"] for a in ("same20", "rotz90", "rotx90") for c in maps[a]]
    norm = Normalize(vmin=np.floor(min(allt)), vmax=np.ceil(max(allt)))
    fig = plt.figure(figsize=(12, 17))
    titles = {"same20": "(i) same orientation 20 kt", "rotz90": "(iii) HD + 'VD' = HD rotated 90 deg about z",
              "rotx90": "(iv) HD + HD rotated 90 deg about x (optimistic)"}
    for i, a in enumerate(("same20", "rotz90", "rotx90")):
        ax = fig.add_subplot(3, 1, i + 1, projection="mollweide")
        s = summary[f"{a}_10kpc"]
        draw_mollweide(ax, maps[a], norm, cmap,
                       f"{titles[a]}, 10 kpc, 722 eval cats, mean of 3 draws; overall "
                       f"$\\theta_{{68}}$ = {s['theta68']:.2f}$^\\circ$", fontsize=7)
    sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    cb = fig.colorbar(sm, ax=fig.axes, orientation="horizontal", fraction=0.025, pad=0.04, aspect=50)
    cb.set_label(r"$\theta_{68}$ per cell [deg] (common scale; lab frame = module A (HD) frame)")
    fig.savefig(out / "two_orientation_maps.png", dpi=130, bbox_inches="tight")
    plt.close(fig)

    payload = {"summary": summary, "gain_vs_same20": gains, "maps": maps, "axis_profile": prof,
               "cell_gain_vs_same20": cellgain, "partner_stats": pstats,
               "gate": json.loads((out / "gate.json").read_text()) if (out / "gate.json").is_file() else None,
               "scheme": SCHEME_722, "axis_bins": AXIS_BINS, "n_boot": 2000}
    (out / "two_orientation_summary.json").write_text(json.dumps(payload, indent=1) + "\n")
    print(json.dumps({k: {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items()
                          if kk not in ("theta68_per_draw",)} for k, v in summary.items()}, indent=1))
    print(json.dumps(gains, indent=1))
    print(json.dumps(pstats, indent=1))
    for a in maps:
        print(a, [round(c["theta68"], 2) for c in maps[a]])
        print(a, "prof", [(round(r["theta68"], 2), round(r["theta68_err"], 2), r["N"]) for r in prof[a]])
    for a in cellgain:
        print(a, "gain", [round(c["d_theta68"], 2) for c in cellgain[a]])


def parse_cats(spec):
    out = []
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = (int(x) for x in part.split("-"))
            out.extend(range(lo, hi + 1))
        else:
            out.append(int(part))
    if any(400 <= c <= 621 for c in out):
        raise SystemExit("cats 400-621 are off limits")
    return sorted(set(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["cache", "gate", "run", "report"])
    ap.add_argument("--cats", default=None)
    ap.add_argument("--cache", default=os.environ.get("TWOORI_CACHE", str(Path(tempfile.gettempdir()) / "twoori_cache")))
    ap.add_argument("--scratch", default=None)
    ap.add_argument("--procs", type=int, default=8)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--tag", default=None)
    args = ap.parse_args()
    if args.command == "cache":
        cmd_cache(args)
    elif args.command == "gate":
        res = cmd_gate(args)
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "gate.json").write_text(json.dumps(res, indent=1) + "\n")
    elif args.command == "run":
        cmd_run(args)
    else:
        cmd_report(args)


if __name__ == "__main__":
    main()
