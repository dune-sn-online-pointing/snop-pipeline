#!/usr/bin/env python3
"""Gates for the detector-frame reco-direction acceptance normalisation of the ES kernel.

    L(n) = prod_i [ p_i pdf_ES(cos(d_i,n) | E_i) / Z_i(n) + (1 - p_i) / 2 ],
    Z_i(n) = sum_{l<=6} lambda_l^(i) R_l(n),   R_l(n) = sum_m c_lm Y_lm(n)

with the 49 real-SH coefficients c_lm of the detector-frame acceptance R(d) measured on the
TRUE-CC reco directions of the table-building slice (cats 673-900, CT v80 >= 0.50, E > 5 MeV).
Deployed 29 September 2026 from the combined-likelihood study
(/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/combo_study/combo_study.md).

Four checks:

  (1) BIT-IDENTITY.  With acceptance_path=None both reconstruct functions return exactly
      the pre-2026-09-29 numbers on two real bursts (references below were produced with
      the unpatched module before the edit and are compared with np.array_equal).
  (2) NORMALISATION.  Z_i(n) from the 49 coefficients equals 2 <R(d) m_i(d.n)>_sphere by
      brute-force integration on a 200k-point Fibonacci grid, and Z == 1 for R == 1.
  (3) GRID PATH.  The production grid-mixture path with the acceptance reproduces the
      study's per-cat posterior-mean directions for arm CMB2_t050_accCC_ccl6.
  (4) EMCEE PATH.  reconstruct_burst_direction (deployed emcee config, uniform prior,
      grid-seeded init) with the acceptance term lands on the grid posterior mean and
      improves over no-acceptance in the same sense as the grid.

Run with:  source scripts/init.sh && python3 test/test_acceptance_term.py
"""
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "python"))

from ana.burst_direction import (  # noqa: E402
    Z_FLOOR,
    _pdf_likelihood,
    acceptance_moments,
    calibrated_p_es,
    fibonacci_sphere_grid,
    load_ct_calibration,
    load_pdf_interpolator,
    load_pdf_table,
    load_reco_acceptance,
    normalize_rows,
    normalize_vector,
    pdf_rows_for_energies,
    reconstruct_burst_direction,
    reconstruct_burst_direction_grid_mixture,
)
from ana.combo_acceptance import multipole_bands  # noqa: E402

MODEL = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/neural-networks/electron_direction/"
             "three_plane_v63_matchfix_ft58_20260921_132520")
ES_TABLE = MODEL / "cosine_energy_pdf_es_burstaxis_ct050_r3.npz"
CALIB = MODEL / "ct_v80_calibration_r3slice_e5.npz"
ACCEPTANCE = MODEL / "reco_acceptance_r3_v63_l6.npz"
ES_TABLE_T030 = MODEL / "cosine_energy_pdf_es_burstaxis_ct030_r3.npz"
ACCEPTANCE_T030 = MODEL / "reco_acceptance_r3_v63_l6_ct030.npz"
PI_FIXED = 0.068421

STUDY = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/combo_study")
DEV_COLLECT = STUDY / "collect_dev_623_672.npz"
EVAL_COLLECT = Path("/eos/project-e/ep-nu/evilla/sn-online-pointing/pipeline-dev/brems_study/"
                    "collect_eval_slimonly.npz")
STUDY_CALIB = STUDY / "tables" / "combo_p_es_given_score_e5_full.npz"
STUDY_RESULT = STUDY / "results" / "F_2_31.npz"   # holds cos_CMB2_t050_accCC_ccl6
STUDY_ARM = "CMB2_t050_accCC_ccl6"
STUDY_RESULT_T030 = STUDY / "threshold_scan" / "results" / "T_t030_2_31.npz"
STUDY_ARM_T030 = "CMB2_t030_accCC_ccl6"

# (label, hard CT cut, ES table, acceptance file, study npz, study arm tag).  The ES table and the
# acceptance are properties of the SAME selection and must always be swapped together.
ARMS = [("t=0.50 (code-path validation)", 0.50, "ES_TABLE", "ACCEPTANCE", "STUDY_RESULT", "STUDY_ARM"),
        ("t=0.30 (deployable)", 0.30, "ES_TABLE_T030", "ACCEPTANCE_T030",
         "STUDY_RESULT_T030", "STUDY_ARM_T030")]

