import os
import numpy as np
import healpy
import matplotlib.pyplot as plt
import emcee
import corner
from scipy.stats import circmean, circstd

from run_pointing_tests import from_coordinate_to_theta_phi

def loglike(args, pred_x, pred_y, pred_z):
    reco_theta, reco_phi = args[0], args[1]

    # norm predictions
    r = np.sqrt(pred_x**2 + pred_y**2 + pred_z**2)
    pred_x = pred_x/r
    pred_y = pred_y/r
    pred_z = pred_z/r

    reco_x = np.sin(reco_phi) * np.cos(reco_theta)
    reco_z = np.sin(reco_phi) * np.sin(reco_theta)
    reco_y = np.cos(reco_phi)

    cos_angle_diff = (reco_x * pred_x + reco_y * pred_y + reco_z * pred_z) / (np.sqrt(reco_x**2 + reco_y**2 + reco_z**2) * np.sqrt(pred_x**2 + pred_y**2 + pred_z**2))

    cos_angle_diff = np.array(cos_angle_diff)  # Convert cos_angle_diff to a numpy array
    cos_angle_diff = np.where(cos_angle_diff > 1, 1, cos_angle_diff)  # Correct for numerical errors
    cos_angle_diff = np.where(cos_angle_diff < -1, -1, cos_angle_diff)  # Correct for numerical errors
    angle_diff = np.arccos(cos_angle_diff)
    

    loglike = -np.sum(angle_diff**2)
    return loglike

def loglike_E_weighted(args, pred_x, pred_y, pred_z, E):
    reco_theta, reco_phi = args[0], args[1]

    # norm predictions
    r = np.sqrt(pred_x**2 + pred_y**2 + pred_z**2)
    pred_x = pred_x/r
    pred_y = pred_y/r
    pred_z = pred_z/r

    reco_x = np.sin(reco_phi) * np.cos(reco_theta)
    reco_z = np.sin(reco_phi) * np.sin(reco_theta)
    reco_y = np.cos(reco_phi)

    cos_angle_diff = (reco_x * pred_x + reco_y * pred_y + reco_z * pred_z) / (np.sqrt(reco_x**2 + reco_y**2 + reco_z**2) * np.sqrt(pred_x**2 + pred_y**2 + pred_z**2))

    cos_angle_diff = np.array(cos_angle_diff)  # Convert cos_angle_diff to a numpy array
    cos_angle_diff = np.where(cos_angle_diff >= 1.0, 0.999, cos_angle_diff)  # Correct for numerical errors
    cos_angle_diff = np.where(cos_angle_diff <= -1.0, -0.999, cos_angle_diff)  # Correct for numerical errors
    # angle_diff = np.arccos(cos_angle_diff)

    # sigma = 1/E
    # loglike = -np.sum(angle_diff**2/(2*sigma**2) + np.log(sigma))
    # print(loglike)
    # energy_bins = np.load(input_data["loglikelihood"]["energy_bins"])
    # cos_bins = np.load(input_data["loglikelihood"]["cos_bins"])
    # pdf2d = np.load(input_data["loglikelihood"]["pdf2d"])

    energy_bins = np.load("/afs/cern.ch/work/d/dapullia/public/dune/playground/create_2dpdf_pointing/energy_bins.npy")
    cos_bins = np.load("/afs/cern.ch/work/d/dapullia/public/dune/playground/create_2dpdf_pointing/cos_bins.npy")
    pdf2d = np.load("/afs/cern.ch/work/d/dapullia/public/dune/playground/create_2dpdf_pointing/cosine_vs_energy.npy")

    loglike = np.sum(np.log(pdf2d[np.digitize(cos_angle_diff, cos_bins)-1, np.digitize(E, energy_bins)-1]))


    return loglike

def logprior(args):
    if args[0] < -np.pi or args[0] > np.pi:
        return -np.inf
    if args[1] < 0 or args[1] > np.pi:
        return -np.inf
    return np.log(np.sin(args[1]))

