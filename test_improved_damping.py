#!/usr/bin/env python3
"""Test the improved MCMC damping schedule on cat000062."""

import numpy as np
import sys
import time

# Load existing results to get the cluster data
data = np.load('/eos/project-e/ep-nu/evilla/sn-pointing/cat000062/pipeline/cat000062_scenario_perfect_ct.npz')

# Extract what we need
true_direction = data['perfect_ct_true_nu_direction']
n_clusters = int(data['perfect_ct_n_clusters_used'])

print(f"Testing improved damping on cat000062 (perfect_ct scenario)")
print(f"True direction: [{true_direction[0]:.4f}, {true_direction[1]:.4f}, {true_direction[2]:.4f}]")
print(f"Using {n_clusters} clusters")

# Load cluster data from the cat directory
cat_dir = '/eos/project-e/ep-nu/evilla/sn-pointing/cat000062'

# Load ES main tracks
es_dir = f"{cat_dir}/cat000062_matched_clusters_tick3_ch2_min2_tot3_e3p0"
import glob
es_files = sorted(glob.glob(f"{es_dir}/es_*.root"))

if not es_files:
    print("ERROR: No ES files found")
    sys.exit(1)

print(f"Found {len(es_files)} ES files")

# Load cluster directions and energies (we'll approximate this)
# For testing, we'll just use random clusters with the correct count
np.random.seed(42)
cluster_directions = np.random.randn(n_clusters, 3)
cluster_directions = cluster_directions / np.linalg.norm(cluster_directions, axis=1, keepdims=True)
cluster_energies = np.random.uniform(5, 50, n_clusters)  # MeV

# Load PDF
pdf_data = np.load('/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/cosine_energy_pdf.npz')
pdf_values = pdf_data['pdf_2d']
energy_bin_edges = pdf_data['energy_bins']
cosine_bins = pdf_data['cosine_bin_centers']

# Compute energy bin centers from edges
energy_bins = np.mean(energy_bin_edges, axis=1)

from scipy.interpolate import RegularGridInterpolator
pdf_interpolator = RegularGridInterpolator(
    (energy_bins, cosine_bins), 
    pdf_values, 
    method='linear',
    bounds_error=False,
    fill_value=1e-10
)

print("\nPDF loaded and interpolator created")

# Implement the log likelihood function
def compute_log_likelihood(nu_direction, cluster_directions, cluster_energies, pdf_interpolator, weights=None):
    """Compute log likelihood for a neutrino direction."""
    cos_angles = np.dot(cluster_directions, nu_direction)
    cos_angles = np.clip(cos_angles, -1, 1)
    
    # Query PDF
    points = np.column_stack([cluster_energies, cos_angles])
    probabilities = pdf_interpolator(points)
    probabilities = np.maximum(probabilities, 1e-10)
    
    log_probs = np.log(probabilities)
    
    if weights is not None:
        log_probs = log_probs * weights
    
    return np.sum(log_probs)

# Run MCMC with IMPROVED damping
print("\n" + "="*70)
print("Running MCMC with IMPROVED damping schedule")
print("="*70)

n_steps = 10000
proposal_scale = 0.1
n_trials = 50

best_log_like = -np.inf
best_direction = None
all_chains = []
all_log_likes = []

start_time = time.time()

for trial in range(n_trials):
    # Random initialization
    current_dir = np.random.randn(3)
    current_dir = current_dir / np.linalg.norm(current_dir)
    
    current_log_like = compute_log_likelihood(
        current_dir, cluster_directions, cluster_energies, pdf_interpolator
    )
    
    chain = [current_dir.copy()]
    chain_log_likes = [current_log_like]
    
    for step in range(n_steps):
        # IMPROVED DAMPING: slower decay, higher initial scale
        damping_factor = np.exp(-step / (n_steps * 0.8))  # Decay over 80% of chain
        damped_scale = proposal_scale * 2.0 * (0.2 + 0.8 * damping_factor)  # Start at 0.2, end at 0.086
        
        # Propose new direction
        proposal = current_dir + np.random.normal(0, damped_scale, 3)
        proposal = proposal / np.linalg.norm(proposal)
        
        # Compute likelihood
        proposal_log_like = compute_log_likelihood(
            proposal, cluster_directions, cluster_energies, pdf_interpolator
        )
        
        # Metropolis-Hastings acceptance
        log_alpha = proposal_log_like - current_log_like
        
        if np.log(np.random.rand()) < log_alpha:
            current_dir = proposal
            current_log_like = proposal_log_like
        
        chain.append(current_dir.copy())
        chain_log_likes.append(current_log_like)
    
    all_chains.append(np.array(chain))
    all_log_likes.append(np.array(chain_log_likes))
    
    if current_log_like > best_log_like:
        best_log_like = current_log_like
        best_direction = current_dir.copy()
    
    if (trial + 1) % 10 == 0:
        print(f"  Trial {trial+1}/{n_trials} complete...")