CT_CUT, E_CUT = 0.50, 5.0
GRID_N_STUDY = 12000            # grid_n of the study's recommended arm
EMCEE_CFG = {"nwalkers": 128, "nsteps": 500, "discard": 100, "prior_type": "uniform",
             "prior_sigma_deg": 10.0, "likelihood_kappa": 25.0, "random_seed": 42,
             "pdf_lookup": "clipped", "pdf_floor": 1e-4}
# three arbitrary but fixed trial directions
TRIAL = np.array([[0.0, 0.0, 1.0],
                  [0.6, -0.8, 0.0],
                  [0.35355339059327373, 0.35355339059327373, 0.8660254037844387]])

# --------------------------------------------------------------------------------------
# Reference outputs of the UNPATCHED module (git 82401dc, before the acceptance term),
# on the dev cats 623 and 624 of the r3 campaign, selection CT v80 >= 0.50 and E > 5 MeV,
# weights = P(ES | CT score) from ct_v80_calibration_r3slice_e5.npz with pi_fixed 0.068421.
# The patched module with acceptance_path=None must reproduce every number EXACTLY.
# --------------------------------------------------------------------------------------
REFERENCE = {
    623: dict(
        n_selected=633,
        emcee_reco_dir=[-0.15328309846437335, 0.7912021993793454, 0.592033251956719],
        emcee_theta_deg=12.013086420989346,
        emcee_omega68_deg=14.039588072607199,
        pdf_loglike_3dirs=[-177.98654469692934, -195.31206878581975, -176.053002692726],
        grid_reco_dir=[-0.14920864769308162, 0.8690183718280555, 0.4717455340317673],
        grid_theta_deg=5.029464748546812,
        grid_omega68_deg=9.761970869539754,
        grid_idx_3dirs=[0, 6008, 825],
        grid_loglike_3dirs=[-455.0763304494517, -481.46050888886396, -458.8595117288976],
    ),
    624: dict(
        n_selected=697,
        emcee_reco_dir=[0.33098743676741893, 0.6672411776631434, 0.6672604645360276],
        emcee_theta_deg=5.565797156175491,
        emcee_omega68_deg=9.835104689041543,
        pdf_loglike_3dirs=[-178.15556457804107, -210.42196378522476, -155.855088451081],
        grid_reco_dir=[0.3989444526590549, 0.5813161192913585, 0.7091649266176395],
        grid_theta_deg=10.4597144601326,
        grid_omega68_deg=13.322034196466062,
        grid_idx_3dirs=[0, 6008, 825],
        grid_loglike_3dirs=[-485.7904585136894, -527.8717255002639, -458.409914056724],
    ),
}

FAILURES = []


def check(ok, msg):
    print(("  PASS  " if ok else "  FAIL  ") + msg)
    if not ok:
        FAILURES.append(msg)


def load_collect(path):
    z = np.load(path, allow_pickle=True)
    a = np.asarray(z["table"], dtype=np.float64)
    return {c: a[:, i] for i, c in enumerate(list(z["cols"]))}


def burst(collect, cat, ct_cut=CT_CUT):
    """Per-event inputs of one cat after the selection (CT >= ct_cut, E > 5 MeV)."""
    s = collect["cat"] == cat
    energy, ct = collect["e_reco"][s], collect["ct"][s]
    dirs = normalize_rows(np.column_stack([collect["dx"][s], collect["dy"][s], collect["dz"][s]]))
    true_dir = normalize_vector(np.array([collect["bx"][s][0], collect["by"][s][0],
                                          collect["bz"][s][0]]))
    m = (ct >= ct_cut) & (energy > E_CUT)
    return dirs[m], energy[m], ct[m], true_dir


def p_es_deployed(ct_scores):
    return calibrated_p_es(ct_scores, load_ct_calibration(str(CALIB)), PI_FIXED)


def p_es_study(ct_scores):
    """The offline study's purity convention: linear interpolation of P(ES|s) itself.

    The deployed calibration stores the LIKELIHOOD RATIO on a slightly wider score grid and
    interpolates that instead, so the two agree exactly at the 50 bin centres (8.3e-17) but
    differ by up to 0.007 in p_i between them.  Check (3) uses this one to isolate the
    acceptance code path from the calibration convention, and quantifies the other.
    """
    z = np.load(STUDY_CALIB, allow_pickle=True)
    s = np.asarray(z["score_center"], dtype=np.float64)
    p = np.asarray(z["p_es_mono"], dtype=np.float64)
    return np.clip(np.interp(np.clip(ct_scores, 0.0, 1.0), s, p, left=p[0], right=p[-1]), 0.0, 1.0)


