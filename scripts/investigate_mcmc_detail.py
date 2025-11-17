#!/usr/bin/env python3
"""
Detailed MCMC investigation script.
Shows convergence behavior, theta/phi distributions, and physics checks.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_pdf import PdfPages
import tensorflow as tf
import uproot
import json
from pathlib import Path
from scipy.interpolate import RegularGridInterpolator
from scipy.optimize import minimize
import argparse

# Data paths
BASE_PATH = Path("/eos/home-e/evilla/DUNE/supernova/train-40k-v3_100k")
CLUSTERS_PATH = BASE_PATH / "cluster_images_tick3_ch2_min2_tot3_e2p0"
VOLUMES_PATH = BASE_PATH / "volumes_tick3_ch2_min2_tot3_e2p0"
TPS_PATH = BASE_PATH / "tps"

# Model paths
MT_MODEL = "/eos/home-e/evilla/DUNE/supernova/models/main-track/v10_100k_nov13"
CT_MODEL = "/eos/home-e/evilla/DUNE/supernova/models/cluster-track/v40_corrected_10k"
ED_MODEL = "/eos/home-e/evilla/DUNE/supernova/models/electron-direction/three_plane_three_plane_v50_100k_20251115_232348"

# Energy-cosine PDF
PDF_FILE = "/eos/home-e/evilla/DUNE/supernova/cosine_energy_pdf.npz"


def load_models():
    """Load the ED model (we don't need MT/CT for this analysis)."""
    print("Loading ED model...")
    
    # Try loading as regular model first (older TF), fallback to TFSMLayer (Keras 3)
    try:
        ed_model = tf.keras.models.load_model(ED_MODEL, compile=False)
    except ValueError:
        # Keras 3 requires TFSMLayer for SavedModel format
        print("  Using TFSMLayer for Keras 3 compatibility...")
        ed_model_layer = tf.keras.layers.TFSMLayer(ED_MODEL, call_endpoint='serving_default')
        
        # Wrap in a functional model for consistent interface
        input_x = tf.keras.Input(shape=(128, 32, 1))
        input_u = tf.keras.Input(shape=(128, 32, 1))
        input_v = tf.keras.Input(shape=(128, 32, 1))
        
        outputs = ed_model_layer(x=input_x, u=input_u, v=input_v)
        
        # Extract the direction output (key varies by model)
        if isinstance(outputs, dict):
            # Find the output key
            output_keys = list(outputs.keys())
            print(f"  Available outputs: {output_keys}")
            # Use first output or look for 'output' or similar
            output_key = [k for k in output_keys if 'output' in k.lower()] or output_keys
            direction = outputs[output_key[0]]
        else:
            direction = outputs
        
        ed_model = tf.keras.Model(inputs=[input_x, input_u, input_v], outputs=direction)
    
    print(f"  ED: {ED_MODEL}")
    return ed_model


def load_energy_cosine_pdf():
    """Load the energy-cosine PDF for MCMC."""
    print(f"\nLoading energy-cosine PDF from {PDF_FILE}")
    data = np.load(PDF_FILE)
    pdf_2d = data['pdf_2d']  # Shape: [n_energy_bins, n_cosine_bins]
    energy_bins = data['energy_bins']  # Shape: [n_energy_bins, 2] (min, max)
    cosine_bin_centers = data['cosine_bin_centers']  # Shape: [n_cosine_bins]
    
    # Use bin centers for energy
    energy_centers = energy_bins.mean(axis=1)
    
    print(f"  PDF shape: {pdf_2d.shape}")
    print(f"  Energy range: [{energy_centers.min():.2f}, {energy_centers.max():.2f}] MeV")
    print(f"  Cosine range: [{cosine_bin_centers.min():.2f}, {cosine_bin_centers.max():.2f}]")
    
    # Create interpolator
    interpolator = RegularGridInterpolator(
        (energy_centers, cosine_bin_centers),
        pdf_2d,
        bounds_error=False,
        fill_value=1e-10
    )
    
    return interpolator, energy_centers, cosine_bin_centers


def load_true_neutrino_direction(cat_name):
    """Load true neutrino direction from tps ROOT file."""
    tps_file = TPS_PATH / f"{cat_name}.root"
    
    with uproot.open(tps_file) as f:
        tree = f["tps"]
        neutrino_px = tree["neutrino_px"].array(library="np")
        neutrino_py = tree["neutrino_py"].array(library="np")
        neutrino_pz = tree["neutrino_pz"].array(library="np")
    
    # Average (should be constant per category)
    true_px = np.mean(neutrino_px)
    true_py = np.mean(neutrino_py)
    true_pz = np.mean(neutrino_pz)
    
    # Normalize
    true_norm = np.sqrt(true_px**2 + true_py**2 + true_pz**2)
    true_direction = np.array([true_px, true_py, true_pz]) / true_norm
    
    print(f"True neutrino direction: {true_direction}")
    print(f"  (θ={np.degrees(np.arccos(true_direction[2])):.2f}°, φ={np.degrees(np.arctan2(true_direction[1], true_direction[0])):.2f}°)")
    
    return true_direction


def load_cluster_images(cat_name, plane):
    """Load cluster images and metadata for a given plane."""
    plane_dir = CLUSTERS_PATH / plane / cat_name
    
    # Find all .npz files
    npz_files = sorted(plane_dir.glob("*.npz"))
    
    all_images = []
    all_metadata = []
    
    for npz_file in npz_files:
        data = np.load(npz_file)
        all_images.append(data['images'])
        all_metadata.append(data['metadata'])
    
    # Concatenate batches
    images = np.concatenate(all_images, axis=0)
    metadata = np.concatenate(all_metadata, axis=0)
    
    return images, metadata


def process_event_with_history(event_id, cluster_images_x, cluster_images_u, cluster_images_v,
                                cluster_energies, ed_model, pdf_interpolator, 
                                true_neutrino_direction, max_iter=1000):
    """
    Process one event and return detailed MCMC history.
    
    Returns:
        dict with keys:
            - event_id
            - n_clusters
            - cluster_energies
            - cluster_directions: shape (n_clusters, 3)
            - mcmc_history: list of dicts with 'direction', 'log_likelihood', 'iteration'
            - final_direction
            - true_direction
            - cos_angle
            - angle_deg
    """
    n_clusters = len(cluster_images_x)
    
    # Predict direction for each cluster
    cluster_directions = []
    for i in range(n_clusters):
        img_x = np.expand_dims(cluster_images_x[i], axis=0)
        img_u = np.expand_dims(cluster_images_u[i], axis=0)
        img_v = np.expand_dims(cluster_images_v[i], axis=0)
        
        direction = ed_model.predict([img_x, img_u, img_v], verbose=0)[0]
        
        # Normalize
        norm = np.linalg.norm(direction)
        if norm > 0:
            direction = direction / norm
        
        cluster_directions.append(direction)
    
    cluster_directions = np.array(cluster_directions)
    
    # MCMC likelihood function with history tracking
    history = []
    
    def neg_log_likelihood(candidate_dir):
        """Negative log-likelihood for minimization."""
        # Normalize candidate direction
        candidate_norm = np.linalg.norm(candidate_dir)
        if candidate_norm < 1e-10:
            return 1e10
        candidate_dir_unit = candidate_dir / candidate_norm
        
        # Compute cosines with all cluster directions
        cosines = np.dot(cluster_directions, candidate_dir_unit)
        
        # Clip to valid range
        cosines = np.clip(cosines, -1.0, 1.0)
        
        # Evaluate PDF for each cluster
        points = np.column_stack([cluster_energies, cosines])
        pdf_values = pdf_interpolator(points)
        
        # Compute log-likelihood
        log_likelihood = np.sum(np.log(np.maximum(pdf_values, 1e-10)))
        
        # Track history
        history.append({
            'iteration': len(history),
            'direction': candidate_dir_unit.copy(),
            'log_likelihood': log_likelihood,
            'cos_angles': cosines.copy()
        })
        
        return -log_likelihood
    
    # Initial guess: mean of cluster directions
    initial_dir = np.mean(cluster_directions, axis=0)
    initial_norm = np.linalg.norm(initial_dir)
    if initial_norm > 0:
        initial_dir = initial_dir / initial_norm
    else:
        initial_dir = np.array([0, 0, 1])
    
    # Run optimization
    result = minimize(
        neg_log_likelihood,
        initial_dir,
        method='BFGS',
        options={'maxiter': max_iter}
    )
    
    # Final direction
    final_direction = result.x / np.linalg.norm(result.x)
    
    # Compare to true neutrino direction
    cos_angle = np.dot(final_direction, true_neutrino_direction)
    angle_deg = np.degrees(np.arccos(np.clip(cos_angle, -1, 1)))
    
    return {
        'event_id': event_id,
        'n_clusters': n_clusters,
        'cluster_energies': cluster_energies.tolist(),
        'cluster_directions': cluster_directions.tolist(),
        'mcmc_history': history,
        'final_direction': final_direction.tolist(),
        'true_direction': true_neutrino_direction.tolist(),
        'cos_angle': cos_angle,
        'angle_deg': angle_deg,
        'mcmc_iterations': len(history),
        'mcmc_success': result.success
    }


def cartesian_to_spherical(directions):
    """
    Convert cartesian directions to spherical coordinates.
    
    Args:
        directions: array of shape (n, 3) with [x, y, z] unit vectors
    
    Returns:
        theta: polar angle from +z axis [0, 180] degrees
        phi: azimuthal angle from +x axis [-180, 180] degrees
    """
    x, y, z = directions[:, 0], directions[:, 1], directions[:, 2]
    
    theta = np.degrees(np.arccos(np.clip(z, -1, 1)))
    phi = np.degrees(np.arctan2(y, x))
    
    return theta, phi


def plot_investigation(results, output_pdf):
    """
    Create comprehensive investigation plots.
    
    Args:
        results: list of event result dictionaries
        output_pdf: path to output PDF file
    """
    with PdfPages(output_pdf) as pdf:
        
        # Page 1: MCMC convergence for first 6 events
        fig = plt.figure(figsize=(12, 10))
        gs = gridspec.GridSpec(3, 2, figure=fig, hspace=0.3, wspace=0.3)
        
        for idx in range(min(6, len(results))):
            ax = fig.add_subplot(gs[idx // 2, idx % 2])
            
            event_data = results[idx]
            history = event_data['mcmc_history']
            
            iterations = [h['iteration'] for h in history]
            log_likelihoods = [h['log_likelihood'] for h in history]
            
            ax.plot(iterations, log_likelihoods, 'b-', alpha=0.7)
            ax.set_xlabel('Iteration')
            ax.set_ylabel('Log Likelihood')
            ax.set_title(f"Event {event_data['event_id']}: {event_data['mcmc_iterations']} iter, " +
                        f"cos={event_data['cos_angle']:.3f}, angle={event_data['angle_deg']:.1f}°")
            ax.grid(True, alpha=0.3)
        
        fig.suptitle('MCMC Convergence History (First 6 Events)', fontsize=14, fontweight='bold')
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        
        # Page 2: Direction evolution in 3D for first event
        if len(results) > 0:
            fig = plt.figure(figsize=(12, 10))
            gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.3, wspace=0.3)
            
            event_data = results[0]
            history = event_data['mcmc_history']
            true_dir = np.array(event_data['true_direction'])
            final_dir = np.array(event_data['final_direction'])
            
            # Extract direction evolution
            directions = np.array([h['direction'] for h in history])
            
            # Plot x, y, z components over iterations
            for comp_idx, comp_name in enumerate(['x', 'y', 'z']):
                ax = fig.add_subplot(gs[comp_idx // 2, comp_idx % 2])
                ax.plot(directions[:, comp_idx], 'b-', alpha=0.7, label='MCMC')
                ax.axhline(true_dir[comp_idx], color='r', linestyle='--', label='True')
                ax.axhline(final_dir[comp_idx], color='g', linestyle=':', label='Final')
                ax.set_xlabel('Iteration')
                ax.set_ylabel(f'Direction {comp_name}')
                ax.set_title(f'{comp_name}-component Evolution')
                ax.legend()
                ax.grid(True, alpha=0.3)
            
            # Plot cos(angle) to true direction
            ax = fig.add_subplot(gs[1, 1])
            cos_to_true = [np.dot(h['direction'], true_dir) for h in history]
            ax.plot(cos_to_true, 'b-', alpha=0.7)
            ax.axhline(event_data['cos_angle'], color='g', linestyle=':', label='Final')
            ax.axhline(1.0, color='r', linestyle='--', label='Perfect')
            ax.set_xlabel('Iteration')
            ax.set_ylabel('cos(angle to true)')
            ax.set_title('Convergence to True Direction')
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            fig.suptitle(f"Direction Evolution: Event {event_data['event_id']}", 
                        fontsize=14, fontweight='bold')
            pdf.savefig(fig, bbox_inches='tight')
            plt.close()
        
        
        # Page 3: Theta-Phi distribution
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        
        # Extract final directions and true direction
        final_directions = np.array([r['final_direction'] for r in results])
        true_direction = np.array(results[0]['true_direction'])
        
        # Convert to spherical
        theta_reco, phi_reco = cartesian_to_spherical(final_directions)
        theta_true, phi_true = cartesian_to_spherical(true_direction.reshape(1, 3))
        
        # Theta histogram
        ax = axes[0, 0]
        ax.hist(theta_reco, bins=30, alpha=0.7, color='blue', edgecolor='black')
        ax.axvline(theta_true[0], color='red', linestyle='--', linewidth=2, label=f'True θ={theta_true[0]:.1f}°')
        ax.set_xlabel('θ (polar angle from +z) [degrees]')
        ax.set_ylabel('Number of events')
        ax.set_title('Theta Distribution')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Phi histogram
        ax = axes[0, 1]
        ax.hist(phi_reco, bins=30, alpha=0.7, color='green', edgecolor='black')
        ax.axvline(phi_true[0], color='red', linestyle='--', linewidth=2, label=f'True φ={phi_true[0]:.1f}°')
        ax.set_xlabel('φ (azimuthal angle from +x) [degrees]')
        ax.set_ylabel('Number of events')
        ax.set_title('Phi Distribution')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # 2D scatter
        ax = axes[1, 0]
        ax.scatter(phi_reco, theta_reco, alpha=0.5, s=20)
        ax.scatter(phi_true[0], theta_true[0], color='red', s=200, marker='*', 
                  edgecolor='black', linewidth=2, label='True direction')
        ax.set_xlabel('φ [degrees]')
        ax.set_ylabel('θ [degrees]')
        ax.set_title('Theta-Phi Scatter')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Cos(angle) histogram
        ax = axes[1, 1]
        cos_angles = [r['cos_angle'] for r in results]
        ax.hist(cos_angles, bins=30, alpha=0.7, color='purple', edgecolor='black')
        ax.axvline(1.0, color='red', linestyle='--', linewidth=2, label='Perfect (cos=1)')
        ax.set_xlabel('cos(angle to true direction)')
        ax.set_ylabel('Number of events')
        ax.set_title('Angular Resolution')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Statistics
        median_cos = np.median(cos_angles)
        median_angle = np.median([r['angle_deg'] for r in results])
        stats_text = f"Median cos = {median_cos:.3f}\nMedian angle = {median_angle:.1f}°"
        fig.text(0.5, 0.02, stats_text, ha='center', fontsize=12, 
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        fig.suptitle('Angular Distribution Analysis', fontsize=14, fontweight='bold')
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        
        # Page 4: Cluster analysis
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        
        # Number of clusters per event
        ax = axes[0, 0]
        n_clusters = [r['n_clusters'] for r in results]
        ax.hist(n_clusters, bins=range(1, max(n_clusters)+2), alpha=0.7, color='orange', edgecolor='black')
        ax.set_xlabel('Number of clusters')
        ax.set_ylabel('Number of events')
        ax.set_title('Clusters per Event')
        ax.grid(True, alpha=0.3)
        
        # Cluster energies distribution
        ax = axes[0, 1]
        all_energies = []
        for r in results:
            all_energies.extend(r['cluster_energies'])
        ax.hist(all_energies, bins=50, alpha=0.7, color='cyan', edgecolor='black')
        ax.set_xlabel('Cluster energy [MeV]')
        ax.set_ylabel('Number of clusters')
        ax.set_title('Cluster Energy Distribution')
        ax.set_yscale('log')
        ax.grid(True, alpha=0.3)
        
        # MCMC iterations
        ax = axes[1, 0]
        iterations = [r['mcmc_iterations'] for r in results]
        ax.hist(iterations, bins=30, alpha=0.7, color='magenta', edgecolor='black')
        ax.set_xlabel('MCMC iterations')
        ax.set_ylabel('Number of events')
        ax.set_title('MCMC Convergence Iterations')
        ax.grid(True, alpha=0.3)
        
        # Angle vs number of clusters
        ax = axes[1, 1]
        angles = [r['angle_deg'] for r in results]
        ax.scatter(n_clusters, angles, alpha=0.5, s=30)
        ax.set_xlabel('Number of clusters')
        ax.set_ylabel('Angle to true direction [degrees]')
        ax.set_title('Angle vs Cluster Count')
        ax.grid(True, alpha=0.3)
        
        fig.suptitle('Cluster and MCMC Analysis', fontsize=14, fontweight='bold')
        pdf.savefig(fig, bbox_inches='tight')
        plt.close()
        
        
        # Page 5: Initial vs Final directions for first event
        if len(results) > 0:
            fig = plt.figure(figsize=(12, 10))
            
            event_data = results[0]
            cluster_dirs = np.array(event_data['cluster_directions'])
            initial_dir = np.mean(cluster_dirs, axis=0)
            initial_dir = initial_dir / np.linalg.norm(initial_dir)
            final_dir = np.array(event_data['final_direction'])
            true_dir = np.array(event_data['true_direction'])
            
            # Convert to spherical
            theta_clusters, phi_clusters = cartesian_to_spherical(cluster_dirs)
            theta_init, phi_init = cartesian_to_spherical(initial_dir.reshape(1, 3))
            theta_final, phi_final = cartesian_to_spherical(final_dir.reshape(1, 3))
            theta_true, phi_true = cartesian_to_spherical(true_dir.reshape(1, 3))
            
            ax = fig.add_subplot(111)
            
            # Plot cluster directions
            ax.scatter(phi_clusters, theta_clusters, alpha=0.5, s=100, color='blue', 
                      label=f'Cluster directions (n={len(cluster_dirs)})')
            
            # Plot initial (mean)
            ax.scatter(phi_init[0], theta_init[0], s=300, color='green', marker='s',
                      edgecolor='black', linewidth=2, label='Initial (mean of clusters)')
            
            # Plot final
            ax.scatter(phi_final[0], theta_final[0], s=300, color='orange', marker='^',
                      edgecolor='black', linewidth=2, label='Final (MCMC)')
            
            # Plot true
            ax.scatter(phi_true[0], theta_true[0], s=500, color='red', marker='*',
                      edgecolor='black', linewidth=2, label='True neutrino')
            
            ax.set_xlabel('φ [degrees]', fontsize=12)
            ax.set_ylabel('θ [degrees]', fontsize=12)
            ax.set_title(f"Event {event_data['event_id']}: Direction Evolution in Theta-Phi Space", 
                        fontsize=14, fontweight='bold')
            ax.legend(fontsize=10)
            ax.grid(True, alpha=0.3)
            
            # Add text with angles
            cos_init = np.dot(initial_dir, true_dir)
            angle_init = np.degrees(np.arccos(np.clip(cos_init, -1, 1)))
            
            text = f"Initial → True: {angle_init:.1f}°\n"
            text += f"Final → True: {event_data['angle_deg']:.1f}°\n"
            text += f"MCMC improved by: {angle_init - event_data['angle_deg']:.1f}°"
            
            ax.text(0.02, 0.98, text, transform=ax.transAxes, 
                   fontsize=10, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
            
            pdf.savefig(fig, bbox_inches='tight')
            plt.close()


def main():
    parser = argparse.ArgumentParser(description='Detailed MCMC investigation')
    parser.add_argument('--cat', type=str, required=True, help='Category name (e.g., cat000020)')
    parser.add_argument('--max-events', type=int, default=40, help='Maximum number of events to process')
    parser.add_argument('--output', type=str, default=None, help='Output PDF path')
    args = parser.parse_args()
    
    cat_name = args.cat
    max_events = args.max_events
    
    if args.output is None:
        output_pdf = f"results/mcmc_investigation_{cat_name}.pdf"
    else:
        output_pdf = args.output
    
    print(f"\n{'='*60}")
    print(f"MCMC DETAILED INVESTIGATION")
    print(f"Category: {cat_name}")
    print(f"Max events: {max_events}")
    print(f"Output: {output_pdf}")
    print(f"{'='*60}\n")
    
    # Load ED model
    ed_model = load_models()
    
    # Load PDF
    pdf_interpolator, energy_centers, cosine_bin_centers = load_energy_cosine_pdf()
    
    # Load true neutrino direction
    true_neutrino_direction = load_true_neutrino_direction(cat_name)
    
    # Load cluster data for all three planes
    print(f"\nLoading cluster data for {cat_name}...")
    images_x, metadata_x = load_cluster_images(cat_name, 'X')
    images_u, metadata_u = load_cluster_images(cat_name, 'U')
    images_v, metadata_v = load_cluster_images(cat_name, 'V')
    
    print(f"  X plane: {images_x.shape[0]} clusters")
    print(f"  U plane: {images_u.shape[0]} clusters")
    print(f"  V plane: {images_v.shape[0]} clusters")
    
    # Get unique event IDs
    event_ids = np.unique(metadata_x[:, 0]).astype(int)
    print(f"\nFound {len(event_ids)} unique events")
    
    # Limit to max_events
    event_ids = event_ids[:max_events]
    print(f"Processing {len(event_ids)} events")
    
    # Process each event
    results = []
    
    for i, event_id in enumerate(event_ids):
        print(f"\nProcessing event {i+1}/{len(event_ids)}: {event_id}")
        
        # Get clusters for this event
        mask_x = (metadata_x[:, 0] == event_id)
        mask_u = (metadata_u[:, 0] == event_id)
        mask_v = (metadata_v[:, 0] == event_id)
        
        event_images_x = images_x[mask_x]
        event_images_u = images_u[mask_u]
        event_images_v = images_v[mask_v]
        
        # Get cluster energies (from metadata column 4, take absolute value)
        event_energies = np.abs(metadata_x[mask_x, 4])
        
        print(f"  Clusters: {len(event_images_x)}")
        print(f"  Energy range: [{event_energies.min():.2f}, {event_energies.max():.2f}] MeV")
        
        # Process with history
        result = process_event_with_history(
            event_id, event_images_x, event_images_u, event_images_v,
            event_energies, ed_model, pdf_interpolator, true_neutrino_direction
        )
        
        print(f"  MCMC: {result['mcmc_iterations']} iterations, " +
              f"success={result['mcmc_success']}")
        print(f"  Result: cos={result['cos_angle']:.3f}, angle={result['angle_deg']:.1f}°")
        
        results.append(result)
    
    # Generate plots
    print(f"\nGenerating investigation plots...")
    plot_investigation(results, output_pdf)
    
    # Save detailed JSON
    json_output = output_pdf.replace('.pdf', '_detail.json')
    with open(json_output, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✓ Investigation complete!")
    print(f"  PDF: {output_pdf}")
    print(f"  JSON: {json_output}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
