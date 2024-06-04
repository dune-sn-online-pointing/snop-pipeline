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

def logprior(args):
    if -np.pi < args[0] < np.pi and 0 < args[1] < np.pi:
        return 0
    return -np.inf

def logpost(args, pred_x, pred_y, pred_z):
    if not np.isfinite(logprior(args)):
        return -np.inf
    return logprior(args) + loglike(args, pred_x, pred_y, pred_z)


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

def run(input_data, predictions, output_folder):    
    output_folder = output_folder + "loglikelihood_results/"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    nwalkers = 100
    ndim = 2
    nsteps = 1000
    discard = 200
    initial_pos = np.array([-np.pi, 0]) + np.random.rand(nwalkers, ndim) * np.array([2*np.pi, np.pi])

    sampler = emcee.EnsembleSampler(nwalkers, ndim, logpost, args=[predictions[:, 0], predictions[:, 1], predictions[:, 2]], moves=[emcee.moves.MHMove(_custom_proposal)])

    sampler.run_mcmc(initial_pos, nsteps, progress=True);
    
    samples = sampler.get_chain()


    fig, axes = plt.subplots(figsize = (14, 16), ncols = 1, nrows = ndim)

    for i in range(ndim):
        for k in range(nwalkers):
            axes[i].plot(samples[: , k, i], alpha=0.7)
        axes[i].set_xlabel("Step number")

    plt.savefig(output_folder + "walkers.png")

    # Plot walk in the healpy map
    nside = 64
    npix = healpy.nside2npix(nside)
    # create a map with the number of pixels
    map_hp = np.zeros(npix)
    thetas, phis = samples[:, :, 0].flatten(), samples[:, :, 1].flatten()
    print(thetas)
    print(phis)
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
                        verbose=True,
                        plot_contours=True,
                        use_math_text=True,
                        quantiles=[0.16, 0.5, 0.84],
                        show_titles=True,
                        bins=50)
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
    print(f"Correctly computed theta: {avg_theta}")
    print(f"Correctly computed phi: {avg_phi}")
    
    # Compute the angles between the average direction and the walkers
    cos_angle_diff = (avg_x * x_walker + avg_y * y_walker + avg_z * z_walker) / (np.sqrt(avg_x**2 + avg_y**2 + avg_z**2) * np.sqrt(x_walker**2 + y_walker**2 + z_walker**2))
    cos_angle_diff = np.array(cos_angle_diff)  # Convert cos_angle_diff to a numpy array
    cos_angle_diff = np.where(cos_angle_diff > 1, 1, cos_angle_diff)  # Correct for numerical errors
    cos_angle_diff = np.where(cos_angle_diff < -1, -1, cos_angle_diff)  # Correct for numerical errors
    angle_diff = np.arccos(cos_angle_diff)

    plt.figure(figsize=(10, 8))

    plt.hist(angle_diff, bins=30)
    plt.xlabel("Angle difference")
    plt.ylabel("Frequency")
    plt.savefig(output_folder + "walkers_angle_diff.png")
    plt.clf()

    weight_for_angle_diff = 1/np.sin(angle_diff)


    # Compute the quantiles for the angle difference weighted
    indexes = np.argsort(angle_diff)
    angle_diff = angle_diff[indexes]
    weight_for_angle_diff = weight_for_angle_diff[indexes]
    cumsum = np.cumsum(weight_for_angle_diff)
    cumsum = cumsum / cumsum[-1]
    quantiles = np.quantile(cumsum, [0.68])
    print(f"Quantiles for the angle difference: {quantiles}")
    omega_resolution = angle_diff[np.where(cumsum > quantiles[0])[0][0]]
    print(f"Omega resolution: {omega_resolution}")
    

    plt.hist(angle_diff, bins=30, weights=weight_for_angle_diff)
    # add vertical lines for the quantiles
    plt.axvline(omega_resolution, color="red", label=f"68% quantile for $\omega$ error: {omega_resolution:.2f}")
    plt.legend()
    plt.xlabel("Angle difference")
    plt.ylabel("Frequency")
    plt.savefig(output_folder + "walkers_angle_diff_weighted.png")
    plt.clf()



    final_theta = circmean(flat_samples[:, 0], high=np.pi, low=-np.pi)
    final_theta_std = circstd(flat_samples[:, 0], high=np.pi, low=-np.pi)
    final_phi = np.mean(flat_samples[:, 1])
    final_phi_std = np.std(flat_samples[:, 1])

    print(f"Final theta: {final_theta} +- {final_theta_std}")
    print(f"Final phi: {final_phi} +- {final_phi_std}")
    return final_theta, final_phi, final_theta_std, final_phi_std, omega_resolution