def theta_deg(cos):
    return float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))


# ======================================================================================
REF_COMMIT = "e06414f"   # last commit BEFORE the acceptance term entered burst_direction.py


def _load_reference_module():
    """Import the pre-acceptance burst_direction.py (git REF_COMMIT) as a separate module.

    The stored REFERENCE numbers below were produced on one lxplus node; other CPUs (e.g.
    AMD EPYC vs Intel) round reductions differently at the 1e-14 level, and the emcee chain
    amplifies that to ~0.05 deg, so exact equality against stored numbers is machine
    dependent.  Producing the reference on THIS machine at test time with the old code keeps
    the bit-identity claim exact.  Returns None if git is unavailable (fallback: tolerances).
    """
    import importlib.util
    import subprocess
    import tempfile
    try:
        src = subprocess.run(["git", "-C", str(REPO), "show",
                              f"{REF_COMMIT}:python/ana/burst_direction.py"],
                             capture_output=True, text=True, check=True).stdout
    except Exception as exc:  # noqa: BLE001
        print(f"  NOTE  reference module unavailable ({exc}); using stored numbers with tolerances")
        return None
    tmp = Path(tempfile.mkdtemp(prefix="bd_ref_")) / "burst_direction_ref.py"
    tmp.write_text(src)
    spec = importlib.util.spec_from_file_location("burst_direction_ref", tmp)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_bit_identity():
    print("\n(1) BIT-IDENTITY with acceptance_path=None (two real bursts, cats 623/624)")
    dev = load_collect(DEV_COLLECT)
    interp = load_pdf_interpolator(str(ES_TABLE), mode="clipped", pdf_floor=1e-4)
    old = _load_reference_module()
    if old is not None:
        print(f"  reference = pre-change module from git {REF_COMMIT}, run on this machine "
              "(exact equality); stored numbers checked with tolerances only")
    for cat, ref in REFERENCE.items():
        if old is not None:
            # same-machine reference from the old code
            dirs0, energy0, ct0, true_dir0 = burst(dev, cat)
            p0 = p_es_deployed(ct0)
            interp0 = old.load_pdf_interpolator(str(ES_TABLE), mode="clipped", pdf_floor=1e-4)
            r0 = old.reconstruct_burst_direction(selected_dirs=dirs0, selected_weights=p0,
                                                 selected_energies=energy0, true_burst_dir=true_dir0,
                                                 use_emcee=True, emcee_cfg=EMCEE_CFG,
                                                 pdf_path=str(ES_TABLE))
            g0 = old.reconstruct_burst_direction_grid_mixture(
                selected_dirs=dirs0, selected_energies=energy0, p_es=p0, true_burst_dir=true_dir0,
                pdf_es_path=str(ES_TABLE), cc_pdf_mode="flat", grid_n=GRID_N_STUDY,
                pdf_floor=1e-4, random_seed=42)
            ref = dict(ref)
            ref["pdf_loglike_3dirs"] = [old._pdf_likelihood(dirs0, energy0, TRIAL[k], interp0,
                                                             selected_weights=p0) for k in range(3)]
            ref["emcee_reco_dir"] = r0["reco_dir"]
            ref["emcee_theta_deg"] = r0["single_pass_theta_deg"]
            ref["emcee_omega68_deg"] = r0["omega68_deg"]
            ref["grid_reco_dir"] = g0["reco_dir"]
            ref["grid_theta_deg"] = g0["single_pass_theta_deg"]
            ref["grid_omega68_deg"] = g0["omega68_deg"]
            ref["grid_loglike_3dirs"] = g0["log_like"][np.asarray(ref["grid_idx_3dirs"], dtype=np.int64)]
            stored = REFERENCE[cat]
            check(abs(g0["single_pass_theta_deg"] - stored["grid_theta_deg"]) < 1e-5
                  and abs(r0["single_pass_theta_deg"] - stored["emcee_theta_deg"]) < 0.3,
                  f"cat{cat}: old code on this machine vs stored reference numbers within tolerance "
                  f"(grid d={abs(g0['single_pass_theta_deg'] - stored['grid_theta_deg']):.1e} deg, "
                  f"emcee d={abs(r0['single_pass_theta_deg'] - stored['emcee_theta_deg']):.2e} deg)")
        dirs, energy, ct, true_dir = burst(dev, cat)
        p = p_es_deployed(ct)
        check(dirs.shape[0] == ref["n_selected"],
              f"cat{cat}: n_selected {dirs.shape[0]} == {ref['n_selected']}")

        ll = np.array([_pdf_likelihood(dirs, energy, TRIAL[k], interp, selected_weights=p)
                       for k in range(3)], dtype=np.float64)
        check(np.array_equal(ll, np.asarray(ref["pdf_loglike_3dirs"], dtype=np.float64)),
              f"cat{cat}: _pdf_likelihood at 3 trial directions bit-identical")

        r = reconstruct_burst_direction(selected_dirs=dirs, selected_weights=p,
                                       selected_energies=energy, true_burst_dir=true_dir,
                                       use_emcee=True, emcee_cfg=EMCEE_CFG,
                                       pdf_path=str(ES_TABLE), acceptance_path=None)
        check(np.array_equal(np.asarray(r["reco_dir"], dtype=np.float64),
                             np.asarray(ref["emcee_reco_dir"], dtype=np.float64))
              and r["single_pass_theta_deg"] == ref["emcee_theta_deg"]
              and r["omega68_deg"] == ref["emcee_omega68_deg"],
              f"cat{cat}: reconstruct_burst_direction (emcee) bit-identical "
              f"(theta {r['single_pass_theta_deg']:.9f})")

        g = reconstruct_burst_direction_grid_mixture(
            selected_dirs=dirs, selected_energies=energy, p_es=p, true_burst_dir=true_dir,
            pdf_es_path=str(ES_TABLE), cc_pdf_mode="flat", grid_n=GRID_N_STUDY,
            pdf_floor=1e-4, random_seed=42, acceptance_path=None)
        idx = np.asarray(ref["grid_idx_3dirs"], dtype=np.int64)
        check(np.array_equal(np.asarray(g["reco_dir"], dtype=np.float64),
                             np.asarray(ref["grid_reco_dir"], dtype=np.float64))
              and g["single_pass_theta_deg"] == ref["grid_theta_deg"]
              and g["omega68_deg"] == ref["grid_omega68_deg"]
              and np.array_equal(g["log_like"][idx],
                                 np.asarray(ref["grid_loglike_3dirs"], dtype=np.float64)),
              f"cat{cat}: reconstruct_burst_direction_grid_mixture bit-identical "
              f"(theta {g['single_pass_theta_deg']:.9f}, logL at 3 grid dirs)")
        check(g["extra"]["acceptance_path"] is None and g["extra"]["acceptance_lmax"] is None,
              f"cat{cat}: extras report no acceptance")


