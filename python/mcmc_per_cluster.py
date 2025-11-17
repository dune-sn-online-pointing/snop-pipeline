#!/usr/bin/env python3
"""
MCMC sampling for neutrino direction using per-cluster ED predictions.

Uses energy-dependent PDF to weight each cluster's contribution to the likelihood.
The PDF encodes how accurate ED predictions are as a function of cluster energy
and angular error (cosine similarity).

Log-likelihood formula:
    log L(d_proposed) = sum_i log[cos(theta_i) * P(E_i, cos(theta_i))]

where:
    theta_i = angle between d_proposed and d_i (cluster direction from ED)
    cos(theta_i) = dot product (assuming unit vectors)
    P(E_i, cos(theta_i)) = PDF value from cosine_energy_pdf.npz
"""

import argparse
import numpy as np
from scipy.interpolate import interp1d, RectBivariateSpline


def load_energy_cosine_pdf(pdf_file):
    """
    Load the 2D PDF: P(cosine, energy).
    
    Returns:
        interpolator: Function that takes (energy, cosine) -> pdf_value
        energy_bins: Energy bin edges
        cosine_bins: Cosine bin centers
    """
    data = np.load(pdf_file)
    pdf_2d = data['pdf_2d']  # Shape: (n_energy_bins, n_cosine_bins)
    energy_bins = data['energy_bins']  # Shape: (n_energy_bins, 2) - [min, max] per bin
    cosine_centers = data['cosine_bin_centers']  # Shape: (n_cosine_bins,)
    
    # Get energy bin centers
    energy_centers = energy_bins.mean(axis=1)
    
    # Create 2D interpolator
    # RectBivariateSpline expects (x, y, z) where z[i,j] = f(x[i], y[j])
    # We have pdf_2d[energy_idx, cosine_idx]
    interpolator = RectBivariateSpline(
        energy_centers, cosine_centers, pdf_2d,
        kx=1, ky=1  # Linear interpolation
    )
    
    return interpolator, energy_centers, cosine_centers


def compute_likelihood(proposed_dir, cluster_dirs, cluster_energies, pdf_interp, energy_range, cosine_range):
    """
    Compute likelihood for a proposed neutrino direction.
    
    Args:
        proposed_dir: (3,) unit vector - proposed neutrino direction
        cluster_dirs: (N, 3) unit vectors - ED-predicted directions for each cluster
        cluster_energies: (N,) cluster energies in MeV
        pdf_interp: Interpolator function (energy, cosine) -> pdf_value
        energy_range: (min, max) valid energy range
        cosine_range: (min, max) valid cosine range
    
    Returns:
        log_likelihood: scalar
    """
    # Compute cosine between proposed and each cluster direction
    cosines = np.dot(cluster_dirs, proposed_dir)  # (N,)
    cosines = np.clip(cosines, -1.0, 1.0)
    
    # Clip energies and cosines to valid range
    energies_clipped = np.clip(cluster_energies, energy_range[0], energy_range[1])
    cosines_clipped = np.clip(cosines, cosine_range[0], cosine_range[1])
    
    # Get PDF values for each cluster
    log_likelihood = 0.0
    for i in range(len(cluster_dirs)):
        energy = energies_clipped[i]
        cosine = cosines_clipped[i]
        
        # PDF value
        pdf_val = float(pdf_interp(energy, cosine, grid=False))
        pdf_val = max(pdf_val, 1e-300)  # Avoid log(0)
        
        # Likelihood contribution: cosine * pdf_value
        # Using cosine as prior (more aligned = more likely)
        # PDF encodes reliability of ED at this energy/angle
        likelihood_contrib = max(cosine, 0.0) * pdf_val  # Only positive cosines
        likelihood_contrib = max(likelihood_contrib, 1e-300)
        
        log_likelihood += np.log(likelihood_contrib)
    
    return log_likelihood


def random_direction_3d():
    """Generate a random unit vector in 3D (uniform on sphere)."""
    vec = np.random.randn(3)
    return vec / np.linalg.norm(vec)


def propose_direction(current_dir, proposal_scale=0.1):
    """
    Propose a new direction near the current one.
    
    Uses a Gaussian perturbation in tangent space.
    """
    # Generate random perturbation perpendicular to current direction
    perturb = np.random.randn(3) * proposal_scale
    new_dir = current_dir + perturb
    new_dir = new_dir / np.linalg.norm(new_dir)
    return new_dir


