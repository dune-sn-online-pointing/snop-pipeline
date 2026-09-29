#!/usr/bin/env python3

from pathlib import Path

import numpy as np

try:
    import emcee
except Exception:
    emcee = None

try:
    from scipy.interpolate import RegularGridInterpolator
    print("Warning: scipy version may be incompatible but will try to use it")
except Exception as e:
    print(f"Failed to import RegularGridInterpolator: {e}")
    RegularGridInterpolator = None

# Detector-frame reco-direction acceptance R(d): the real spherical-harmonic helpers live in
# ana.combo_acceptance (combo study, 28 September 2026, section 8.2).  burst_direction is
# imported both as `ana.burst_direction` (PYTHONPATH = <repo>/python, set by scripts/init.sh
# and inherited by every condor job through test/run_small_sample_pipeline.sh) and, in a
# couple of scripts, as a top-level `burst_direction` with <repo>/python/ana on sys.path; the
# fallback below covers the second case so the import cannot fail at pipeline run time.
try:
    from ana.combo_acceptance import legendre_moments_of_rows, multipole_bands
except ImportError:  # pragma: no cover - import-path fallback only
    import sys as _sys

    _sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from ana.combo_acceptance import legendre_moments_of_rows, multipole_bands

# Z_i(n) = sum_l lambda_l^(i) R_l(n) is floored exactly as in the offline study
# (python/ana/combo_gridfit.py): a band-limited R can dip low and Z must stay positive.
Z_FLOOR = 1e-3


def load_reco_acceptance(path):
    """Detector-frame reco-direction acceptance R(d), <R>_sphere = 1, as real-SH
    coefficients up to lmax (see python/ana/combo_tables.py).  Measured on the
    table-building slice from the selection's TRUE-CC reco directions, which cannot
    know the burst axis.  MUST be rebuilt whenever the ED model, the CT model or the
    selection changes (combo_study.md section 8.4), together with the ES table and the
    P(ES|score) calibration, and the rotated-R null must be re-run each time."""
    z = np.load(path, allow_pickle=True)
    return {"coeffs": np.asarray(z["coeffs"], dtype=np.float64),
            "lmax": int(z["lmax"]), "path": str(path)}


def acceptance_moments(pdf_table, energies, lmax):
    """lambda_l^(i) = int pdf_ES(c | E_i) P_l(c) dc  ->  (N, lmax+1); computed once per fit.

    With the pdf rows in the cos-density convention (integral over c in [-1, 1] equal to 1)
    lambda_0 == 1, so Z_i(n) = sum_l lambda_l^(i) R_l(n) reduces to 1 for R == 1.
    """
    return legendre_moments_of_rows(pdf_rows_for_energies(pdf_table, energies),
                                    pdf_table["cos_centers"], int(lmax))


def load_pdf_interpolator(pdf_path, mode="clipped", pdf_floor=1e-4):
    """Energy-cosine pdf lookup for the burst likelihood.

    mode="clipped" (default since 2026-09-04): the table is floored at `pdf_floor` and
    renormalised per energy row (load_pdf_table), and every query has its energy and
    cosine CLIPPED into the range of the bin centres before bilinear interpolation, so
    an event can never fall outside the grid.

    mode="hole": the pre-fix behaviour, kept for reproducing old results. The
    RegularGridInterpolator spans only the bin CENTRES ([-0.99, 0.99] in cos) and returns
    fill_value=1e-10 outside them, so any event within ~8 deg of the trial direction was
    scored log(1e-10): the likelihood maximum then sits wherever it dodges every event's
    cap, not at the truth (see docs/mixture_ct_scenario7_study.md).
    """
    if pdf_path is None or not Path(pdf_path).exists():
        return None
    if mode == "hole":
        return _load_pdf_interpolator_hole(pdf_path)
    if mode != "clipped":
        raise ValueError(f"unknown pdf lookup mode: {mode!r} (expected 'clipped' or 'hole')")
    try:
        table = load_pdf_table(pdf_path, pdf_floor=pdf_floor)
    except Exception as e:
        print(f"Warning: Failed to load PDF from {pdf_path}: {e}")
        return None
    e_centers = np.asarray(table["energy_centers"], dtype=np.float64)
    c_centers = np.asarray(table["cos_centers"], dtype=np.float64)
    pdf = np.asarray(table["pdf"], dtype=np.float64)
    e_lo, e_hi = float(e_centers[0]), float(e_centers[-1])
    c_lo, c_hi = float(c_centers[0]), float(c_centers[-1])

    if RegularGridInterpolator is not None:
        base = RegularGridInterpolator((e_centers, c_centers), pdf, method='linear',
                                       bounds_error=False, fill_value=None)

        def clipped_interpolator(points):
            pts = np.array(np.atleast_2d(points), dtype=np.float64, copy=True)
            pts[:, 0] = np.clip(pts[:, 0], e_lo, e_hi)
            pts[:, 1] = np.clip(pts[:, 1], c_lo, c_hi)
            return base(pts)

        return clipped_interpolator

    def clipped_bilinear(points):
        pts = np.atleast_2d(np.asarray(points, dtype=np.float64))
        e = np.clip(pts[:, 0], e_lo, e_hi)
        c = np.clip(pts[:, 1], c_lo, c_hi)
        ei = np.clip(np.searchsorted(e_centers, e, side="right"), 1, len(e_centers) - 1)
        ci = np.clip(np.searchsorted(c_centers, c, side="right"), 1, len(c_centers) - 1)
        de = e_centers[ei] - e_centers[ei - 1]
        dc = c_centers[ci] - c_centers[ci - 1]
        fe = np.where(de > 0, (e - e_centers[ei - 1]) / np.where(de > 0, de, 1.0), 0.0)
        fc = np.where(dc > 0, (c - c_centers[ci - 1]) / np.where(dc > 0, dc, 1.0), 0.0)
        p00 = pdf[ei - 1, ci - 1]
        p01 = pdf[ei - 1, ci]
        p10 = pdf[ei, ci - 1]
        p11 = pdf[ei, ci]
        return (p00 * (1 - fe) * (1 - fc) + p01 * (1 - fe) * fc
                + p10 * fe * (1 - fc) + p11 * fe * fc)

    return clipped_bilinear


def _load_pdf_interpolator_hole(pdf_path):
    """Pre-fix lookup (bin-centre grid, fill_value=1e-10 outside). Do not use for new results."""
    try:
        data = np.load(pdf_path)
        pdf_2d = data['pdf_2d']
        energy_bins = data['energy_bins']  # Shape: (N_energy, 2) with [min, max] for each bin
        cosine_bin_centers = data['cosine_bin_centers']
        
        # Create energy bin centers from min/max ranges
        energy_centers = energy_bins.mean(axis=1)
        
        # Try scipy interpolator first
        if RegularGridInterpolator is not None:
            try:
                interpolator = RegularGridInterpolator(
                    (energy_centers, cosine_bin_centers),
                    pdf_2d,
                    method='linear',
                    bounds_error=False,
                    fill_value=1e-10
                )
                return interpolator
            except Exception as e:
                print(f"Warning: scipy interpolator failed ({e}), using simple interpolation")
        
        # Fallback to simple bilinear interpolation
        def simple_interpolator(points):
            """Simple bilinear interpolation fallback."""
            points = np.atleast_2d(points)
            result = np.full(points.shape[0], 1e-10)
            
            for i, (energy, cosine) in enumerate(points):
                # Find nearest energy bin
                e_idx = np.searchsorted(energy_centers, energy)
                e_idx = np.clip(e_idx, 0, len(energy_centers) - 1)
                
                # Find nearest cosine bin  
                c_idx = np.searchsorted(cosine_bin_centers, cosine)
                c_idx = np.clip(c_idx, 0, len(cosine_bin_centers) - 1)
                
                # Simple nearest neighbor for now
                if 0 <= e_idx < pdf_2d.shape[0] and 0 <= c_idx < pdf_2d.shape[1]:
                    result[i] = max(pdf_2d[e_idx, c_idx], 1e-10)
            
            return result
        
        return simple_interpolator
        
    except Exception as e:
        print(f"Warning: Failed to load PDF from {pdf_path}: {e}")
        return None