# ======================================================================================
def _exact_legendre_moments(rows, cos_edges, lmax, nsub=32):
    """Legendre moments of the same HISTOGRAM density, integrated exactly per bin.

    `legendre_moments_of_rows` uses the midpoint rule (row_k P_l(c_k) dc).  This
    Gauss-Legendre version isolates that approximation from the sphere-integration error.
    """
    x, w = np.polynomial.legendre.leggauss(nsub)
    lo, hi = cos_edges[:-1], cos_edges[1:]
    c = (0.5 * (hi - lo)[:, None] * x[None, :] + 0.5 * (hi + lo)[:, None]).ravel()
    ww = (0.5 * (hi - lo)[:, None] * w[None, :]).ravel()
    pm1, pl = np.ones_like(c), c.copy()
    P = [pm1, pl]
    for l in range(2, lmax + 1):
        pm1, pl = pl, ((2 * l - 1) * c * pl - (l - 1) * pm1) / l
        P.append(pl)
    rep = np.repeat(rows, nsub, axis=1)
    return np.column_stack([(rep * (P[l] * ww)[None, :]).sum(axis=1) for l in range(lmax + 1)])


def check_normalisation(n_sphere=2000000, block=250000):
    print(f"\n(2) NORMALISATION: Z_i(n) == 2 <R(d) m_i(d.n)>_sphere ({n_sphere // 1000}k-point "
          f"integration)")
    acc = load_reco_acceptance(str(ACCEPTANCE))
    lmax = acc["lmax"]
    table = load_pdf_table(str(ES_TABLE), pdf_floor=1e-4)
    edges = np.asarray(table["cos_edges"], dtype=np.float64)
    energies = np.array([5.5, 7.0, 9.0, 13.0, 21.0, 45.0])
    rows = pdf_rows_for_energies(table, energies)                 # (N, n_cos)
    lam = acceptance_moments(table, energies, lmax)               # (N, lmax+1), midpoint rule
    lam_exact = _exact_legendre_moments(rows, edges, lmax)
    check(np.allclose(lam[:, 0], 1.0, atol=1e-12),
          f"lambda_0 == 1 for every row (max |d| = {np.max(np.abs(lam[:, 0] - 1.0)):.2e})")
    print(f"      max |lambda_l midpoint - exact| per l: "
          f"{np.array2string(np.max(np.abs(lam - lam_exact), axis=0), precision=6)}")

    iso = np.zeros_like(acc["coeffs"])
    iso[0] = np.sqrt(4.0 * np.pi)                                 # c_00 Y_00 == 1
    trials = np.vstack([TRIAL, fibonacci_sphere_grid(7)])
    rl_meas = multipole_bands(acc["coeffs"], trials, lmax)
    rl_iso = multipole_bands(iso, trials, lmax)
    z_impl = np.maximum(lam @ rl_meas, Z_FLOOR)                   # (N, n_trial), as in the code
    z_exact = np.maximum(lam_exact @ rl_meas, Z_FLOOR)
    z_iso = np.maximum(lam @ rl_iso, Z_FLOOR)
    check(float(np.max(np.abs(z_iso - 1.0))) < 1e-9,
          f"R == 1 (only the monopole): max |Z - 1| = {np.max(np.abs(z_iso - 1.0)):.2e}")

    # brute force, accumulated in blocks so the (N, n_sphere) row lookup stays small
    acc_sum = np.zeros((rows.shape[0], trials.shape[0]))
    r_lo, r_hi, r_sum, n_done = np.inf, -np.inf, 0.0, 0
    sphere_all = fibonacci_sphere_grid(n_sphere)
    for s in range(0, n_sphere, block):
        sphere = sphere_all[s:s + block]
        r_d = multipole_bands(acc["coeffs"], sphere, lmax).sum(axis=0)
        r_lo, r_hi = min(r_lo, r_d.min()), max(r_hi, r_d.max())
        r_sum += r_d.sum()
        n_done += sphere.shape[0]
        cos_all = np.clip(sphere @ trials.T, -1.0, 1.0)            # (block, n_trial)
        for j in range(trials.shape[0]):
            # histogram evaluation of the row: the density whose Legendre moments lambda_l are
            k = np.clip(np.searchsorted(edges, cos_all[:, j], side="right") - 1, 0,
                        rows.shape[1] - 1)
            acc_sum[:, j] += (r_d[None, :] * rows[:, k]).sum(axis=1)
    z_bf = 2.0 * acc_sum / n_done
    print(f"      band-limited R over the sphere: {r_lo:.4f} - {r_hi:.4f}, "
          f"mean {r_sum / n_done:.6f}")
    rel_impl = float(np.max(np.abs(z_impl - z_bf) / z_bf))
    rel_exact = float(np.max(np.abs(z_exact - z_bf) / z_bf))
    check(rel_impl < 1e-3, f"max relative |Z_impl - Z_bruteforce| = {rel_impl:.2e} < 1e-3")
    check(rel_exact < 3e-4,
          f"with exact per-bin Legendre moments: {rel_exact:.2e} < 3e-4, i.e. the residual above "
          f"is the MIDPOINT rule inside legendre_moments_of_rows, not the model")


