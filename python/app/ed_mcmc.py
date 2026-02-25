#!/usr/bin/env python3
"""
Lightweight MCMC wrapper to refine direction using ED-produced PDFs.

This script expects an input .npz produced by `ed_inference.py` which must contain:
 - `ed_raw`: an array (M, K) or (M, ...) representing the ED model output per selected cluster.
 - `energy`: optional (M,) energies for each selected cluster.
 - `tentative_dirs`: (M,3) unit vectors giving the tentative direction for each selected cluster.

We assume `ed_raw` encodes a binned PDF over angular error (i.e., probability density as a function
of angle between candidate direction and the tentative direction). To interpret `ed_raw` we also
accept a key `angle_bin_centers` present in the .npz; if not present we will create a default
linear binning between 0 and pi with length matching the second axis of `ed_raw`.

The sampler uses a simple Metropolis-Hastings on 3D unit vectors: propose a small Gaussian
perturbation in 3D and renormalize.
"""

import argparse
from pathlib import Path
import numpy as np
from scipy.interpolate import interp1d


def unit_vector_from_angles(theta, phi):
    x = np.sin(theta) * np.cos(phi)
    y = np.sin(theta) * np.sin(phi)
    z = np.cos(theta)
    return np.stack([x, y, z], axis=-1)


def angle_between(u, v):
    # both are (...,3)
    u = u / np.linalg.norm(u, axis=-1, keepdims=True)
    v = v / np.linalg.norm(v, axis=-1, keepdims=True)
    dot = np.sum(u * v, axis=-1)
    dot = np.clip(dot, -1.0, 1.0)
    return np.arccos(dot)


def likelihood_from_pdf(angle, pdf_interp):
    # pdf_interp should be an interpolator returning non-negative values
    val = float(pdf_interp(angle))
    # guard against zero probabilities
    return max(val, 1e-300)


def run_mcmc_for_cluster(tentative_dir, pdf_vals, angle_bin_centers, nsteps=2000, proposal_scale=0.1):
    # Build interpolator
    interp = interp1d(angle_bin_centers, pdf_vals, bounds_error=False, fill_value=1e-300)

    # Initialize chain at tentative_dir
    cur = tentative_dir / np.linalg.norm(tentative_dir)
    cur_angle = 0.0  # angle between tentative and tentative
    cur_like = likelihood_from_pdf(cur_angle, interp)

    chain = np.zeros((nsteps, 3), dtype=float)
    likes = np.zeros(nsteps, dtype=float)

    for i in range(nsteps):
        # propose: add small Gaussian noise in 3D and renormalize
        prop = cur + np.random.normal(scale=proposal_scale, size=3)
        prop = prop / np.linalg.norm(prop)
        ang = angle_between(prop[np.newaxis, :], tentative_dir[np.newaxis, :])[0]
        prop_like = likelihood_from_pdf(ang, interp)

        # MH accept
        if np.random.rand() < (prop_like / cur_like):
            cur = prop
            cur_like = prop_like
            cur_angle = ang

        chain[i] = cur
        likes[i] = cur_like

    return chain, likes


def summarize_chain(chain, likes):
    # Return mean direction (normalize) and best sample
    mean_vec = np.mean(chain, axis=0)
    mean_vec = mean_vec / np.linalg.norm(mean_vec)
    best_idx = np.argmax(likes)
    best_vec = chain[best_idx]
    best_vec = best_vec / np.linalg.norm(best_vec)
    return mean_vec, best_vec


def main():
    p = argparse.ArgumentParser()
    p.add_argument('ed_inference_npz', help='.npz created by ed_inference.py')
    p.add_argument('--out', default='results/ed_mcmc_results.npz')
    p.add_argument('--nsteps', type=int, default=2000)
    p.add_argument('--proposal-scale', type=float, default=0.08, help='Gaussian std dev for 3D proposal')
    args = p.parse_args()

    data = np.load(args.ed_inference_npz)
    if 'ed_raw' not in data:
        raise KeyError('Input file must contain `ed_raw` array')
    ed_raw = data['ed_raw']
    tentative_dirs = data.get('tentative_dirs')
    if tentative_dirs is None:
        raise KeyError('Input file must contain `tentative_dirs` (M,3)')

    # Determine angle bin centers
    angle_centers = data.get('angle_bin_centers')
    if angle_centers is None:
        # assume ed_raw second axis is number of angle bins
        K = ed_raw.shape[1]
        angle_centers = np.linspace(0.0, np.pi, K)

    results = {}
    all_mean = []
    all_best = []
    all_chain_likes = []

    for i in range(ed_raw.shape[0]):
        pdf_vals = ed_raw[i]
        tentative = tentative_dirs[i]
        chain, likes = run_mcmc_for_cluster(tentative, pdf_vals, angle_centers, nsteps=args.nsteps, proposal_scale=args.proposal_scale)
        mean_vec, best_vec = summarize_chain(chain, likes)
        all_mean.append(mean_vec)
        all_best.append(best_vec)
        all_chain_likes.append(likes)

    all_mean = np.asarray(all_mean)
    all_best = np.asarray(all_best)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_path, mean_direction=all_mean, best_direction=all_best, chain_likes=all_chain_likes)
    print(f'Saved MCMC results to {out_path}')


if __name__ == '__main__':
    main()
