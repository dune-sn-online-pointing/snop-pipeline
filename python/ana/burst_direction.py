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


def load_pdf_interpolator(pdf_path):
    """Load and create interpolator for energy-cosine PDF (compatible with old pipeline)."""
    if pdf_path is None or not Path(pdf_path).exists():
        return None
    
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


def _pdf_likelihood(selected_dirs, selected_energies, true_direction, pdf_interpolator):
    """Compute log-likelihood using PDF (compatible with old pipeline method)."""
    if pdf_interpolator is None or selected_dirs.shape[0] == 0:
        return 0.0
    
    # Compute cosine angles between predicted directions and true direction
    cos_angles = np.clip(selected_dirs @ true_direction, -1.0, 1.0)
    
    # Evaluate PDF for each cluster
    points = np.column_stack([selected_energies, cos_angles])
    pdf_values = pdf_interpolator(points)
    pdf_values = np.maximum(pdf_values, 1e-10)  # Avoid log(0)
    
    return float(np.sum(np.log(pdf_values)))


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
            y_pred = np.asarray(pred_data["y_pred"]).astype(int) if "y_pred" in pred_data else None
            if y_pred_proba.shape[0] != metadata.shape[0]:
                raise ValueError(
                    f"Prediction length mismatch in {pred_file}: {y_pred_proba.shape[0]} vs {metadata.shape[0]}"
                )
            weights = np.clip(y_pred_proba, 0.0, 1.0)
            # Keep weighted-ct aligned with legacy behavior:
            # apply CT selection first, then weight selected clusters by ES probability.
            if y_pred is not None and y_pred.shape[0] == metadata.shape[0]:
                mask = y_pred == 1
            else:
                mask = weights > 0.5
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



def _run_emcee(selected_dirs, selected_weights, selected_energies, true_burst_dir, emcee_cfg, pdf_interpolator=None):
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
            ll = _pdf_likelihood(selected_dirs, selected_energies, direction, pdf_interpolator)
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
        # Convert mean direction to spherical coordinates
        mean_theta, mean_phi = direction_to_angles(mean_electron_dir)
        # Convert to MCMC convention that matches the likelihood function
        # MCMC uses: x=sin(phi)*cos(theta), y=cos(phi), z=sin(phi)*sin(theta)
        # So: phi = arccos(y), theta = atan2(z, x)
        mean_phi_emcee = np.arccos(np.clip(mean_electron_dir[1], -1.0, 1.0))  # y = cos(phi)
        mean_theta_emcee = np.arctan2(mean_electron_dir[2], mean_electron_dir[0])  # atan2(z, x)

        # Initialize walkers with perturbations around mean (using configured sigma)
        rng = np.random.default_rng(random_seed)
        perturbation_rad = prior_sigma_rad  # Use configured prior width
        p0 = np.empty((nwalkers, 2), dtype=np.float64)
        p0[:, 0] = mean_theta_emcee + rng.normal(0, perturbation_rad, nwalkers)  # theta (azimuthal)
        p0[:, 1] = mean_phi_emcee + rng.normal(0, perturbation_rad, nwalkers)   # phi (polar)

        # Ensure phi stays in valid range [0, pi]
        p0[:, 1] = np.clip(p0[:, 1], 1e-6, np.pi - 1e-6)
        # Wrap theta to [-pi, pi]
        p0[:, 0] = (p0[:, 0] + np.pi) % (2 * np.pi) - np.pi

    # Use affine-invariant stretch moves with scale parameter a=3.0 (established method)
    sampler = emcee.EnsembleSampler(nwalkers, 2, _logpost,
                                   moves=[emcee.moves.StretchMove(a=3.0)])
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
        
    # Load PDF if path provided
    pdf_interpolator = None
    if pdf_path is not None:
        pdf_interpolator = load_pdf_interpolator(pdf_path)

    emcee_cfg = emcee_cfg or {}
    if use_emcee:
        try:
            emcee_res = _run_emcee(selected_dirs, selected_weights, selected_energies, 
                                   true_burst_dir, emcee_cfg, pdf_interpolator)
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