def check_hard_cut_equivalence():
    print("\n(2b) mixture.ct_hard_cut == mixture.s_min with p_floor 0 (same posterior)")
    ev = load_collect(EVAL_COLLECT)
    cat = 2
    s = ev["cat"] == cat
    energy, ct = ev["e_reco"][s], ev["ct"][s]
    dirs = normalize_rows(np.column_stack([ev["dx"][s], ev["dy"][s], ev["dz"][s]]))
    true_dir = normalize_vector(np.array([ev["bx"][s][0], ev["by"][s][0], ev["bz"][s][0]]))
    keep = energy > E_CUT
    d_all, e_all, ct_all = dirs[keep], energy[keep], ct[keep]
    p_all = np.where(ct_all >= CT_CUT, p_es_deployed(ct_all), 0.0)      # the s_min form
    m = ct_all >= CT_CUT
    for acc_path in (None, str(ACCEPTANCE)):
        g_soft = _grid_fit(d_all, e_all, p_all, true_dir, acc_path)
        g_hard = _grid_fit(d_all[m], e_all[m], p_all[m], true_dir, acc_path)
        sep = theta_deg(float(np.dot(g_soft["reco_dir"], g_hard["reco_dir"])))
        check(sep < 1e-6, f"acceptance={'yes' if acc_path else 'no '}: hard cut ({int(m.sum())} "
                          f"events) and p_i=0 floor ({d_all.shape[0]} events) agree to "
                          f"{sep:.2e} deg")