def logpost(args, pred_x, pred_y, pred_z):
    if not np.isfinite(logprior(args)):
        return -np.inf
    return logprior(args) + loglike(args, pred_x, pred_y, pred_z)

def logpost_E_weighted(args, pred_x, pred_y, pred_z, E):
    if not np.isfinite(logprior(args)):
        return -np.inf
    return logprior(args) + loglike_E_weighted(args, pred_x, pred_y, pred_z, E)


def _custom_proposal(state, random):
    new_state = np.copy(state)
    new_state[:, 0] = random.normal(state[:, 0], 0.1)
    new_state[:, 1] = random.normal(state[:, 1], 0.1)
    new_state[:, 0] = np.where(new_state[:, 1] > np.pi, new_state[:, 0] + np.pi, new_state[:, 0])
    new_state[:, 0] = np.where(new_state[:, 1] < 0, new_state[:, 0] + np.pi, new_state[:, 0])
    new_state[:, 0] = (new_state[:, 0] + np.pi) % (2 * np.pi) - np.pi

    new_state[:, 1] = np.where(new_state[:, 1] > np.pi, np.pi-(new_state[:, 1] - np.pi), new_state[:, 1])
    new_state[:, 1] = np.where(new_state[:, 1] < 0, -new_state[:, 1], new_state[:, 1])

    # new_state[:, 1] = np.where(new_state[:, 1] > np.pi, np.pi, new_state[:, 1])
    # new_state[:, 1] = np.where(new_state[:, 1] < 0, 0, new_state[:, 1])
    

    return new_state, np.ones(state.shape[0])