def _pdf_likelihood(selected_dirs, selected_energies, true_direction, pdf_interpolator,
                    selected_weights=None, acceptance=None, acceptance_moments=None):
    """Weighted log-likelihood sum_i w_i log pdf_ES(cos_i | E_i).

    `selected_weights=None` (or all ones) is the plain sum used by the hard-selection
    scenarios. The weighted-ct scenario passes P(ES) per event; until 2026-09-07 those
    weights never reached the likelihood, so that scenario was an unweighted fit of all
    events.

    `acceptance` (from load_reco_acceptance) adds the detector-frame acceptance
    normalisation of the ES kernel: with p_i(d|n) = m_i(d.n) R(d) / Z_i(n) the per-event
    factor log R(d_i) is independent of the trial direction and drops out of the posterior,
    while -sum_i w_i log Z_i(n) does not.  `acceptance_moments` is the (N, lmax+1) matrix
    of lambda_l^(i) from acceptance_moments(), computed once per fit.  Left at None the
    result is bit-identical to the pre-2026-09-29 likelihood."""
    if pdf_interpolator is None or selected_dirs.shape[0] == 0:
        return 0.0

    # Compute cosine angles between predicted directions and true direction
    cos_angles = np.clip(selected_dirs @ true_direction, -1.0, 1.0)

    # Evaluate PDF for each cluster
    points = np.column_stack([selected_energies, cos_angles])
    pdf_values = pdf_interpolator(points)
    pdf_values = np.maximum(pdf_values, 1e-10)  # Avoid log(0)
    log_pdf = np.log(pdf_values)
    if acceptance is None:
        if selected_weights is None:
            return float(np.sum(log_pdf))
        w = np.asarray(selected_weights, dtype=np.float64)
        return float(np.sum(w * log_pdf))

    if acceptance_moments is None:
        raise ValueError("_pdf_likelihood: acceptance needs acceptance_moments "
                         "(see ana.burst_direction.acceptance_moments)")
    w = (np.ones(log_pdf.shape[0], dtype=np.float64) if selected_weights is None
         else np.asarray(selected_weights, dtype=np.float64))
    ll = float(np.sum(w * log_pdf))
    # p_i(d|n) = m_i(d.n) R(d) / Z_i(n): log R(d_i) is independent of n and drops out,
    # -sum_i w_i log Z_i(n) does not.  Z_i(n) = sum_l lambda_l^(i) R_l(n).
    n_dir = np.asarray(true_direction, dtype=np.float64).reshape(1, 3)
    rl = multipole_bands(acceptance["coeffs"], n_dir, int(acceptance["lmax"]))[:, 0]
    z = np.maximum(np.asarray(acceptance_moments, dtype=np.float64) @ rl, Z_FLOOR)
    ll -= float(np.sum(w * np.log(z)))
    return ll


def normalize_rows(vectors):
    vectors = np.asarray(vectors, dtype=np.float64)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def normalize_vector(vector):
    vector = np.asarray(vector, dtype=np.float64)
    norm = np.linalg.norm(vector)
    if norm == 0:
        return None
    return vector / norm


def direction_to_angles(direction):
    direction = normalize_vector(direction)
    if direction is None:
        return float("nan"), float("nan")
    theta = float(np.arccos(np.clip(direction[2], -1.0, 1.0)))
    phi = float(np.arctan2(direction[1], direction[0]))
    return theta, phi


def angles_to_direction(theta, phi):
    return np.array([
        np.sin(theta) * np.cos(phi),
        np.sin(theta) * np.sin(phi),
        np.cos(theta),
    ], dtype=np.float64)


def angular_error_deg(direction_a, direction_b):
    """Compute angular error in degrees between two direction vectors."""
    a = normalize_vector(direction_a)
    b = normalize_vector(direction_b)
    if a is None or b is None:
        return float("nan")
    cos_theta = np.clip(np.dot(a, b), -1.0, 1.0)
    # Handle both scalar and array cases
    if np.isscalar(cos_theta):
        return float(np.degrees(np.arccos(cos_theta)))
    else:
        return float(np.degrees(np.arccos(cos_theta.item())))


def _resolve_direction_inputs(metadata, direction_mode):
    true_electron_vec = metadata[:, 7:10]
    true_electron_valid = np.linalg.norm(true_electron_vec, axis=1) > 0

    true_burst_vec = metadata[:, 15:18]
    true_burst_valid = np.linalg.norm(true_burst_vec, axis=1) > 0
    if not np.any(true_burst_valid):
        raise ValueError("No valid true burst direction vectors in metadata[:, 15:18]")

    true_burst_dir = normalize_vector(np.mean(normalize_rows(true_burst_vec[true_burst_valid]), axis=0))
    if true_burst_dir is None:
        raise ValueError("Failed to build valid true burst direction")

    direction_mode_used = direction_mode
    if direction_mode == "true":
        electron_dirs = normalize_rows(true_electron_vec)
        electron_valid = true_electron_valid
    elif direction_mode == "reco":
        # Placeholder; caller must provide reconstructed vectors from persisted contract.
        electron_dirs = normalize_rows(true_electron_vec)
        electron_valid = np.zeros(metadata.shape[0], dtype=bool)
    else:
        raise ValueError(f"Unsupported direction_mode: {direction_mode}")

    return electron_dirs, electron_valid, true_burst_dir, direction_mode_used


def _load_reco_dirs_from_run(run_dir: Path, n_rows: int):
    reco_path = Path(run_dir) / "predictions" / "reco_directions.npz"
    if not reco_path.exists():
        return None, None

    data = np.load(reco_path, allow_pickle=True)
    if "reco_dirs" not in data:
        return None, None

    reco_dirs = np.asarray(data["reco_dirs"], dtype=np.float64)
    if reco_dirs.ndim != 2 or reco_dirs.shape[1] != 3:
        return None, None
    if reco_dirs.shape[0] != n_rows:
        return None, None

    reco_dirs = normalize_rows(reco_dirs)
    reco_valid = np.isfinite(reco_dirs).all(axis=1) & (np.linalg.norm(reco_dirs, axis=1) > 0)

    if "has_reco" in data:
        has_reco = np.asarray(data["has_reco"]).astype(bool)
        if has_reco.shape[0] == n_rows:
            reco_valid = reco_valid & has_reco

    return reco_dirs, reco_valid


