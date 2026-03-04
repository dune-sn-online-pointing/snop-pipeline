#!/usr/bin/env python3

from pathlib import Path

import numpy as np

try:
    import emcee
except Exception:
    emcee = None


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
    a = normalize_vector(direction_a)
    b = normalize_vector(direction_b)
    if a is None or b is None:
        return float("nan")
    cos_theta = float(np.clip(np.dot(a, b), -1.0, 1.0))
    return float(np.degrees(np.arccos(cos_theta)))


def _resolve_direction_inputs(metadata, direction_mode):
    # metadata column convention in current pipeline outputs:
    # 4:7  -> true electron momentum vector
    # 7:10 -> reconstructed main-track momentum vector
    # 15:18 -> true burst direction vector
    true_electron_vec = metadata[:, 4:7]
    reco_electron_vec = metadata[:, 7:10]
    true_electron_valid = np.linalg.norm(true_electron_vec, axis=1) > 0
    reco_electron_valid = np.linalg.norm(reco_electron_vec, axis=1) > 0

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
        valid_mask = true_electron_valid
    elif direction_mode == "reco":
        electron_dirs = normalize_rows(reco_electron_vec)
        valid_mask = reco_electron_valid
    else:
        raise ValueError(f"Unsupported direction_mode: {direction_mode}")

    if not np.any(valid_mask):
        raise ValueError(f"No valid {direction_mode} electron direction vectors")

    return electron_dirs, valid_mask, true_burst_dir, direction_mode_used


def select_electrons_from_run(run_dir: Path, selection_mode: str, direction_mode: str, min_energy_mev: float):
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

    # Cluster reconstructed energy (already e3p0-cut upstream in data production).
    energy = metadata[:, 10] if metadata.shape[1] > 10 else np.full(metadata.shape[0], np.nan)

    weights = np.ones(metadata.shape[0], dtype=np.float64)

    if selection_mode == "predicted-es":
        pred_file = run_dir / "predictions" / "channel_predictions.npz"
        if pred_file.exists():
            pred_data = np.load(pred_file, allow_pickle=True)
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
            weights = np.clip(y_pred_proba, 0.0, 1.0)
            mask = np.ones(metadata.shape[0], dtype=bool)
        else:
            mask = metadata[:, 3].astype(int) == 1
    elif selection_mode == "true-es":
        mask = metadata[:, 3].astype(int) == 1
    elif selection_mode == "all":
        mask = np.ones(metadata.shape[0], dtype=bool)
    else:
        raise ValueError(f"Unsupported selection_mode: {selection_mode}")

    if min_energy_mev > 0:
        mask = mask & (energy >= float(min_energy_mev))

    mask = mask & valid_electron

    selected_dirs = electron_dirs[mask]
    selected_weights = weights[mask]
    selected_energy = energy[mask]

    return {
        "selected_dirs": selected_dirs,
        "selected_weights": selected_weights,
        "selected_energy": selected_energy,
        "n_selected": int(selected_dirs.shape[0]),
        "true_burst_dir": true_burst_dir,
        "direction_mode_used": direction_mode_used,
    }


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


def _run_emcee(selected_dirs, selected_weights, emcee_cfg):
    if emcee is None:
        raise RuntimeError("emcee is required but not available")

    nwalkers = int(emcee_cfg.get("nwalkers", 64))
    nsteps = int(emcee_cfg.get("nsteps", 2000))
    discard = int(emcee_cfg.get("discard", 400))
    prior_kappa = float(emcee_cfg.get("prior_kappa", 25.0))
    likelihood_kappa = float(emcee_cfg.get("likelihood_kappa", 25.0))
    random_seed = int(emcee_cfg.get("random_seed", 42))

    if nwalkers < 8:
        nwalkers = 8
    if nwalkers % 2 != 0:
        nwalkers += 1
    if discard >= nsteps:
        discard = max(0, nsteps // 4)

    prior_center = _weighted_mean_direction(selected_dirs, selected_weights)
    if prior_center is None:
        raise ValueError("Cannot build prior center from empty selected directions")

    def _logprior(theta_phi):
        theta, phi = theta_phi
        if theta < 0 or theta > np.pi:
            return -np.inf
        if phi < -np.pi or phi > np.pi:
            return -np.inf
        direction = angles_to_direction(theta, phi)
        # sin(theta): uniform over sphere; vMF-like concentration around weighted mean
        return np.log(np.sin(theta) + 1e-12) + prior_kappa * float(np.dot(direction, prior_center))

    def _logpost(theta_phi):
        lp = _logprior(theta_phi)
        if not np.isfinite(lp):
            return -np.inf
        direction = angles_to_direction(theta_phi[0], theta_phi[1])
        align = np.clip(selected_dirs @ direction, -1.0, 1.0)
        ll = likelihood_kappa * float(np.sum(selected_weights * align))
        return lp + ll

    theta0, phi0 = direction_to_angles(prior_center)
    rng = np.random.default_rng(random_seed)
    p0 = np.empty((nwalkers, 2), dtype=np.float64)
    p0[:, 0] = np.clip(theta0 + rng.normal(0, 0.15, nwalkers), 1e-5, np.pi - 1e-5)
    p0[:, 1] = ((phi0 + rng.normal(0, 0.15, nwalkers) + np.pi) % (2 * np.pi)) - np.pi

    sampler = emcee.EnsembleSampler(nwalkers, 2, _logpost, moves=emcee.moves.StretchMove())
    sampler.run_mcmc(p0, nsteps, progress=False)

    flat = sampler.get_chain(discard=discard, flat=True)
    if flat.shape[0] == 0:
        raise RuntimeError("emcee produced no post-burn-in samples")

    sample_dirs = np.array([angles_to_direction(t, p) for t, p in flat], dtype=np.float64)
    reco_dir = normalize_vector(np.mean(sample_dirs, axis=0))
    if reco_dir is None:
        raise RuntimeError("Failed to build reconstructed direction from emcee samples")

    return {
        "method": "emcee",
        "reco_dir": reco_dir,
        "sample_dirs": sample_dirs,
        "acceptance_fraction": float(np.mean(sampler.acceptance_fraction)),
    }


def reconstruct_burst_direction(
    selected_dirs,
    selected_weights,
    true_burst_dir,
    use_emcee=True,
    emcee_cfg=None,
):
    selected_dirs = np.asarray(selected_dirs, dtype=np.float64)
    selected_weights = np.asarray(selected_weights, dtype=np.float64)

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
    if use_emcee:
        try:
            emcee_res = _run_emcee(selected_dirs, selected_weights, emcee_cfg)
            theta_samples_deg = np.array([
                angular_error_deg(sample_dir, true_burst_dir) for sample_dir in emcee_res["sample_dirs"]
            ], dtype=np.float64)
            theta_samples_deg = theta_samples_deg[np.isfinite(theta_samples_deg)]
            single_pass = angular_error_deg(emcee_res["reco_dir"], true_burst_dir)
            omega68 = float(np.quantile(theta_samples_deg, 0.68)) if theta_samples_deg.size > 0 else float("nan")
            return {
                "method": "emcee",
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