def run(input_data, predictions, E, output_folder):    
    output_folder = output_folder + input_data["loglikelihood"]["output_folder"]
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    nwalkers = input_data["loglikelihood"]["n_walkers"]
    ndim = 2
    nsteps = input_data["loglikelihood"]["n_steps"]
    discard = input_data["loglikelihood"]["discard"]
    initial_pos = np.array([-np.pi, 0]) + np.random.rand(nwalkers, ndim) * np.array([2*np.pi, np.pi])

    if E is None:
        sampler = emcee.EnsembleSampler(nwalkers, ndim, logpost, args=[predictions[:, 0], predictions[:, 1], predictions[:, 2]], moves=[emcee.moves.MHMove(_custom_proposal)])
    else:
        sampler = emcee.EnsembleSampler(nwalkers, ndim, logpost_E_weighted, args=[predictions[:, 0], predictions[:, 1], predictions[:, 2], E], moves=[emcee.moves.MHMove(_custom_proposal)])

    sampler.run_mcmc(initial_pos, nsteps, progress=False)
    
    samples = sampler.get_chain()


    fig, axes = plt.subplots(figsize = (14, 16), ncols = 1, nrows = ndim)

    for i in range(ndim):
        for k in range(nwalkers):
            axes[i].plot(samples[: , k, i], alpha=0.7)
        axes[i].set_xlabel("Step number")

    plt.savefig(output_folder + "walkers.png")
    plt.close()
    
    # Plot walk in the healpy map
    nside = 64
    npix = healpy.nside2npix(nside)
    # create a map with the number of pixels
    map_hp = np.zeros(npix)
    thetas, phis = samples[:, :, 0].flatten(), samples[:, :, 1].flatten()
    thetas = np.mod(thetas, 2*np.pi)
    phis = np.mod(phis, np.pi)
    # get the indices
    indices = healpy.ang2pix(nside, phis, thetas)
    # fill the map
    for index in indices:
        map_hp[index] += 1
    
    map_hp = np.where(map_hp == 0, healpy.UNSEEN, map_hp)

    plt.figure(figsize=(14, 10))
    healpy.mollview(map_hp, title="Walkers map", cmap="viridis")
    healpy.graticule()
    plt.savefig(output_folder + "walkers_map.png")
    plt.clf()




    flat_samples = sampler.get_chain(flat=True, discard=discard)

    fig = corner.corner(flat_samples,  
                        verbose=False,
                        plot_contours=True,
                        use_math_text=True,
                        quantiles=[0.16, 0.5, 0.84],
                        show_titles=True,
                        bins=50,
                        labels=[r"$\theta$ [rad]", r"$\phi$ [rad]"],
                        label_kwargs={"fontsize": 14},
                        title_kwargs={"fontsize": 14}
                        )
    fig.figsize = (10, 10)
    plt.savefig(output_folder + "corner.png")
    plt.clf()

    # Compute the final results
    x_walker = np.sin(flat_samples[:, 1]) * np.cos(flat_samples[:, 0])
    z_walker = np.sin(flat_samples[:, 1]) * np.sin(flat_samples[:, 0])
    y_walker = np.cos(flat_samples[:, 1])

    # get the mean direction
    avg_x = np.mean(x_walker)
    avg_y = np.mean(y_walker)
    avg_z = np.mean(z_walker)

    avg_x = avg_x / np.sqrt(avg_x**2 + avg_y**2 + avg_z**2)
    avg_y = avg_y / np.sqrt(avg_x**2 + avg_y**2 + avg_z**2)
    avg_z = avg_z / np.sqrt(avg_x**2 + avg_y**2 + avg_z**2)

    avg_theta = np.arctan2(avg_z, avg_x)
    avg_phi = np.arccos(avg_y)
    
    # Compute the angles between the average direction and the walkers
    cos_angle_diff = (avg_x * x_walker + avg_y * y_walker + avg_z * z_walker) / (np.sqrt(avg_x**2 + avg_y**2 + avg_z**2) * np.sqrt(x_walker**2 + y_walker**2 + z_walker**2))
    cos_angle_diff = np.array(cos_angle_diff)  # Convert cos_angle_diff to a numpy array
    cos_angle_diff = np.where(cos_angle_diff > 1, 1, cos_angle_diff)  # Correct for numerical errors
    cos_angle_diff = np.where(cos_angle_diff < -1, -1, cos_angle_diff)  # Correct for numerical errors
    angle_diff = np.arccos(cos_angle_diff)

    angle_diff_sorted = np.sort(angle_diff)
    cumsum_angle_diff = np.cumsum(angle_diff_sorted)
    cumsum_angle_diff = cumsum_angle_diff / cumsum_angle_diff[-1]
    correct_quantile_index_angle_diff = np.where(cumsum_angle_diff > 0.68)[0][0]
    omega_resolution = angle_diff_sorted[correct_quantile_index_angle_diff]
    plt.figure(figsize=(10, 8))

    plt.hist(angle_diff, bins=30)
    # add vertical lines for the quantiles
    plt.axvline(omega_resolution, color="red", label=f"68% quantile for angle error: {omega_resolution:.2f}")
    plt.xlabel("Angle difference")
    plt.ylabel("Frequency")
    plt.legend()
    plt.savefig(output_folder + "walkers_angle_diff.png")
    plt.clf()


    final_theta_std = circstd(flat_samples[:, 0], high=np.pi, low=-np.pi)
    final_phi_std = np.std(flat_samples[:, 1])

    # print(f"Final theta: {avg_theta} +- {final_theta_std}")
    # print(f"Final phi: {avg_phi} +- {final_phi_std}")
    print(f"Final theta: {avg_theta} +- {final_theta_std}")
    print(f"Final phi: {avg_phi} +- {final_phi_std}")
    print(f"Omega resolution: {omega_resolution}")
    np.save(output_folder + "likelihood_results.npy", np.array([avg_theta, avg_phi, final_theta_std, final_phi_std, omega_resolution]))

    return avg_theta, avg_phi, final_theta_std, final_phi_std, omega_resolution