def select_electrons_from_run(run_dir: Path, selection_mode: str, direction_mode: str, min_energy_mev: float, ct_threshold: float = None, mixture_cfg: dict = None):
    run_dir = Path(run_dir)
    vol_path = run_dir / "volume_images" / "volumes.npz"
    if not vol_path.exists():
        raise FileNotFoundError(f"Missing volumes file: {vol_path}")

    vol_data = np.load(vol_path, allow_pickle=True)
    metadata = np.asarray(vol_data["metadata"], dtype=np.float64)
    if metadata.ndim != 2 or metadata.shape[1] < 18:
        raise ValueError(f"Unexpected metadata shape in {vol_path}: {metadata.shape}")

    electron_dirs, valid_electron, true_burst_dir, direction_mode_used = _resolve_direction_inputs(
        metadata, direction_mode
    )

    if direction_mode == "reco":
        reco_dirs, reco_valid = _load_reco_dirs_from_run(run_dir, metadata.shape[0])
        if reco_dirs is not None and np.any(reco_valid):
            electron_dirs = reco_dirs
            valid_electron = reco_valid
            direction_mode_used = "reco"
        else:
            raise RuntimeError(
                f"direction_mode='reco' requested but reco_directions.npz not found or contains no valid "
                f"directions in {run_dir}/predictions/. "
                "Make sure electron_direction is enabled in the pipeline config."
            )

    # Cluster reconstructed energy (already e3p0-cut upstream in data production).
    energy = metadata[:, 10] if metadata.shape[1] > 10 else np.full(metadata.shape[0], np.nan)

    weights = np.ones(metadata.shape[0], dtype=np.float64)

    if selection_mode == "predicted-es":
        pred_file = run_dir / "predictions" / "channel_predictions.npz"
        if pred_file.exists():
            pred_data = np.load(pred_file, allow_pickle=True)
            # Re-threshold from stored probabilities if a custom threshold is requested,
            # otherwise use the stored binary predictions (baked in at pipeline time).
            if ct_threshold is not None and "y_pred_proba" in pred_data:
                y_pred_proba = np.asarray(pred_data["y_pred_proba"]).astype(float)
                if y_pred_proba.shape[0] != metadata.shape[0]:
                    raise ValueError(
                        f"Prediction length mismatch in {pred_file}: {y_pred_proba.shape[0]} vs {metadata.shape[0]}"
                    )
                mask = y_pred_proba >= ct_threshold
            else:
                y_pred = np.asarray(pred_data["y_pred"]).astype(int)
                if y_pred.shape[0] != metadata.shape[0]:
                    raise ValueError(
                        f"Prediction length mismatch in {pred_file}: {y_pred.shape[0]} vs {metadata.shape[0]}"
                    )
                mask = y_pred == 1
        else:
            mask = metadata[:, 3].astype(int) == 1
    elif selection_mode == "weighted-ct":
        pred_file = run_dir / "predictions" / "channel_predictions.npz"
        if pred_file.exists():
            pred_data = np.load(pred_file, allow_pickle=True)
            y_pred_proba = np.asarray(pred_data["y_pred_proba"]).astype(float)
            if y_pred_proba.shape[0] != metadata.shape[0]:
                raise ValueError(
                    f"Prediction length mismatch in {pred_file}: {y_pred_proba.shape[0]} vs {metadata.shape[0]}"
                )
            # Use ALL events; weight each by P(ES) so CC-like events contribute minimally.
            # No hard threshold — this is the point of weighted-ct vs predicted-es.
            weights = np.clip(y_pred_proba, 0.0, 1.0)
            mask = np.ones(metadata.shape[0], dtype=bool)
        else:
            mask = metadata[:, 3].astype(int) == 1
    elif selection_mode == "true-es":
        mask = metadata[:, 3].astype(int) == 1
    elif selection_mode == "all":
        mask = np.ones(metadata.shape[0], dtype=bool)
    elif selection_mode == "mixture-ct":
        # Scenario 7: keep ALL events with a valid direction (no CT threshold);
        # weights = calibrated P(ES | CT score, class prior), consumed by the
        # grid-mixture likelihood (see reconstruct_burst_direction_grid_mixture).
        mixture_cfg = mixture_cfg or {}
        mask = np.ones(metadata.shape[0], dtype=bool)
        mixture_extra = _mixture_event_probabilities(run_dir, metadata, mixture_cfg)
        weights = mixture_extra["p_es"]
        # Optional HARD CT cut, opt-in through mixture.ct_hard_cut (default None = keep every
        # event, i.e. unchanged).  The r3 re-scan and the combo study both recommend a
        # relaxed hard cut (CT v80 >= 0.50) before the mixture fit.  A hard cut and
        # mixture.s_min with p_floor = 0 give the SAME posterior -- a p_i = 0 event only adds
        # the trial-direction-independent log q_CC -- but the cut keeps n_selected, the
        # reported purity and the cost of the fit honest.
        ct_hard_cut = mixture_cfg.get("ct_hard_cut")
        if ct_hard_cut is not None:
            ct_score_all = mixture_extra["ct_score"]
            if not np.all(np.isfinite(ct_score_all)):
                raise ValueError("mixture.ct_hard_cut needs per-event CT scores "
                                 "(mixture.ct_source must be 'ct')")
            mask = mask & (ct_score_all >= float(ct_hard_cut))
    else:
        raise ValueError(f"Unsupported selection_mode: {selection_mode}")

    if min_energy_mev > 0:
        mask = mask & (energy >= float(min_energy_mev))

    mask = mask & valid_electron

    selected_dirs = electron_dirs[mask]
    selected_weights = weights[mask]
    selected_energy = energy[mask]

    result = {
        "selected_dirs": selected_dirs,
        "selected_weights": selected_weights,
        "selected_energy": selected_energy,
        "n_selected": int(selected_dirs.shape[0]),
        "true_burst_dir": true_burst_dir,
        "direction_mode_used": direction_mode_used,
    }
    if selection_mode == "mixture-ct":
        # per-event side information for the mixture likelihood and for offline re-evaluation
        result["mixture"] = {
            "p_es": mixture_extra["p_es"][mask],
            "ct_score": mixture_extra["ct_score"][mask],
            "is_es_true": metadata[mask, 3].astype(int) == 1,
            "true_electron_dirs": normalize_rows(metadata[mask, 7:10]),
            "true_nu_dirs": normalize_rows(metadata[mask, 15:18]),
            "event_number": metadata[mask, 0].astype(int),
            "true_particle_energy": metadata[mask, 11],
            "pi_used": float(mixture_extra["pi_used"]),
            "pi_mode": str(mixture_extra["pi_mode"]),
            "ct_source": str(mixture_extra["ct_source"]),
            "n_loaded": int(metadata.shape[0]),
            "n_true_es_loaded": int(np.sum(metadata[:, 3].astype(int) == 1)),
        }
    return result


def _weighted_mean_direction(selected_dirs, selected_weights):
    if selected_dirs.size == 0:
        return None
    weighted = np.sum(selected_dirs * selected_weights[:, None], axis=0)
    return normalize_vector(weighted)