# ======================================================================================
def _grid_fit(dirs, energy, p, true_dir, acceptance_path, grid_n=GRID_N_STUDY,
              es_table=None):
    return reconstruct_burst_direction_grid_mixture(
        selected_dirs=dirs, selected_energies=energy, p_es=p, true_burst_dir=true_dir,
        pdf_es_path=str(es_table or ES_TABLE), cc_pdf_mode="flat", grid_n=grid_n, pdf_floor=1e-4,
        random_seed=42, acceptance_path=acceptance_path)


def check_grid_against_study(cats):
    """Both deployed arms against their own offline reference arm, per cat."""
    ev = load_collect(EVAL_COLLECT)
    g = globals()
    out_t050 = {}
    for label, cut, es_key, acc_key, res_key, arm_key in ARMS:
        es, acc = g[es_key], g[acc_key]
        arm = g[arm_key]
        z = np.load(g[res_key], allow_pickle=True)
        print(f"\n(3) GRID PATH, {label}: vs the offline arm {arm} (grid_n={GRID_N_STUDY})")
        ref = {int(c): float(v) for c, v in zip(z["cats"], z[f"cos_{arm}"])}
        ref_n = {int(c): float(v) for c, v in zip(z["cats"], z[f"nsel_{arm}"])}
        d_study, d_deployed = [], []
        print("      cat    n_sel  offline theta  pipeline theta   |d| [deg]   deployed-calib |d|")
        for cat in cats:
            dirs, energy, ct, true_dir = burst(ev, cat, ct_cut=cut)
            g_s = _grid_fit(dirs, energy, p_es_study(ct), true_dir, str(acc), es_table=es)
            g_d = _grid_fit(dirs, energy, p_es_deployed(ct), true_dir, str(acc), es_table=es)
            t_ref = theta_deg(ref[cat])
            d_study.append(abs(g_s["single_pass_theta_deg"] - t_ref))
            d_deployed.append(abs(g_d["single_pass_theta_deg"] - t_ref))
            check(dirs.shape[0] == int(ref_n[cat]), f"cat{cat}: n_selected {dirs.shape[0]} "
                  f"== offline {int(ref_n[cat])}")
            print(f"      {cat:<6d} {dirs.shape[0]:<6d} {t_ref:<14.5f} "
                  f"{g_s['single_pass_theta_deg']:<15.5f} {d_study[-1]:<11.2e} "
                  f"{d_deployed[-1]:.4f}")
            if cut == 0.50:
                out_t050[cat] = (g_s, g_d, t_ref)   # check (4) appends its own fits to this tuple
        check(max(d_study) < 0.05, f"{label}: max |dtheta| vs the offline arm (offline purity "
                                   f"convention) = {max(d_study):.2e} < 0.05 deg")
        print(f"      with the DEPLOYED calibration convention: max |dtheta| = "
              f"{max(d_deployed):.4f} deg, mean {np.mean(d_deployed):.4f} deg "
              f"(p_i differs by up to 0.007; not a code difference)")
    return out_t050