def run_mcmc_for_event(
    cluster_dirs, cluster_energies, tentative_dir,
    pdf_interp, energy_range, cosine_range,
    nsteps=2000, proposal_scale=0.1
):
    """
    Run MCMC to find best neutrino direction for one event.
    
    Returns:
        chain: (nsteps, 3) array of sampled directions
        log_likes: (nsteps,) array of log-likelihoods
    """
    chain = np.zeros((nsteps, 3))
    log_likes = np.zeros(nsteps)
    
    # Initialize
    current_dir = tentative_dir / np.linalg.norm(tentative_dir)
    current_loglike = compute_likelihood(
        current_dir, cluster_dirs, cluster_energies,
        pdf_interp, energy_range, cosine_range
    )
    
    n_accept = 0
    
    for step in range(nsteps):
        # Propose new direction
        proposed_dir = propose_direction(current_dir, proposal_scale)
        proposed_loglike = compute_likelihood(
            proposed_dir, cluster_dirs, cluster_energies,
            pdf_interp, energy_range, cosine_range
        )
        
        # Metropolis-Hastings acceptance
        log_ratio = proposed_loglike - current_loglike
        if log_ratio > 0 or np.random.rand() < np.exp(log_ratio):
            current_dir = proposed_dir
            current_loglike = proposed_loglike
            n_accept += 1
        
        chain[step] = current_dir
        log_likes[step] = current_loglike
    
    accept_rate = n_accept / nsteps
    return chain, log_likes, accept_rate


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('ed_results', help='NPZ with per-cluster ED predictions')
    p.add_argument('pdf_file', help='NPZ with energy-cosine PDF (cosine_energy_pdf.npz)')
    p.add_argument('--out', default='results/mcmc_directions.npz')
    p.add_argument('--nsteps', type=int, default=2000, help='MCMC steps per event')
    p.add_argument('--proposal-scale', type=float, default=0.1, help='Gaussian proposal scale')
    p.add_argument('--burnin', type=int, default=500, help='Burn-in steps to discard')
    
    args = p.parse_args()
    
    # Load energy-cosine PDF
    print(f"Loading energy-cosine PDF from: {args.pdf_file}")
    pdf_interp, energy_centers, cosine_centers = load_energy_cosine_pdf(args.pdf_file)
    energy_range = (energy_centers.min(), energy_centers.max())
    cosine_range = (cosine_centers.min(), cosine_centers.max())
    print(f"  Energy range: [{energy_range[0]:.1f}, {energy_range[1]:.1f}] MeV")
    print(f"  Cosine range: [{cosine_range[0]:.3f}, {cosine_range[1]:.3f}]")
    
    # Load ED per-cluster results
    print(f"\nLoading ED cluster predictions from: {args.ed_results}")
    ed_data = np.load(args.ed_results, allow_pickle=True)
    events = ed_data['events']
    cluster_directions = ed_data['cluster_directions']  # Object array of (N_i, 3) arrays
    cluster_energies = ed_data['cluster_energies']  # Object array of (N_i,) arrays
    tentative_dirs = ed_data.get('tentative_dirs')  # Optional: (n_events, 3)
    
    n_events = len(events)
    print(f"  Found {n_events} events")
    
    # Run MCMC for each event
    print(f"\nRunning MCMC ({args.nsteps} steps per event, burn-in={args.burnin})...")
    
    results = {
        'events': events,
        'chains': [],
        'log_likelihoods': [],
        'best_directions': [],
        'mean_directions': [],
        'accept_rates': []
    }
    
    for i, event in enumerate(events):
        cluster_dirs = cluster_directions[i]  # (N_clusters, 3)
        cluster_energs = cluster_energies[i]  # (N_clusters,)
        
        # Initial guess: use tentative direction or mean of cluster directions
        if tentative_dirs is not None:
            init_dir = tentative_dirs[i]
        else:
            init_dir = cluster_dirs.mean(axis=0)
        init_dir = init_dir / np.linalg.norm(init_dir)
        
        # Run MCMC
        chain, log_likes, accept_rate = run_mcmc_for_event(
            cluster_dirs, cluster_energs, init_dir,
            pdf_interp, energy_range, cosine_range,
            nsteps=args.nsteps, proposal_scale=args.proposal_scale
        )
        
        # Discard burn-in
        chain_post = chain[args.burnin:]
        log_likes_post = log_likes[args.burnin:]
        
        # Best direction: MAP estimate (highest likelihood)
        best_idx = np.argmax(log_likes_post)
        best_dir = chain_post[best_idx]
        
        # Mean direction (posterior mean)
        mean_dir = chain_post.mean(axis=0)
        mean_dir = mean_dir / np.linalg.norm(mean_dir)
        
        results['chains'].append(chain)
        results['log_likelihoods'].append(log_likes)
        results['best_directions'].append(best_dir)
        results['mean_directions'].append(mean_dir)
        results['accept_rates'].append(accept_rate)
        
        if (i + 1) % 10 == 0 or i == n_events - 1:
            print(f"  Processed {i+1}/{n_events} events (accept rate: {accept_rate:.1%})")
    
    # Save results
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    np.savez_compressed(
        out_path,
        events=results['events'],
        chains=np.array(results['chains'], dtype=object),
        log_likelihoods=np.array(results['log_likelihoods'], dtype=object),
        best_directions=np.array(results['best_directions']),
        mean_directions=np.array(results['mean_directions']),
        accept_rates=np.array(results['accept_rates']),
        nsteps=args.nsteps,
        burnin=args.burnin,
        proposal_scale=args.proposal_scale
    )
    
    print(f"\nSaved MCMC results to: {out_path}")
    print(f"  Mean acceptance rate: {np.mean(results['accept_rates']):.1%}")


if __name__ == '__main__':
    from pathlib import Path
    main()