def _theta_samples_from_bootstrap(selected_dirs, selected_weights, true_burst_dir, random_seed=42):
    n_selected = selected_dirs.shape[0]
    n_bootstrap = int(min(2000, max(400, 20 * n_selected)))
    rng = np.random.default_rng(random_seed)
    theta_samples = np.empty(n_bootstrap, dtype=np.float64)
    for i in range(n_bootstrap):
        draw_idx = rng.integers(0, n_selected, size=n_selected)
        boot_dirs = selected_dirs[draw_idx]
        boot_weights = selected_weights[draw_idx]
        boot_reco = _weighted_mean_direction(boot_dirs, boot_weights)
        theta_samples[i] = angular_error_deg(boot_reco, true_burst_dir)
    return theta_samples[np.isfinite(theta_samples)]



def _run_emcee(selected_dirs, selected_weights, selected_energies, true_burst_dir, emcee_cfg,
               pdf_interpolator=None, acceptance=None, acceptance_moments=None):
    if emcee is None:
        raise RuntimeError("emcee is required but not available")

    # Use established MCMC parameters: 128 walkers × 500 steps with 100-step burn-in (20%)
    nwalkers = int(emcee_cfg.get("nwalkers", 128))
    nsteps = int(emcee_cfg.get("nsteps", 500))
    discard = int(emcee_cfg.get("discard", 100))
    random_seed = int(emcee_cfg.get("random_seed", 42))

    # Prior configuration
    prior_type = emcee_cfg.get("prior_type", "uniform")
    prior_sigma_deg = float(emcee_cfg.get("prior_sigma_deg", 10.0))
    prior_sigma_rad = np.radians(prior_sigma_deg)

    if nwalkers < 8:
        nwalkers = 8
    if nwalkers % 2 != 0:
        nwalkers += 1
    if discard >= nsteps:
        discard = max(0, nsteps // 5)  # 20% burn-in

    # Calculate mean electron direction for Gaussian prior
    mean_electron_dir = _weighted_mean_direction(selected_dirs, selected_weights)
    if mean_electron_dir is None:
        mean_electron_dir = np.array([0, 0, 1], dtype=np.float64)  # Fallback

    # Prior: Gaussian around mean direction vs uniform on sphere
    def _logprior(args):
        theta, phi = args[0], args[1]
        if theta < -np.pi or theta > np.pi:
            return -np.inf
        if phi < 0 or phi > np.pi:
            return -np.inf

        if prior_type == "gaussian_around_mean":
            # Gaussian prior centered on mean electron direction
            direction = np.array([
                np.sin(phi) * np.cos(theta),
                np.cos(phi),
                np.sin(phi) * np.sin(theta)
            ])
            cos_angle = np.clip(np.dot(direction, mean_electron_dir), -1.0, 1.0)
            angular_distance = np.arccos(cos_angle)

            # Gaussian likelihood in angular distance
            log_gaussian = -0.5 * (angular_distance / prior_sigma_rad) ** 2
            return log_gaussian + np.log(np.sin(phi) + 1e-12)  # Include Jacobian
        else:
            # Uniform prior on sphere (original)
            return np.log(np.sin(phi) + 1e-12)

    def _logpost(args):
        lp = _logprior(args)
        if not np.isfinite(lp):
            return -np.inf

        theta, phi = args[0], args[1]
        # Direction convention matching original:
        # x = sin(phi) * cos(theta)
        # z = sin(phi) * sin(theta)
        # y = cos(phi)
        reco_x = np.sin(phi) * np.cos(theta)
        reco_z = np.sin(phi) * np.sin(theta)
        reco_y = np.cos(phi)
        direction = np.array([reco_x, reco_y, reco_z])

        # Use PDF likelihood (matching original loglike_E_weighted)
        if pdf_interpolator is not None:
            ll = _pdf_likelihood(selected_dirs, selected_energies, direction, pdf_interpolator,
                                 selected_weights=selected_weights, acceptance=acceptance,
                                 acceptance_moments=acceptance_moments)
        else:
            # Fallback to angle-squared likelihood (original loglike without PDF)
            cos_angles = np.clip(selected_dirs @ direction, -1.0, 1.0)
            angles = np.arccos(cos_angles)
            ll = -float(np.sum(angles ** 2))

        return lp + ll

    # Initialize walkers around mean electron direction (calculated earlier for prior)
    if mean_electron_dir is None:
        # Fallback to uniform initialization if mean direction fails
        rng = np.random.default_rng(random_seed)
        p0 = np.empty((nwalkers, 2), dtype=np.float64)
        p0[:, 0] = -np.pi + rng.random(nwalkers) * 2 * np.pi  # theta in [-pi, pi]
        p0[:, 1] = rng.random(nwalkers) * np.pi  # phi in [0, pi]
    else:
        rng = np.random.default_rng(random_seed)
        init_mode = str(emcee_cfg.get("init_mode", "grid"))
        seed_dir = np.asarray(mean_electron_dir, dtype=np.float64)
        if init_mode == "grid" and pdf_interpolator is not None:
            # Seed the walkers at the global maximum of the (weighted) likelihood on an
            # equal-area grid, within init_sigma_deg of it. The legacy 45-deg init around
            # the weighted mean never collapses onto a ~0.5-deg posterior in 500 steps
            # (best case 1.5 -> 0.7 deg on real bursts), while any fixed narrow init
            # around a contaminated mean is worse for the deployed selection; seeding
            # at the grid maximum removes the dependence on the start (2026-09-07).
            grid_n = int(emcee_cfg.get("init_grid_n", 4000))
            grid = fibonacci_sphere_grid(grid_n)
            cos_grid = np.clip(selected_dirs @ grid.T, -1.0, 1.0)  # (N_events, N_grid)
            pts = np.column_stack([np.repeat(selected_energies, grid_n), cos_grid.ravel()])
            log_pdf = np.log(np.maximum(pdf_interpolator(pts), 1e-10)).reshape(cos_grid.shape)
            w = np.asarray(selected_weights, dtype=np.float64)
            ll_grid = w @ log_pdf
            if acceptance is not None:
                # seed at the maximum of the likelihood the sampler actually targets: the
                # -sum_i w_i log Z_i(n) term tilts the surface by O(100) per burst, so the
                # R-free grid maximum is not where the walkers should start.
                rl_seed = multipole_bands(acceptance["coeffs"], grid, int(acceptance["lmax"]))
                z_seed = np.maximum(np.asarray(acceptance_moments, dtype=np.float64) @ rl_seed,
                                    Z_FLOOR)
                ll_grid = ll_grid - (w @ np.log(z_seed))
            i_max = int(np.argmax(ll_grid))
            seed_dir = grid[i_max]
            init_sigma_cfg = emcee_cfg.get("init_sigma_deg", "auto")
            if str(init_sigma_cfg) == "auto":
                # Scale the start to the posterior's own width: the angular radius
                # around the grid maximum that holds 68% of the grid posterior mass,
                # clipped to [init_sigma_min_deg, init_sigma_max_deg]. A peaked
                # posterior (pure sample) gets a tight start, a broad one
                # (contaminated sample) keeps a wide start so the posterior mean is
                # still explored rather than pinned to a spike at the maximum.
                post = np.exp(ll_grid - ll_grid[i_max])
                post /= post.sum()
                ang = np.arccos(np.clip(grid @ seed_dir, -1.0, 1.0))
                order = np.argsort(ang)
                cum = np.cumsum(post[order])
                r68 = float(np.degrees(ang[order][min(int(np.searchsorted(cum, 0.68)), len(order) - 1)]))
                lo = float(emcee_cfg.get("init_sigma_min_deg", 5.0))
                hi = float(emcee_cfg.get("init_sigma_max_deg", 45.0))
                init_sigma_rad = np.radians(min(max(r68, lo), hi))
            else:
                init_sigma_rad = np.radians(float(init_sigma_cfg))
        elif prior_type == "uniform":
            # Legacy: wide init (45°) near the weighted mean direction, so a contaminated
            # mean (up to ~55° from truth) does not lock the walkers.
            init_sigma_rad = np.radians(float(emcee_cfg.get("init_sigma_deg", 45.0)))
        else:
            init_sigma_rad = prior_sigma_rad
        mean_phi_emcee = np.arccos(np.clip(seed_dir[1], -1.0, 1.0))
        mean_theta_emcee = np.arctan2(seed_dir[2], seed_dir[0])
        p0 = np.empty((nwalkers, 2), dtype=np.float64)
        p0[:, 0] = mean_theta_emcee + rng.normal(0, init_sigma_rad, nwalkers)
        p0[:, 1] = mean_phi_emcee + rng.normal(0, init_sigma_rad, nwalkers)
        p0[:, 1] = np.clip(p0[:, 1], 1e-6, np.pi - 1e-6)
        p0[:, 0] = (p0[:, 0] + np.pi) % (2 * np.pi) - np.pi

    # Affine-invariant stretch moves; a=2.0 (default) targets ~23% acceptance.
    # a=3.0 gives ~8-12% which indicates under-mixing.
    stretch_a = float(emcee_cfg.get("stretch_a", 2.0))
    sampler = emcee.EnsembleSampler(nwalkers, 2, _logpost,
                                   moves=[emcee.moves.StretchMove(a=stretch_a)])
    # random_seed used to seed only the walker start positions; emcee itself drew its
    # stretch moves from an unseeded RandomState, so no result was repeatable.
    sampler.random_state = np.random.RandomState(random_seed).get_state()
    sampler.run_mcmc(p0, nsteps, progress=False)

    flat = sampler.get_chain(discard=discard, flat=True)
    if flat.shape[0] == 0:
        raise RuntimeError("emcee produced no post-burn-in samples")

    # Convert samples to Cartesian using same convention as logpost (matching original)
    # flat[:,0] = theta, flat[:,1] = phi
    sample_dirs = np.zeros((flat.shape[0], 3), dtype=np.float64)
    sample_dirs[:, 0] = np.sin(flat[:, 1]) * np.cos(flat[:, 0])  # x = sin(phi)*cos(theta)
    sample_dirs[:, 1] = np.cos(flat[:, 1])  # y = cos(phi)
    sample_dirs[:, 2] = np.sin(flat[:, 1]) * np.sin(flat[:, 0])  # z = sin(phi)*sin(theta)

    # Get mean direction (matching original)
    avg_x = np.mean(sample_dirs[:, 0])
    avg_y = np.mean(sample_dirs[:, 1])
    avg_z = np.mean(sample_dirs[:, 2])
    norm = np.sqrt(avg_x**2 + avg_y**2 + avg_z**2)
    reco_dir = np.array([avg_x/norm, avg_y/norm, avg_z/norm], dtype=np.float64)

    method_name = "emcee"
    if pdf_interpolator is not None:
        method_name = "emcee+pdf"

    return {
        "method": method_name,
        "reco_dir": reco_dir,
        "sample_dirs": sample_dirs,
        "acceptance_fraction": float(np.mean(sampler.acceptance_fraction)),
    }


def reconstruct_burst_direction(
    selected_dirs,
    selected_weights,
    selected_energies, 
    true_burst_dir,
    use_emcee=True,
    emcee_cfg=None,
    pdf_path=None,
    acceptance_path=None,
):
    selected_dirs = np.asarray(selected_dirs, dtype=np.float64)
    selected_weights = np.asarray(selected_weights, dtype=np.float64)
    selected_energies = np.asarray(selected_energies, dtype=np.float64)

    if selected_dirs.shape[0] == 0:
        return {
            "method": "none",
            "reco_dir": None,
            "theta_samples_deg": np.array([], dtype=np.float64),
            "single_pass_theta_deg": float("nan"),
            "omega68_deg": float("nan"),
            "acceptance_fraction": float("nan"),
        }
        
    emcee_cfg = emcee_cfg or {}
    # Load PDF if path provided. "pdf_lookup": "hole" in the emcee config reproduces the
    # pre-2026-09-04 (buggy) lookup; the default is the clipped lookup.
    pdf_interpolator = None
    if pdf_path is not None:
        pdf_interpolator = load_pdf_interpolator(
            pdf_path,
            mode=str(emcee_cfg.get("pdf_lookup", "clipped")),
            pdf_floor=float(emcee_cfg.get("pdf_floor", 1e-4)),
        )
    # Detector-frame acceptance normalisation of the ES kernel (optional; absent =
    # unchanged).  The (N, lmax+1) Legendre moments of the per-event pdf rows are computed
    # ONCE here, before the sampler, not per likelihood call.
    acceptance = load_reco_acceptance(acceptance_path) if acceptance_path else None
    acc_moments = None
    if acceptance is not None:
        if pdf_interpolator is None:
            raise ValueError("acceptance_path needs a usable pdf_path: the acceptance "
                             "normalisation only makes sense for the ES-pdf likelihood")
        acc_moments = acceptance_moments(
            load_pdf_table(pdf_path, pdf_floor=float(emcee_cfg.get("pdf_floor", 1e-4))),
            selected_energies, acceptance["lmax"])
    if use_emcee:
        try:
            emcee_res = _run_emcee(selected_dirs, selected_weights, selected_energies, 
                                   true_burst_dir, emcee_cfg, pdf_interpolator,
                                   acceptance=acceptance, acceptance_moments=acc_moments)
            theta_samples_deg = np.array([
                angular_error_deg(sample_dir, true_burst_dir) for sample_dir in emcee_res["sample_dirs"]
            ], dtype=np.float64)
            theta_samples_deg = theta_samples_deg[np.isfinite(theta_samples_deg)]
            single_pass = angular_error_deg(emcee_res["reco_dir"], true_burst_dir)
            omega68 = float(np.quantile(theta_samples_deg, 0.68)) if theta_samples_deg.size > 0 else float("nan")
            return {
                "method": emcee_res["method"],
                "reco_dir": emcee_res["reco_dir"],
                "theta_samples_deg": theta_samples_deg,
                "single_pass_theta_deg": single_pass,
                "omega68_deg": omega68,
                "acceptance_fraction": emcee_res["acceptance_fraction"],
            }
        except Exception:
            # Keep workflow robust in environments where emcee is missing.
            pass

    reco_dir = _weighted_mean_direction(selected_dirs, selected_weights)
    theta_samples_deg = _theta_samples_from_bootstrap(
        selected_dirs,
        selected_weights,
        true_burst_dir,
        random_seed=int(emcee_cfg.get("random_seed", 42)),
    )
    single_pass = angular_error_deg(reco_dir, true_burst_dir)
    omega68 = float(np.quantile(theta_samples_deg, 0.68)) if theta_samples_deg.size > 0 else float("nan")
    return {
        "method": "weighted-mean+bootstrap" if not use_emcee else "weighted-mean+bootstrap (emcee unavailable)",
        "reco_dir": reco_dir,
        "theta_samples_deg": theta_samples_deg,
        "single_pass_theta_deg": single_pass,
        "omega68_deg": omega68,
        "acceptance_fraction": float("nan"),
    }


# ===========================================================================
# Scenario 7 "mixture-ct": additive helpers (not used by the emcee scenarios)
# ===========================================================================
#
# Likelihood per trial direction n:
#   logL(n) = sum_i log[ p_i pdf_ES(cos_i | E_i) + (1 - p_i) pdf_CC(cos_i | E_i) ],  cos_i = d_i . n
# where p_i = calibrated P(ES | CT score s_i, class prior pi) and both pdfs are proper
# densities in cos on [-1, 1] per energy bin. The posterior (uniform prior on the sphere)
# is evaluated exactly on an equal-area grid; the point estimate is the posterior mean.
#
# Lookup safety: the tables are evaluated with cos AND energy clipped into the table
# range (bin-centre grid), so no event can fall into an out-of-range fill value.
# The emcee scenarios (1-6) keep their historical RegularGridInterpolator behaviour.

_MIXTURE_GOLDEN_ANGLE = np.pi * (3.0 - np.sqrt(5.0))


def load_pdf_table(pdf_path, pdf_floor=1e-4):
    """Load a cosine-energy pdf table (layout of data/cosine_energy_pdf.npz) as plain arrays.

    Each energy row is floored at `pdf_floor` and renormalised to unit integral over
    cos in [-1, 1], so the table is a proper density (zero bins in the raw histogram
    would otherwise give log(0) penalties).
    """
    data = np.load(pdf_path, allow_pickle=True)
    pdf = np.asarray(data["pdf_2d"], dtype=np.float64)
    energy_bins = np.asarray(data["energy_bins"], dtype=np.float64)
    cos_centers = np.asarray(data["cosine_bin_centers"], dtype=np.float64)
    if "cosine_bin_edges" in data:
        cos_edges = np.asarray(data["cosine_bin_edges"], dtype=np.float64)
    else:
        step = cos_centers[1] - cos_centers[0]
        cos_edges = np.concatenate([cos_centers - step / 2.0, [cos_centers[-1] + step / 2.0]])
    widths = cos_edges[1:] - cos_edges[:-1]
    pdf = np.maximum(pdf, float(pdf_floor))
    pdf = pdf / np.sum(pdf * widths[None, :], axis=1, keepdims=True)
    return {
        "pdf": pdf,
        "energy_bins": energy_bins,
        "energy_centers": energy_bins.mean(axis=1),
        "cos_centers": cos_centers,
        "cos_edges": cos_edges,
        "path": str(pdf_path),
    }


def flat_pdf_table(reference_table):
    """A table with the same binning as `reference_table` but isotropic (0.5 everywhere)."""
    out = dict(reference_table)
    out["pdf"] = np.full_like(reference_table["pdf"], 0.5)
    out["path"] = "flat"
    return out


def pdf_rows_for_energies(table, energies):
    """Per-event pdf row (N, n_cos): linear interpolation between energy-bin centres,
    with energies clipped into [first centre, last centre] (no fill value)."""
    e_centers = table["energy_centers"]
    pdf = table["pdf"]
    e = np.clip(np.asarray(energies, dtype=np.float64), e_centers[0], e_centers[-1])
    hi = np.searchsorted(e_centers, e, side="right")
    hi = np.clip(hi, 1, len(e_centers) - 1)
    lo = hi - 1
    denom = e_centers[hi] - e_centers[lo]
    frac = np.where(denom > 0, (e - e_centers[lo]) / np.where(denom > 0, denom, 1.0), 0.0)
    return pdf[lo] * (1.0 - frac)[:, None] + pdf[hi] * frac[:, None]


def eval_pdf_rows(rows, cos_values, cos_centers):
    """Evaluate per-event rows (N, n_cos) at cos_values (N, G) with linear interpolation
    in cos and clipping into [cos_centers[0], cos_centers[-1]]."""
    c0 = cos_centers[0]
    dc = cos_centers[1] - cos_centers[0]
    n_c = cos_centers.shape[0]
    t = (np.clip(cos_values, c0, cos_centers[-1]) - c0) / dc
    idx = np.clip(np.floor(t).astype(np.int64), 0, n_c - 2)
    frac = np.clip(t - idx, 0.0, 1.0)
    v0 = np.take_along_axis(rows, idx, axis=1)
    v1 = np.take_along_axis(rows, idx + 1, axis=1)
    return v0 * (1.0 - frac) + v1 * frac


def fibonacci_sphere_grid(n_points):
    """Equal-area (Fibonacci lattice) grid of unit vectors, shape (n_points, 3)."""
    i = np.arange(n_points, dtype=np.float64)
    z = 1.0 - 2.0 * (i + 0.5) / n_points
    r = np.sqrt(np.maximum(0.0, 1.0 - z * z))
    phi = i * _MIXTURE_GOLDEN_ANGLE
    return np.column_stack([r * np.cos(phi), r * np.sin(phi), z])


def load_ct_calibration(calibration_path):
    """Load data/ct_v80_calibration.npz (see python/ana/build_ct_calibration.py)."""
    data = np.load(calibration_path, allow_pickle=True)
    return {
        "s_grid": np.asarray(data["s_grid"], dtype=np.float64),
        "lr_grid": np.asarray(data["lr_grid"], dtype=np.float64),
        "path": str(calibration_path),
    }


def calibrated_p_es(ct_scores, calibration, pi):
    """P(ES | s, pi) = pi LR(s) / (pi LR(s) + 1 - pi), LR = f_ES(s)/f_CC(s) from the calibration."""
    s = np.clip(np.asarray(ct_scores, dtype=np.float64), 0.0, 1.0)
    lr = np.interp(s, calibration["s_grid"], calibration["lr_grid"])
    pi = float(pi)
    return pi * lr / (pi * lr + (1.0 - pi))


def _mixture_event_probabilities(run_dir, metadata, mixture_cfg):
    """Per-event P(ES) for the mixture likelihood, from the run's stored CT scores.

    mixture_cfg keys (all optional):
      calibration_path : npz from build_ct_calibration.py (required unless ct_source="truth")
      pi_mode          : "truth" (default; run's own true-ES fraction among loaded clusters)
                         or "fixed" (use pi_fixed)
      pi_fixed         : class prior used when pi_mode == "fixed" (default 0.09)
      ct_source        : "ct" (default) or "truth" (p_i = 1 for true ES, 0 otherwise; unit check)
      p_floor          : optional lower bound on p_i (default 0 = none)
      s_min            : optional CT-score floor; events below it get p_i = p_floor (default none)
    """
    run_dir = Path(run_dir)
    n = metadata.shape[0]
    is_es_true = metadata[:, 3].astype(int) == 1
    pi_mode = str(mixture_cfg.get("pi_mode", "truth"))
    if pi_mode == "fixed":
        pi_used = float(mixture_cfg.get("pi_fixed", 0.09))
    elif pi_mode == "truth":
        pi_used = float(np.mean(is_es_true)) if n > 0 else 0.0
    else:
        raise ValueError(f"Unsupported mixture pi_mode: {pi_mode}")
    pi_used = float(np.clip(pi_used, 1e-4, 1.0 - 1e-4))

    ct_source = str(mixture_cfg.get("ct_source", "ct"))
    ct_score = np.full(n, np.nan, dtype=np.float64)
    if ct_source == "truth":
        p_es = is_es_true.astype(np.float64)
    elif ct_source == "ct":
        pred_file = run_dir / "predictions" / "channel_predictions.npz"
        if not pred_file.exists():
            raise FileNotFoundError(f"mixture-ct needs CT scores but {pred_file} is missing")
        pred_data = np.load(pred_file, allow_pickle=True)
        ct_score = np.asarray(pred_data["y_pred_proba"], dtype=np.float64)
        if ct_score.shape[0] != n:
            raise ValueError(f"Prediction length mismatch in {pred_file}: {ct_score.shape[0]} vs {n}")
        calib_path = mixture_cfg.get("calibration_path")
        if not calib_path:
            raise ValueError("mixture-ct needs mixture.calibration_path (or ct_source='truth')")
        calibration = load_ct_calibration(calib_path)
        p_es = calibrated_p_es(ct_score, calibration, pi_used)
        s_min = mixture_cfg.get("s_min")
        p_floor = float(mixture_cfg.get("p_floor", 0.0))
        if s_min is not None:
            p_es = np.where(ct_score >= float(s_min), p_es, p_floor)
        if p_floor > 0:
            p_es = np.maximum(p_es, p_floor)
    else:
        raise ValueError(f"Unsupported mixture ct_source: {ct_source}")

    return {
        "p_es": np.clip(p_es, 0.0, 1.0),
        "ct_score": ct_score,
        "pi_used": pi_used,
        "pi_mode": pi_mode,
        "ct_source": ct_source,
    }


def load_cc_direction_map(map_path):
    """Load data/cc_reco_direction_map.npz (see python/ana/build_cc_direction_map.py)."""
    data = np.load(map_path, allow_pickle=True)
    return {"grid_dirs": np.asarray(data["grid_dirs"], dtype=np.float64), "q": np.asarray(data["q"], dtype=np.float64),
            "path": str(map_path)}


def cc_map_lookup(cc_map, dirs):
    """Per-event CC density q(d_i) (cos-density convention, uniform = 0.5): nearest map grid point."""
    dirs = np.asarray(dirs, dtype=np.float64)
    out = np.empty(dirs.shape[0], dtype=np.float64)
    g = cc_map["grid_dirs"]
    for s in range(0, dirs.shape[0], 4096):
        out[s:s + 4096] = cc_map["q"][np.argmax(dirs[s:s + 4096] @ g.T, axis=1)]
    return out


def grid_mixture_posterior(selected_dirs, selected_energies, p_es, pdf_es_table, pdf_cc_table,
                           grid_n=41253, chunk=4096, cc_const_per_event=None, acceptance=None):
    """Exact posterior of the burst direction on an equal-area sphere grid (uniform prior).

    Per event the mixture density m_i(cos) = p_i pdf_ES(cos|E_i) + (1-p_i) pdf_CC(cos|E_i) is
    tabulated once on the cos-bin centres (energy interpolated, clipped); log m_i is then
    interpolated linearly in cos (clipped into the centre range) for every grid direction.

    With `acceptance` (from load_reco_acceptance) the ES component carries the detector-frame
    acceptance normalisation and the premixed-row trick no longer applies, so a second branch
    evaluates
        m_i(n) = p_i pdf_ES(d_i.n | E_i) / Z_i(n) + (1 - p_i) q_CC,i,
        Z_i(n) = sum_{l<=lmax} lambda_l^(i) R_l(n)
    with the ES row interpolated in the log and q_CC,i the (trial-direction independent) CC
    density of the event.  R(d_i) itself cancels between the two components of the consistent
    common-acceptance model and is therefore not applied (combo_study.md section 3.1).
    `acceptance=None` is bit-identical to the pre-2026-09-29 code.

    Returns (grid_dirs (G,3), log_like (G,), posterior (G,) normalised to sum 1).
    """
    dirs = np.asarray(selected_dirs, dtype=np.float32)
    energies = np.asarray(selected_energies, dtype=np.float64)
    p = np.clip(np.asarray(p_es, dtype=np.float64), 0.0, 1.0)[:, None]
    cos_centers = np.asarray(pdf_es_table["cos_centers"], dtype=np.float64)
    if pdf_cc_table["cos_centers"].shape != cos_centers.shape or not np.allclose(pdf_cc_table["cos_centers"], cos_centers):
        raise ValueError("pdf_ES and pdf_CC tables must share the same cosine binning")
    if cc_const_per_event is not None:
        # CC component = detector-frame density q(d_i): a per-event constant (independent of the trial direction)
        rows_cc = np.asarray(cc_const_per_event, dtype=np.float64)[:, None] * np.ones((1, cos_centers.shape[0]))
    else:
        rows_cc = pdf_rows_for_energies(pdf_cc_table, energies)
    rows_es = pdf_rows_for_energies(pdf_es_table, energies)
    log_rows = None
    if acceptance is None:
        rows = p * rows_es + (1.0 - p) * rows_cc
        log_rows = np.log(np.maximum(rows, 1e-300)).astype(np.float32)  # (N, n_cos)

    grid = fibonacci_sphere_grid(int(grid_n))
    grid32 = grid.astype(np.float32)
    lam = rl_grid = log_rows_es = q_cc = None
    if acceptance is not None:
        lmax = int(acceptance["lmax"])
        lam = legendre_moments_of_rows(rows_es, cos_centers, lmax)          # (N, lmax+1)
        rl_grid = multipole_bands(acceptance["coeffs"], grid, lmax)         # (lmax+1, G)
        log_rows_es = np.log(np.maximum(rows_es, 1e-300)).astype(np.float32)
        if cc_const_per_event is not None:
            q_cc = np.asarray(cc_const_per_event, dtype=np.float64)
        else:
            # The deployed model has a FLAT CC component (0.5); a per-event detector-frame
            # constant is handled above.  A cos-dependent CC table together with the
            # acceptance term was never studied, so refuse it rather than drop it silently.
            if not np.allclose(rows_cc, rows_cc[:, :1]):
                raise ValueError("acceptance is only supported with a flat or per-event "
                                 "constant CC component (cc_pdf_mode 'flat' or 'detector-map')")
            q_cc = np.asarray(rows_cc[:, 0], dtype=np.float64)
    c0 = np.float32(cos_centers[0])
    c_last = np.float32(cos_centers[-1])
    inv_dc = np.float32(1.0 / (cos_centers[1] - cos_centers[0]))
    n_c = cos_centers.shape[0]
    log_like = np.empty(grid.shape[0], dtype=np.float64)
    for start in range(0, grid.shape[0], int(chunk)):
        g = grid32[start:start + chunk]
        t = (np.clip(dirs @ g.T, c0, c_last) - c0) * inv_dc  # (N, g) in [0, n_c-1]
        idx = np.minimum(t.astype(np.int32), n_c - 2)
        frac = t - idx
        if acceptance is None:
            v0 = np.take_along_axis(log_rows, idx, axis=1)
            v1 = np.take_along_axis(log_rows, idx + 1, axis=1)
            log_like[start:start + chunk] = np.sum(v0 + (v1 - v0) * frac, axis=0, dtype=np.float64)
        else:
            v0 = np.take_along_axis(log_rows_es, idx, axis=1)
            v1 = np.take_along_axis(log_rows_es, idx + 1, axis=1)
            g_es = np.exp(v0 + (v1 - v0) * frac)          # pdf_ES(d_i . n), log-interpolated
            z = np.maximum(lam @ rl_grid[:, start:start + chunk], Z_FLOOR)
            m = p * g_es / z + (1.0 - p) * q_cc[:, None]
            log_like[start:start + chunk] = np.sum(np.log(np.maximum(m, 1e-300)), axis=0,
                                                   dtype=np.float64)
    log_post = log_like - np.max(log_like)
    post = np.exp(log_post)
    post /= np.sum(post)
    return grid, log_like, post


def hpd_region_from_grid(post, credible_mass=0.68):
    """Smallest-area highest-posterior-density region on an equal-area grid.

    Returns dict: level (posterior value at the region boundary), n_points, area_sr,
    radius_deg (equivalent angular radius of a cap of the same solid angle), member mask.
    """
    order = np.argsort(post)[::-1]
    csum = np.cumsum(post[order])
    k = int(np.searchsorted(csum, float(credible_mass), side="left")) + 1
    k = min(max(k, 1), post.shape[0])
    level = float(post[order[k - 1]])
    members = np.zeros(post.shape[0], dtype=bool)
    members[order[:k]] = True
    n_grid = post.shape[0]
    area_sr = 4.0 * np.pi * k / n_grid
    cos_r = 1.0 - area_sr / (2.0 * np.pi)
    radius_deg = float(np.degrees(np.arccos(np.clip(cos_r, -1.0, 1.0))))
    return {"level": level, "n_points": k, "area_sr": float(area_sr), "radius_deg": radius_deg,
            "members": members}


def reconstruct_burst_direction_grid_mixture(selected_dirs, selected_energies, p_es, true_burst_dir,
                                             pdf_es_path, pdf_cc_path=None, cc_pdf_mode="table",
                                             grid_n=41253, pdf_floor=1e-4, n_theta_samples=4000,
                                             random_seed=42, credible_mass=0.68, cc_map_path=None,
                                             acceptance_path=None):
    """Scenario-7 aggregation: grid posterior of the ES/CC mixture likelihood.

    Fills the same keys as reconstruct_burst_direction (method, reco_dir, theta_samples_deg,
    single_pass_theta_deg, omega68_deg, acceptance_fraction) plus truth-free credible-region
    fields (hpd68_radius_deg, truth_in_hpd68, map_theta_deg, ...) and the grid posterior.
    """
    selected_dirs = np.asarray(selected_dirs, dtype=np.float64)
    selected_energies = np.asarray(selected_energies, dtype=np.float64)
    p_es = np.asarray(p_es, dtype=np.float64)
    true_burst_dir = normalize_vector(true_burst_dir)
    if selected_dirs.shape[0] == 0:
        return {
            "method": "grid-mixture",
            "reco_dir": None,
            "theta_samples_deg": np.array([], dtype=np.float64),
            "single_pass_theta_deg": float("nan"),
            "omega68_deg": float("nan"),
            "acceptance_fraction": float("nan"),
            "extra": {},
        }

    pdf_es_table = load_pdf_table(pdf_es_path, pdf_floor=pdf_floor)
    cc_const = None
    if cc_pdf_mode == "detector-map":
        # CC component = detector-frame density of CC reco directions, q(d_i) (independent of n)
        if not cc_map_path:
            raise ValueError("cc_pdf_mode='detector-map' needs cc_map_path")
        cc_map = load_cc_direction_map(cc_map_path)
        cc_const = cc_map_lookup(cc_map, selected_dirs)
        pdf_cc_table = flat_pdf_table(pdf_es_table)
        pdf_cc_table["path"] = cc_map["path"]
    elif cc_pdf_mode == "flat" or not pdf_cc_path:
        pdf_cc_table = flat_pdf_table(pdf_es_table)
        cc_pdf_mode = "flat"
    else:
        pdf_cc_table = load_pdf_table(pdf_cc_path, pdf_floor=pdf_floor)
        cc_pdf_mode = "table"

    # Detector-frame acceptance normalisation of the ES kernel (optional; absent = unchanged)
    acceptance = load_reco_acceptance(acceptance_path) if acceptance_path else None

    grid, log_like, post = grid_mixture_posterior(
        selected_dirs, selected_energies, p_es, pdf_es_table, pdf_cc_table, grid_n=grid_n,
        cc_const_per_event=cc_const, acceptance=acceptance,
    )

    mean_dir = normalize_vector(np.sum(post[:, None] * grid, axis=0))
    if mean_dir is None:
        mean_dir = grid[int(np.argmax(post))]
    map_idx = int(np.argmax(post))
    map_dir = grid[map_idx]

    hpd = hpd_region_from_grid(post, credible_mass=credible_mass)
    truth_idx = int(np.argmax(grid @ true_burst_dir))
    truth_in_hpd = bool(hpd["members"][truth_idx])

    rng = np.random.default_rng(int(random_seed))
    sample_idx = rng.choice(post.shape[0], size=int(n_theta_samples), replace=True, p=post)
    sample_dirs = grid[sample_idx]
    theta_samples_deg = np.degrees(np.arccos(np.clip(sample_dirs @ true_burst_dir, -1.0, 1.0)))

    single_pass = angular_error_deg(mean_dir, true_burst_dir)
    omega68 = float(np.quantile(theta_samples_deg, credible_mass)) if theta_samples_deg.size else float("nan")
    # posterior spread about its own mean (truth-free), for reference
    ang_to_mean = np.degrees(np.arccos(np.clip(grid @ mean_dir, -1.0, 1.0)))
    order = np.argsort(ang_to_mean)
    csum = np.cumsum(post[order])
    q68_about_mean = float(ang_to_mean[order][min(int(np.searchsorted(csum, credible_mass)), post.shape[0] - 1)])

    extra = {
        "map_theta_deg": angular_error_deg(map_dir, true_burst_dir),
        "hpd68_radius_deg": hpd["radius_deg"],
        "hpd68_area_sr": hpd["area_sr"],
        "hpd68_n_points": int(hpd["n_points"]),
        "truth_in_hpd68": truth_in_hpd,
        "q68_about_mean_deg": q68_about_mean,
        "grid_n": int(grid.shape[0]),
        "cc_pdf_mode": cc_pdf_mode,
        "pdf_es_path": pdf_es_table["path"],
        "pdf_cc_path": pdf_cc_table["path"],
        "sum_p_es": float(np.sum(p_es)),
        "log_like_max": float(np.max(log_like)),
        "acceptance_path": (acceptance["path"] if acceptance is not None else None),
        "acceptance_lmax": (int(acceptance["lmax"]) if acceptance is not None else None),
    }
    return {
        "method": "grid-mixture",
        "reco_dir": mean_dir,
        "map_dir": map_dir,
        "theta_samples_deg": theta_samples_deg,
        "single_pass_theta_deg": single_pass,
        "omega68_deg": omega68,
        "acceptance_fraction": float("nan"),
        "grid_dirs": grid,
        "posterior": post,
        "log_like": log_like,
        "extra": extra,
    }