# ======================================================================================
def _weighted_grid_mean(dirs, energy, w, acceptance_path, grid_n=6000, chunk=512):
    """Exact posterior mean of the SAME weighted pseudo-likelihood `_pdf_likelihood` evaluates,
    on an equal-area grid: sum_i w_i log pdf_ES(d_i.n | E_i) [- sum_i w_i log Z_i(n)].

    This is the reference the emcee sampler must reproduce.  It is NOT the mixture likelihood
    the grid path fits -- see check (4b).
    """
    interp = load_pdf_interpolator(str(ES_TABLE), mode="clipped", pdf_floor=1e-4)
    grid = fibonacci_sphere_grid(int(grid_n))
    ll = np.empty(grid.shape[0])
    for s in range(0, grid.shape[0], chunk):
        g = grid[s:s + chunk]
        cos_g = np.clip(dirs @ g.T, -1.0, 1.0)
        pts = np.column_stack([np.repeat(energy, g.shape[0]), cos_g.ravel()])
        ll[s:s + chunk] = w @ np.log(np.maximum(interp(pts), 1e-10)).reshape(cos_g.shape)
    if acceptance_path:
        acc = load_reco_acceptance(acceptance_path)
        lam = acceptance_moments(load_pdf_table(str(ES_TABLE), pdf_floor=1e-4), energy,
                                 acc["lmax"])
        rl = multipole_bands(acc["coeffs"], grid, acc["lmax"])
        ll = ll - (w @ np.log(np.maximum(lam @ rl, Z_FLOOR)))
    post = np.exp(ll - ll.max())
    post /= post.sum()
    return normalize_vector(np.sum(post[:, None] * grid, axis=0))


