#!/usr/bin/env python3
"""
Detector-frame density map of ED reco directions for CC clusters, q(d), for the mixture-ct
scenario ("cc_pdf_mode": "detector-map").

For a fixed burst the CC component of the mixture must be the density of CC reco directions
on the detector sphere (independent of the burst direction). Measured on the isotropic prod_cc
pool (build_cc_cosine_pdf.py --events-out), it is far from uniform (about 2x excess along +-y),
and using a flat 0.5 instead lets the CC excess masquerade as ES signal and pulls the posterior
toward the vertical axis.

Map: von Mises-Fisher kernel density on an equal-area Fibonacci grid, normalised so that the
mean over the sphere is 1; q(d) = 0.5 * relative density (0.5 = uniform in the cos-density
convention of the pdf tables).

Usage:
  python3 python/ana/build_cc_direction_map.py --events /eos/.../cc_ed_events.npz \
      --out data/cc_reco_direction_map.npz --png data/cc_reco_direction_map.png [--kappa 30] [--grid-n 4000]
"""
import argparse
from pathlib import Path
import sys

import numpy as np

python_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(python_root))
from ana.burst_direction import fibonacci_sphere_grid  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", required=True, help="npz with reco_dirs (+ valid) from build_cc_cosine_pdf.py --events-out")
    ap.add_argument("--out", required=True)
    ap.add_argument("--png", default=None)
    ap.add_argument("--kappa", type=float, default=30.0, help="vMF kernel concentration (30 ~ 10 deg smoothing)")
    ap.add_argument("--grid-n", type=int, default=4000)
    ap.add_argument("--min-energy", type=float, default=0.0)
    args = ap.parse_args()

    d = np.load(args.events, allow_pickle=True)
    dirs = np.asarray(d["reco_dirs"], dtype=np.float64)
    ok = np.asarray(d["valid"], dtype=bool) if "valid" in d else np.ones(len(dirs), bool)
    if args.min_energy > 0 and "energy_reco" in d:
        ok &= np.asarray(d["energy_reco"], float) >= args.min_energy
    dirs = dirs[ok]
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
    grid = fibonacci_sphere_grid(args.grid_n)
    # kernel density: sum_i exp(kappa (d_i . g)) in chunks
    dens = np.zeros(grid.shape[0])
    for s in range(0, len(dirs), 5000):
        dens += np.exp(args.kappa * (grid @ dirs[s:s + 5000].T) - args.kappa).sum(axis=1)
    rel = dens / dens.mean()  # mean over equal-area grid = 1
    q = 0.5 * rel
    T = (dirs.T @ dirs) / len(dirs)
    w, U = np.linalg.eigh(T)
    axes = {"+x": [1, 0, 0], "-x": [-1, 0, 0], "+y": [0, 1, 0], "-y": [0, -1, 0], "+z": [0, 0, 1], "-z": [0, 0, -1]}
    print(f"{len(dirs)} CC reco directions; inertia eigenvalues {np.round(w, 3)} (iso 0.333)")
    print(f"relative density: min {rel.min():.3f} max {rel.max():.3f} at {np.round(grid[np.argmax(rel)], 3)}; "
          + ", ".join(f"{k}: {rel[np.argmax(grid @ np.asarray(v, float))]:.2f}" for k, v in axes.items()))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    np.savez(args.out, grid_dirs=grid.astype(np.float32), q=q.astype(np.float32), relative_density=rel.astype(np.float32),
             kappa=args.kappa, grid_n=args.grid_n, n_events=len(dirs), source=str(args.events),
             note="q(d) = 0.5 * relative detector-frame density of CC ED reco directions (vMF kernel), uniform = 0.5")
    print(f"saved {args.out}")
    if args.png:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        theta = np.degrees(np.arccos(np.clip(grid[:, 1], -1, 1)))  # polar angle from +y (vertical)
        phi = np.degrees(np.arctan2(grid[:, 2], grid[:, 0]))
        fig, ax = plt.subplots(1, 2, figsize=(14, 5))
        sc = ax[0].scatter(phi, 90 - theta, c=rel, s=6, cmap="viridis")
        ax[0].set_xlabel("azimuth in x-z plane [deg]  (atan2(z, x))")
        ax[0].set_ylabel("elevation from x-z plane toward +y [deg]")
        ax[0].set_title("CC reco-direction relative density (detector frame)")
        plt.colorbar(sc, ax=ax[0], label="density / isotropic")
        ax[1].hist(rel, bins=50)
        ax[1].set_xlabel("relative density")
        ax[1].set_title(f"kappa={args.kappa}, grid {args.grid_n}, N={len(dirs)}")
        fig.tight_layout()
        fig.savefig(args.png, dpi=120)
        print(f"saved {args.png}")


if __name__ == "__main__":
    main()