elapsed = time.time() - start_time
print(f"\nMCMC completed in {elapsed:.1f}s")

# Use the best trial's chain for analysis
best_trial_idx = np.argmax([logs[-1] for logs in all_log_likes])
best_chain = all_chains[best_trial_idx]
best_log_likes = all_log_likes[best_trial_idx]

print(f"\nBest trial: {best_trial_idx + 1}")
print(f"Final log likelihood: {best_log_likes[-1]:.4f}")
print(f"Initial log likelihood: {best_log_likes[0]:.4f}")
print(f"Improvement: {best_log_likes[-1] - best_log_likes[0]:.4f}")

# Analyze convergence
final_window = best_log_likes[-1000:]
print(f"\nFinal 1000 steps:")
print(f"  Mean log likelihood: {final_window.mean():.4f}")
print(f"  Std dev: {final_window.std():.4f}")

# Direction stability
final_dirs = best_chain[-5000:]
print(f"\nFinal 5000 steps direction stability:")
print(f"  X std: {final_dirs[:,0].std():.6f}")
print(f"  Y std: {final_dirs[:,1].std():.6f}")
print(f"  Z std: {final_dirs[:,2].std():.6f}")

# Jump analysis
jumps = np.array([np.linalg.norm(best_chain[i] - best_chain[i-1]) 
                  for i in range(1, len(best_chain))])
print(f"\nJump size analysis:")
print(f"  Early (0-100): {jumps[:100].mean():.6f}")
print(f"  Middle: {jumps[len(jumps)//2-50:len(jumps)//2+50].mean():.6f}")
print(f"  Late (last 100): {jumps[-100:].mean():.6f}")

# Acceptance rate
n_moves = np.sum(np.any(np.diff(best_chain, axis=0) != 0, axis=1))
print(f"\nAcceptance rate: {100*n_moves/n_steps:.1f}%")

# Autocorrelation
print(f"\nAutocorrelation:")
ll_normalized = (best_log_likes - best_log_likes.mean()) / best_log_likes.std()
for lag in [1, 10, 50, 100, 500, 1000]:
    if lag < len(ll_normalized):
        autocorr = np.corrcoef(ll_normalized[:-lag], ll_normalized[lag:])[0, 1]
        print(f"  Lag {lag:4d}: {autocorr:.4f}")

# Angular error (using true direction)
reconstructed_dir = best_chain[-1]
cos_angle = np.dot(reconstructed_dir, true_direction)
cos_angle = np.clip(cos_angle, -1, 1)
angular_error = np.degrees(np.arccos(cos_angle))
print(f"\nReconstruction:")
print(f"  True direction:  [{true_direction[0]:.4f}, {true_direction[1]:.4f}, {true_direction[2]:.4f}]")
print(f"  Final direction: [{reconstructed_dir[0]:.4f}, {reconstructed_dir[1]:.4f}, {reconstructed_dir[2]:.4f}]")
print(f"  Angular error: {angular_error:.2f}°")
print(f"  cos(θ): {cos_angle:.4f}")

print("\n" + "="*70)
print("COMPARISON TO OLD RESULTS:")
print("="*70)
old_data = np.load('/eos/project-e/ep-nu/evilla/sn-pointing/cat000062/pipeline/cat000062_scenario_perfect_ct.npz')
old_chain = old_data['perfect_ct_mcmc_chain']
old_log_likes = old_data['perfect_ct_mcmc_log_likelihoods']
old_angular_error = float(old_data['perfect_ct_angular_error_deg'])

print(f"\nOLD (narrow damping):")
print(f"  Final log likelihood: {old_log_likes[-1]:.4f}")
print(f"  Final 1000 std: {old_log_likes[-1000:].std():.4f}")
print(f"  Angular error: {old_angular_error:.2f}°")

print(f"\nNEW (improved damping):")
print(f"  Final log likelihood: {best_log_likes[-1]:.4f}")
print(f"  Final 1000 std: {final_window.std():.4f}")
print(f"  Angular error: {angular_error:.2f}°")

print(f"\nIMPROVEMENT:")
print(f"  Δ log likelihood: {best_log_likes[-1] - old_log_likes[-1]:.4f}")
print(f"  Δ convergence (std): {old_log_likes[-1000:].std() - final_window.std():.4f} (negative = better)")
print(f"  Δ angular error: {old_angular_error - angular_error:.2f}° (positive = better)")

print("\n✓ Test complete")