def check_emcee(cats, grid_out):
    print("\n(4) EMCEE PATH with the acceptance term (deployed config, grid-seeded init; "
          "t=0.50 arm)")
    ev = load_collect(EVAL_COLLECT)
    acc = load_reco_acceptance(str(ACCEPTANCE))
    table = load_pdf_table(str(ES_TABLE), pdf_floor=1e-4)
    # (4.0) the two code paths must build the SAME Z at the same trial direction
    dirs, energy, ct, true_dir = burst(ev, cats[0])
    lam = acceptance_moments(table, energy, acc["lmax"])
    grid = fibonacci_sphere_grid(GRID_N_STUDY)
    j = int(np.argmax(grid @ TRIAL[2]))
    z_emcee = np.maximum(lam @ multipole_bands(acc["coeffs"], grid[j][None, :], acc["lmax"])[:, 0],
                         Z_FLOOR)
    z_grid = np.maximum(lam @ multipole_bands(acc["coeffs"], grid, acc["lmax"])[:, j], Z_FLOOR)
    check(float(np.max(np.abs(z_emcee - z_grid))) < 1e-12,
          f"Z_i(n) identical in the emcee and grid paths at the same direction "
          f"(max |d| = {np.max(np.abs(z_emcee - z_grid)):.2e})")

    print("\n  (4a) emcee vs the EXACT grid posterior mean of its own weighted likelihood")
    print("      cat    emcee+acc  grid(same L)  sep     emcee noacc  grid(same L)  sep")
    d_acc, d_non = [], []
    for cat in cats:
        dirs, energy, ct, true_dir = burst(ev, cat)
        p = p_es_deployed(ct)
        t0 = time.time()
        e_acc = reconstruct_burst_direction(
            selected_dirs=dirs, selected_weights=p, selected_energies=energy,
            true_burst_dir=true_dir, use_emcee=True, emcee_cfg=EMCEE_CFG,
            pdf_path=str(ES_TABLE), acceptance_path=str(ACCEPTANCE))
        e_non = reconstruct_burst_direction(
            selected_dirs=dirs, selected_weights=p, selected_energies=energy,
            true_burst_dir=true_dir, use_emcee=True, emcee_cfg=EMCEE_CFG,
            pdf_path=str(ES_TABLE), acceptance_path=None)
        w_acc = _weighted_grid_mean(dirs, energy, p, str(ACCEPTANCE))
        w_non = _weighted_grid_mean(dirs, energy, p, None)
        s_acc = theta_deg(float(np.dot(e_acc["reco_dir"], w_acc)))
        s_non = theta_deg(float(np.dot(e_non["reco_dir"], w_non)))
        d_acc.append(s_acc)
        d_non.append(s_non)
        check(e_acc["method"] == "emcee+pdf",
              f"cat{cat}: emcee ran with the pdf likelihood ({time.time() - t0:.0f}s)")
        print(f"      {cat:<6d} {e_acc['single_pass_theta_deg']:<10.3f} "
              f"{theta_deg(float(np.dot(w_acc, true_dir))):<13.3f} {s_acc:<7.3f} "
              f"{e_non['single_pass_theta_deg']:<12.3f} "
              f"{theta_deg(float(np.dot(w_non, true_dir))):<13.3f} {s_non:.3f}")
        grid_out[cat] = grid_out[cat] + (e_acc, e_non, w_acc, w_non)
    check(max(d_acc) < 2.5,
          f"WITH the acceptance term the sampler tracks its own exact posterior mean: "
          f"max sep = {max(d_acc):.3f} deg (mean {np.mean(d_acc):.3f})")
    check(max(d_acc) <= max(d_non) + 0.5,
          f"and no worse than WITHOUT it (max sep without = {max(d_non):.3f} deg, "
          f"mean {np.mean(d_non):.3f}): adding the term does not spoil convergence")

    print("\n  (4b) the weighted-emcee model is NOT the deployed mixture model (documented)")
    print("      cat    mixture grid acc  mixture grid noacc  d(grid)   emcee acc  emcee noacc"
          "  d(emcee)")
    n_grid_better, sep_acc, sep_non = 0, [], []
    for cat in cats:
        dirs, energy, ct, true_dir = burst(ev, cat)
        p = p_es_deployed(ct)
        g_acc = grid_out[cat][1]
        g_non = _grid_fit(dirs, energy, p, true_dir, None)
        e_acc, e_non = grid_out[cat][3], grid_out[cat][4]
        dg = g_acc["single_pass_theta_deg"] - g_non["single_pass_theta_deg"]
        de = e_acc["single_pass_theta_deg"] - e_non["single_pass_theta_deg"]
        sep_acc.append(theta_deg(float(np.dot(e_acc["reco_dir"], g_acc["reco_dir"]))))
        sep_non.append(theta_deg(float(np.dot(e_non["reco_dir"], g_non["reco_dir"]))))
        n_grid_better += int(dg < 0)
        print(f"      {cat:<6d} {g_acc['single_pass_theta_deg']:<17.3f} "
              f"{g_non['single_pass_theta_deg']:<19.3f} {dg:<+9.3f} "
              f"{e_acc['single_pass_theta_deg']:<10.3f} {e_non['single_pass_theta_deg']:<12.3f} "
              f"{de:+.3f}")
    check(n_grid_better == len(cats),
          f"the DEPLOYED grid-mixture path improves with the acceptance on "
          f"{n_grid_better}/{len(cats)} cats")
    print(f"      emcee(weighted) to grid(mixture) separation: with the acceptance "
          f"mean {np.mean(sep_acc):.1f} / max {max(sep_acc):.1f} deg; WITHOUT it already "
          f"mean {np.mean(sep_non):.1f} / max {max(sep_non):.1f} deg.")
    print("      EXPECTED, NOT A BUG. `_pdf_likelihood` is a WEIGHTED PSEUDO-LIKELIHOOD,")
    print("      sum_i w_i log pdf_ES(cos_i), not the per-event mixture: it has no flat-CC floor,")
    print("      so a contaminated event pointing away from n costs w_i log(pdf_floor) instead of")
    print("      log((1-p_i)/2), and the two estimators already disagree by degrees WITHOUT any")
    print("      acceptance on this selection.  The DEPLOYED model is the grid-mixture path; the")
    print("      emcee path carries the term exactly (4a) but is a different statistical model")
    print("      and must not be used as a substitute for the mixture.")

# ======================================================================================
def main():
    for p in (ES_TABLE, CALIB, ACCEPTANCE, ES_TABLE_T030, ACCEPTANCE_T030, DEV_COLLECT,
              EVAL_COLLECT, STUDY_CALIB, STUDY_RESULT, STUDY_RESULT_T030):
        if not Path(p).exists():
            raise SystemExit(f"missing input: {p}")
    for f in (ACCEPTANCE, ACCEPTANCE_T030):
        a = load_reco_acceptance(str(f))
        print(f"acceptance: {f.name}, {a['coeffs'].size} coefficients, lmax {a['lmax']}")
    cats = [2, 3, 4, 5, 6]
    t0 = time.time()
    check_bit_identity()
    check_normalisation()
    check_hard_cut_equivalence()
    grid_out = check_grid_against_study(cats)
    check_emcee(cats, grid_out)
    print(f"\n({time.time() - t0:.0f}s)")
    if FAILURES:
        print(f"\n{len(FAILURES)} CHECK(S) FAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        raise SystemExit(1)
    print("\nACCEPTANCE TERM OK")


if __name__ == "__main__":
    main()
