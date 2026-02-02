#!/usr/bin/env python3
"""
Analyze MCMC results by loading cluster data directly and filtering for ES main tracks.
Creates theta/phi histograms and angular distribution analysis.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_pdf import PdfPages
import tensorflow as tf
import uproot
import json
import argparse
from pathlib import Path
from scipy.interpolate import RegularGridInterpolator
from scipy.optimize import minimize

# Data paths
BASE_PATH = Path("/eos/home-e/evilla/DUNE/supernova/train-40k-v3_100k")
CLUSTERS_PATH = BASE_PATH / "cluster_images_tick3_ch2_min2_tot3_e2p0"
TPS_PATH = BASE_PATH / "tps"

# Model paths
ED_MODEL = "/eos/home-e/evilla/DUNE/supernova/models/electron-direction/three_plane_three_plane_v50_100k_20251115_232348"
PDF_FILE = "/eos/home-e/evilla/DUNE/supernova/cosine_energy_pdf.npz"


def load_ed_model():
    """Load ED model with TF2/Keras3 compatibility."""
    try:
        model = tf.keras.models.load_model(ED_MODEL, compile=False)
    except ValueError:
        # Keras 3 requires TFSMLayer
        model_layer = tf.keras.layers.TFSMLayer(ED_MODEL, call_endpoint='serving_default')
        
        input_x = tf.keras.Input(shape=(128, 32, 1))
        input_u = tf.keras.Input(shape=(128, 32, 1))
        input_v = tf.keras.Input(shape=(128, 32, 1))
        
        outputs = model_layer(x=input_x, u=input_u, v=input_v)
        
        if isinstance(outputs, dict):
            output_keys = list(outputs.keys())
            output_key = [k for k in output_keys if 'output' in k.lower()] or output_keys
            direction = outputs[output_key[0]]
        else:
            direction = outputs
        
        model = tf.keras.Model(inputs=[input_x, input_u, input_v], outputs=direction)
    
    return model


def load_energy_cosine_pdf():
    """Load energy-cosine PDF."""
    data = np.load(PDF_FILE)
    pdf_2d = data['pdf_2d']
    energy_bins = data['energy_bins']
    cosine_bin_centers = data['cosine_bin_centers']
    
    energy_centers = energy_bins.mean(axis=1)
    
    interpolator = RegularGridInterpolator(
        (energy_centers, cosine_bin_centers),
        pdf_2d,
        bounds_error=False,
        fill_value=1e-10
    )
    
    return interpolator


def load_true_neutrino_direction(cat_name):
    """Load true neutrino direction from tps ROOT file."""
    tps_dir = TPS_PATH
    root_files = sorted(tps_dir.glob(f"{cat_name}*.root"))
    
    if not root_files:
        return None
    
    with uproot.open(root_files[0]) as f:
        tree = f['tps']
        nu_px = tree['neutrino_px'].array(library='np')
        nu_py = tree['neutrino_py'].array(library='np')
        nu_pz = tree['neutrino_pz'].array(library='np')
    
    # Average (should be constant per category)
    true_px = np.mean(nu_px)
    true_py = np.mean(nu_py)
    true_pz = np.mean(nu_pz)
    
    # Normalize
    true_norm = np.sqrt(true_px**2 + true_py**2 + true_pz**2)
    true_direction = np.array([true_px, true_py, true_pz]) / true_norm
    
    return true_direction


def load_cluster_data(cat_name, plane):
    """Load cluster images and metadata for given plane."""
    plane_dir = CLUSTERS_PATH / plane / cat_name
    npz_files = sorted(plane_dir.glob("*.npz"))
    
    all_images = []
    all_metadata = []
    
    for npz_file in npz_files:
        data = np.load(npz_file)
        all_images.append(data['images'])
        all_metadata.append(data['metadata'])
    
    images = np.concatenate(all_images, axis=0)
    metadata = np.concatenate(all_metadata, axis=0)
    
    return images, metadata


def compute_mcmc_direction(cluster_images_x, cluster_images_u, cluster_images_v, 
                          cluster_energies, ed_model, pdf_interpolator):
    """Run ED model + MCMC to find best neutrino direction."""
    n_clusters = len(cluster_images_x)
    
    # Predict cluster directions
    cluster_directions = []
    for i in range(n_clusters):
        img_x = np.expand_dims(cluster_images_x[i], axis=0)
        img_u = np.expand_dims(cluster_images_u[i], axis=0)
        img_v = np.expand_dims(cluster_images_v[i], axis=0)
        
        direction = ed_model.predict([img_x, img_u, img_v], verbose=0)[0]
        norm = np.linalg.norm(direction)
        if norm > 0:
            direction = direction / norm
        
        cluster_directions.append(direction)
    
    cluster_directions = np.array(cluster_directions)
    
    # MCMC optimization
    def neg_log_likelihood(candidate_dir):
        candidate_norm = np.linalg.norm(candidate_dir)
        if candidate_norm < 1e-10:
            return 1e10
        candidate_dir_unit = candidate_dir / candidate_norm
        
        cosines = np.dot(cluster_directions, candidate_dir_unit)
        cosines = np.clip(cosines, -1.0, 1.0)
        
        points = np.column_stack([cluster_energies, cosines])
        pdf_values = pdf_interpolator(points)
        
        log_likelihood = np.sum(np.log(np.maximum(pdf_values, 1e-10)))
        
        return -log_likelihood
    
    # Initial guess: mean of cluster directions
    initial_dir = np.mean(cluster_directions, axis=0)
    initial_norm = np.linalg.norm(initial_dir)
    if initial_norm > 0:
        initial_dir = initial_dir / initial_norm
    else:
        initial_dir = np.array([0, 0, 1])
    
    result = minimize(neg_log_likelihood, initial_dir, method='BFGS', options={'maxiter': 1000})
    
    final_direction = result.x / np.linalg.norm(result.x)
    
    return final_direction


def cartesian_to_spherical(directions):
    """
    Convert cartesian directions to spherical coordinates.
    
    Args:
        directions: array of shape (n, 3) with [x, y, z] unit vectors
    
    Returns:
        theta: polar angle from +z axis [0, 180] degrees
        phi: azimuthal angle from +x axis [-180, 180] degrees
    """
    directions = np.array(directions)
    if directions.ndim == 1:
        directions = directions.reshape(1, -1)
    
    x, y, z = directions[:, 0], directions[:, 1], directions[:, 2]
    
    theta = np.degrees(np.arccos(np.clip(z, -1, 1)))
    phi = np.degrees(np.arctan2(y, x))
    
    return theta, phi


def plot_investigation(results_data, output_pdf):
    """
    Create comprehensive investigation plots from existing results.
    
    Args:
        results_data: dict with 'summary' and 'events' keys
        output_pdf: path to output PDF file
    """
    events = results_data['events']
    summary = results_data['summary']
    cat_name = results_data['cat_name']
    
    with PdfPages(output_pdf) as pdf:
        
        # Page 1: Theta-Phi distribution
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        
        # Extract directions
        mcmc_directions = np.array([e['mcmc_direction'] for e in events])
        true_direction = np.array(events[0]['true_direction'])
        
        # Convert to spherical
        theta_reco, phi_reco = cartesian_to_spherical(mcmc_directions)
        theta_true, phi_true = cartesian_to_spherical(true_direction.reshape(1, 3))
        
        # Theta histogram
        ax = axes[0, 0]
        ax.hist(theta_reco, bins=30, alpha=0.7, color='blue', edgecolor='black')
        ax.axvline(theta_true[0], color='red', linestyle='--', linewidth=2, 
                  label=f'True θ={theta_true[0]:.1f}°')
        ax.set_xlabel('θ (polar angle from +z) [degrees]', fontsize=11)
        ax.set_ylabel('Number of events', fontsize=11)
        ax.set_title('Theta Distribution', fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Add statistics
        mean_theta = np.mean(theta_reco)
        std_theta = np.std(theta_reco)
        ax.text(0.98, 0.97, f'Mean: {mean_theta:.1f}°\nStd: {std_theta:.1f}°',
               transform=ax.transAxes, fontsize=9,
               verticalalignment='top', horizontalalignment='right',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        # Phi histogram
        ax = axes[0, 1]
        ax.hist(phi_reco, bins=30, alpha=0.7, color='green', edgecolor='black')
        ax.axvline(phi_true[0], color='red', linestyle='--', linewidth=2, 
                  label=f'True φ={phi_true[0]:.1f}°')
        ax.set_xlabel('φ (azimuthal angle from +x) [degrees]', fontsize=11)
        ax.set_ylabel('Number of events', fontsize=11)
        ax.set_title('Phi Distribution', fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Add statistics
        mean_phi = np.mean(phi_reco)
        std_phi = np.std(phi_reco)
        ax.text(0.98, 0.97, f'Mean: {mean_phi:.1f}°\nStd: {std_phi:.1f}°',
               transform=ax.transAxes, fontsize=9,
               verticalalignment='top', horizontalalignment='right',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        # 2D scatter
        ax = axes[1, 0]
        scatter = ax.scatter(phi_reco, theta_reco, c=[e['cosine_angle'] for e in events],
                           cmap='RdYlGn', alpha=0.6, s=50, edgecolor='black', linewidth=0.5)
        ax.scatter(phi_true[0], theta_true[0], color='red', s=400, marker='*', 
                  edgecolor='black', linewidth=2, label='True direction', zorder=100)
        ax.set_xlabel('φ [degrees]', fontsize=11)
        ax.set_ylabel('θ [degrees]', fontsize=11)
        ax.set_title('Theta-Phi Scatter (color = cos(angle))', fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label('cos(angle to true)', fontsize=10)
        
        # Cos(angle) histogram
        ax = axes[1, 1]
        cos_angles = [e['cosine_angle'] for e in events]
        ax.hist(cos_angles, bins=30, alpha=0.7, color='purple', edgecolor='black')
        ax.axvline(1.0, color='red', linestyle='--', linewidth=2, label='Perfect (cos=1)')
        ax.axvline(0.0, color='gray', linestyle=':', linewidth=1, label='90°')
        ax.set_xlabel('cos(angle to true direction)', fontsize=11)
        ax.set_ylabel('Number of events', fontsize=11)
        ax.set_title('Angular Resolution', fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Statistics
        median_cos = summary['median_cosine']
        median_angle = summary['median_angle_deg']
        p68_angle = summary['p68_angle_deg']
        stats_text = (f"Category: {cat_name}\n"
                     f"Median cos = {median_cos:.3f}\n"
                     f"Median angle = {median_angle:.1f}°\n"
                     f"68th percentile = {p68_angle:.1f}°")
        fig.text(0.5, 0.02, stats_text, ha='center', fontsize=11, 
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))
        
        fig.suptitle(f'Angular Distribution Analysis: {cat_name}', 
                    fontsize=14, fontweight='bold')
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        
        # Page 2: Bias analysis
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        
        # Theta bias
        ax = axes[0, 0]
        theta_bias = theta_reco - theta_true[0]
        ax.hist(theta_bias, bins=30, alpha=0.7, color='blue', edgecolor='black')
        ax.axvline(0, color='red', linestyle='--', linewidth=2, label='No bias')
        ax.set_xlabel('Δθ = θ_reco - θ_true [degrees]', fontsize=11)
        ax.set_ylabel('Number of events', fontsize=11)
        ax.set_title('Theta Bias', fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        mean_bias = np.mean(theta_bias)
        ax.text(0.98, 0.97, f'Mean bias: {mean_bias:.1f}°\nStd: {np.std(theta_bias):.1f}°',
               transform=ax.transAxes, fontsize=9,
               verticalalignment='top', horizontalalignment='right',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        # Phi bias
        ax = axes[0, 1]
        phi_bias = phi_reco - phi_true[0]
        # Handle wrapping at ±180°
        phi_bias = np.where(phi_bias > 180, phi_bias - 360, phi_bias)
        phi_bias = np.where(phi_bias < -180, phi_bias + 360, phi_bias)
        ax.hist(phi_bias, bins=30, alpha=0.7, color='green', edgecolor='black')
        ax.axvline(0, color='red', linestyle='--', linewidth=2, label='No bias')
        ax.set_xlabel('Δφ = φ_reco - φ_true [degrees]', fontsize=11)
        ax.set_ylabel('Number of events', fontsize=11)
        ax.set_title('Phi Bias', fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        mean_bias = np.mean(phi_bias)
        ax.text(0.98, 0.97, f'Mean bias: {mean_bias:.1f}°\nStd: {np.std(phi_bias):.1f}°',
               transform=ax.transAxes, fontsize=9,
               verticalalignment='top', horizontalalignment='right',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        # Angle distribution
        ax = axes[1, 0]
        angles = [e['angle_deg'] for e in events]
        ax.hist(angles, bins=30, alpha=0.7, color='orange', edgecolor='black')
        ax.axvline(0, color='red', linestyle='--', linewidth=2, label='Perfect')
        ax.axvline(90, color='gray', linestyle=':', linewidth=1, label='90° (random)')
        ax.set_xlabel('Angle to true direction [degrees]', fontsize=11)
        ax.set_ylabel('Number of events', fontsize=11)
        ax.set_title('Opening Angle Distribution', fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Direction components
        ax = axes[1, 1]
        x_reco = mcmc_directions[:, 0]
        y_reco = mcmc_directions[:, 1]
        z_reco = mcmc_directions[:, 2]
        x_true, y_true, z_true = true_direction
        
        positions = [1, 2, 3]
        bp = ax.boxplot([x_reco, y_reco, z_reco], positions=positions,
                       labels=['x', 'y', 'z'], patch_artist=True)
        for patch, color in zip(bp['boxes'], ['lightblue', 'lightgreen', 'lightcoral']):
            patch.set_facecolor(color)
        
        ax.axhline(0, color='gray', linestyle=':', linewidth=1, alpha=0.5)
        ax.scatter([1, 2, 3], [x_true, y_true, z_true], color='red', s=200, 
                  marker='*', edgecolor='black', linewidth=2, label='True', zorder=100)
        ax.set_ylabel('Direction component', fontsize=11)
        ax.set_title('Cartesian Components Distribution', fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')
        
        fig.suptitle(f'Bias Analysis: {cat_name}', fontsize=14, fontweight='bold')
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        
        # Page 3: Cluster analysis
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        
        # Number of clusters per event
        ax = axes[0, 0]
        n_clusters = [e['n_clusters'] for e in events]
        ax.hist(n_clusters, bins=range(min(n_clusters), max(n_clusters)+2), 
               alpha=0.7, color='orange', edgecolor='black')
        ax.set_xlabel('Number of clusters', fontsize=11)
        ax.set_ylabel('Number of events', fontsize=11)
        ax.set_title('Clusters per Event', fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        # MCMC log-likelihood
        ax = axes[0, 1]
        log_likelihoods = [e['mcmc_log_likelihood'] for e in events]
        ax.hist(log_likelihoods, bins=30, alpha=0.7, color='cyan', edgecolor='black')
        ax.set_xlabel('MCMC log-likelihood', fontsize=11)
        ax.set_ylabel('Number of events', fontsize=11)
        ax.set_title('MCMC Log-Likelihood Distribution', fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        # Angle vs number of clusters
        ax = axes[1, 0]
        angles = [e['angle_deg'] for e in events]
        ax.scatter(n_clusters, angles, alpha=0.5, s=50, edgecolor='black', linewidth=0.5)
        ax.set_xlabel('Number of clusters', fontsize=11)
        ax.set_ylabel('Angle to true direction [degrees]', fontsize=11)
        ax.set_title('Angle vs Cluster Count', fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        # Correlation coefficient
        corr = np.corrcoef(n_clusters, angles)[0, 1]
        ax.text(0.02, 0.98, f'Correlation: {corr:.3f}',
               transform=ax.transAxes, fontsize=10,
               verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        # Angle vs log-likelihood
        ax = axes[1, 1]
        ax.scatter(log_likelihoods, angles, alpha=0.5, s=50, edgecolor='black', linewidth=0.5)
        ax.set_xlabel('MCMC log-likelihood', fontsize=11)
        ax.set_ylabel('Angle to true direction [degrees]', fontsize=11)
        ax.set_title('Angle vs Log-Likelihood', fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        # Correlation coefficient
        corr = np.corrcoef(log_likelihoods, angles)[0, 1]
        ax.text(0.02, 0.98, f'Correlation: {corr:.3f}',
               transform=ax.transAxes, fontsize=10,
               verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        fig.suptitle(f'MCMC Performance Analysis: {cat_name}', fontsize=14, fontweight='bold')
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        
        # Page 4: Show "flipped" version for comparison
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        
        # Flip directions
        mcmc_directions_flipped = -mcmc_directions
        cos_angles_flipped = np.sum(mcmc_directions_flipped * true_direction, axis=1)
        angles_flipped = np.degrees(np.arccos(np.clip(cos_angles_flipped, -1, 1)))
        
        # Convert flipped to spherical
        theta_flipped, phi_flipped = cartesian_to_spherical(mcmc_directions_flipped)
        
        # Original vs flipped angle comparison
        ax = axes[0, 0]
        ax.hist(angles, bins=30, alpha=0.5, color='blue', label='Original', edgecolor='black')
        ax.hist(angles_flipped, bins=30, alpha=0.5, color='red', label='Flipped', edgecolor='black')
        ax.axvline(0, color='green', linestyle='--', linewidth=2, label='Perfect')
        ax.set_xlabel('Angle to true direction [degrees]', fontsize=11)
        ax.set_ylabel('Number of events', fontsize=11)
        ax.set_title('Original vs Flipped Angles', fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Statistics comparison
        stats_text = (f"Original: median={np.median(angles):.1f}°, mean={np.mean(angles):.1f}°\n"
                     f"Flipped: median={np.median(angles_flipped):.1f}°, mean={np.mean(angles_flipped):.1f}°")
        ax.text(0.98, 0.97, stats_text,
               transform=ax.transAxes, fontsize=9,
               verticalalignment='top', horizontalalignment='right',
               bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        # Theta comparison
        ax = axes[0, 1]
        ax.hist(theta_reco, bins=30, alpha=0.5, color='blue', label='Original', edgecolor='black')
        ax.hist(theta_flipped, bins=30, alpha=0.5, color='red', label='Flipped', edgecolor='black')
        ax.axvline(theta_true[0], color='green', linestyle='--', linewidth=2, label='True')
        ax.set_xlabel('θ [degrees]', fontsize=11)
        ax.set_ylabel('Number of events', fontsize=11)
        ax.set_title('Theta: Original vs Flipped', fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Phi comparison
        ax = axes[1, 0]
        ax.hist(phi_reco, bins=30, alpha=0.5, color='blue', label='Original', edgecolor='black')
        ax.hist(phi_flipped, bins=30, alpha=0.5, color='red', label='Flipped', edgecolor='black')
        ax.axvline(phi_true[0], color='green', linestyle='--', linewidth=2, label='True')
        ax.set_xlabel('φ [degrees]', fontsize=11)
        ax.set_ylabel('Number of events', fontsize=11)
        ax.set_title('Phi: Original vs Flipped', fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # 2D scatter comparison
        ax = axes[1, 1]
        ax.scatter(phi_reco, theta_reco, alpha=0.4, s=50, color='blue', 
                  label='Original', edgecolor='black', linewidth=0.5)
        ax.scatter(phi_flipped, theta_flipped, alpha=0.4, s=50, color='red',
                  label='Flipped', marker='s', edgecolor='black', linewidth=0.5)
        ax.scatter(phi_true[0], theta_true[0], color='green', s=400, marker='*', 
                  edgecolor='black', linewidth=2, label='True', zorder=100)
        ax.set_xlabel('φ [degrees]', fontsize=11)
        ax.set_ylabel('θ [degrees]', fontsize=11)
        ax.set_title('Theta-Phi: Original vs Flipped', fontweight='bold')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        fig.suptitle(f'Direction Flip Comparison: {cat_name}\n' + 
                    '(Flipping shows what resolution would be if ED predicted neutrino direction)',
                    fontsize=14, fontweight='bold')
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()


def main():
    parser = argparse.ArgumentParser(description='Analyze MCMC results for ES main tracks')
    parser.add_argument('--cat', type=str, required=True, help='Category name (e.g., cat000020)')
    parser.add_argument('--output', type=str, default=None, help='Output PDF path')
    parser.add_argument('--filter-es', action='store_true', default=True, help='Filter for ES interactions')
    parser.add_argument('--filter-main', action='store_true', default=True, help='Filter for main track')
    args = parser.parse_args()
    
    cat_name = args.cat
    
    if args.output is None:
        output_pdf = f"results/mcmc_investigation_{cat_name}_filtered.pdf"
    else:
        output_pdf = args.output
    
    print(f"\n{'='*60}")
    print(f"MCMC Analysis: {cat_name}")
    print(f"Filter ES: {args.filter_es}")
    print(f"Filter Main Track: {args.filter_main}")
    print(f"{'='*60}\n")
    
    # Load models
    print("Loading ED model...")
    ed_model = load_ed_model()
    
    print("Loading energy-cosine PDF...")
    pdf_interpolator = load_energy_cosine_pdf()
    
    print("Loading true neutrino direction...")
    true_neutrino_direction = load_true_neutrino_direction(cat_name)
    print(f"  True direction: {true_neutrino_direction}")
    
    # Load cluster data for all planes
    print(f"\nLoading cluster data for {cat_name}...")
    images_x, metadata_x = load_cluster_data(cat_name, 'X')
    images_u, metadata_u = load_cluster_data(cat_name, 'U')
    images_v, metadata_v = load_cluster_data(cat_name, 'V')
    
    print(f"  X plane: {images_x.shape[0]} clusters")
    print(f"  U plane: {images_u.shape[0]} clusters")
    print(f"  V plane: {images_v.shape[0]} clusters")
    
    # Metadata positions (from generate_cluster_arrays.py):
    # 0: event_id
    # 1: is_marley
    # 2: is_main_track
    # 3: is_es_interaction
    # 4-6: true_pos (x,y,z)
    # 7-9: true_particle_mom (px,py,pz)
    # 10: cluster_energy_mev
    # 11: true_particle_energy
    # 12: plane_number
    # 13: match_id
    
    # Get unique event IDs
    event_ids = np.unique(metadata_x[:, 0]).astype(int)
    print(f"\nTotal events in category: {len(event_ids)}")
    
    # Filter events based on criteria
    filtered_event_ids = []
    for event_id in event_ids:
        mask = (metadata_x[:, 0] == event_id)
        event_meta = metadata_x[mask]
        
        # Check if ANY cluster in this event satisfies criteria
        is_main = np.any(event_meta[:, 2] > 0.5)  # is_main_track
        is_es = np.any(event_meta[:, 3] > 0.5)    # is_es_interaction
        
        include_event = True
        if args.filter_main and not is_main:
            include_event = False
        if args.filter_es and not is_es:
            include_event = False
        
        if include_event:
            filtered_event_ids.append(event_id)
    
    print(f"Filtered events (ES main tracks): {len(filtered_event_ids)}")
    
    if len(filtered_event_ids) == 0:
        print("✗ No events match filter criteria!")
        return
    
    # Process filtered events
    results = []
    
    for i, event_id in enumerate(filtered_event_ids):
        if (i + 1) % 20 == 0 or (i + 1) == len(filtered_event_ids):
            print(f"\rProcessing event {i+1}/{len(filtered_event_ids)}...", end='', flush=True)
        
        # Get clusters for this event
        mask_x = (metadata_x[:, 0] == event_id)
        mask_u = (metadata_u[:, 0] == event_id)
        mask_v = (metadata_v[:, 0] == event_id)
        
        event_images_x = images_x[mask_x]
        event_images_u = images_u[mask_u]
        event_images_v = images_v[mask_v]
        
        event_energies = np.abs(metadata_x[mask_x, 10])  # cluster_energy_mev
        
        # Run MCMC
        mcmc_direction = compute_mcmc_direction(
            event_images_x, event_images_u, event_images_v,
            event_energies, ed_model, pdf_interpolator
        )
        
        # Compare to true direction
        cos_angle = np.dot(mcmc_direction, true_neutrino_direction)
        angle_deg = np.degrees(np.arccos(np.clip(cos_angle, -1, 1)))
        
        results.append({
            'event_id': int(event_id),
            'n_clusters': len(event_images_x),
            'mcmc_direction': mcmc_direction.tolist(),
            'true_direction': true_neutrino_direction.tolist(),
            'cosine_angle': float(cos_angle),
            'angle_deg': float(angle_deg)
        })
    
    print("\n")
    
    # Generate plots
    print(f"Generating investigation plots...")
    
    # Create results data structure compatible with original plotting function
    results_data = {
        'cat_name': cat_name,
        'summary': {
            'n_events': len(results),
            'median_cosine': float(np.median([r['cosine_angle'] for r in results])),
            'median_angle_deg': float(np.median([r['angle_deg'] for r in results])),
            'mean_cosine': float(np.mean([r['cosine_angle'] for r in results])),
            'p68_cosine': float(np.percentile([r['cosine_angle'] for r in results], 68)),
            'p68_angle_deg': float(np.percentile([r['angle_deg'] for r in results], 68))
        },
        'events': results
    }
    
    plot_investigation(results_data, output_pdf)
    
    # Save JSON
    json_output = output_pdf.replace('.pdf', '.json')
    with open(json_output, 'w') as f:
        json.dump(results_data, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✓ Analysis complete!")
    print(f"  Events analyzed: {len(results)}")
    print(f"  Median cos: {results_data['summary']['median_cosine']:.3f}")
    print(f"  Median angle: {results_data['summary']['median_angle_deg']:.1f}°")
    print(f"  68th percentile: {results_data['summary']['p68_angle_deg']:.1f}°")
    print(f"  PDF: {output_pdf}")
    print(f"  JSON: {json_output}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
