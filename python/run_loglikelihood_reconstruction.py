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
    # norm true

    pred_angles = from_coordinate_to_theta_phi(np.array([pred_x, pred_y, pred_z]).T)
    pred_theta, pred_phi = pred_angles[:, 0], pred_angles[:, 1]

    # calculate log likelihood
    mins = np.minimum(reco_theta, pred_theta)
    maxs = np.maximum(reco_theta, pred_theta)
    true_diff = maxs - mins
    true_diff = np.where(true_diff > np.pi, 2*np.pi - true_diff, true_diff)


    loglike = -np.sum((true_diff)**2 + (reco_phi - pred_phi)**2)
    
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
    new_state[:, 0] = (new_state[:, 0] + np.pi) % (2 * np.pi) - np.pi
    new_state[:, 1] = np.where(new_state[:, 1] > np.pi, np.pi, new_state[:, 1])
    new_state[:, 1] = np.where(new_state[:, 1] < 0, 0, new_state[:, 1])
    return new_state, np.ones(state.shape[0])



def run(input_data, predictions, output_folder):    
    output_folder = output_folder + "loglikelihood_results/"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    nwalkers = 100
    ndim = 2
    nsteps = 1000
    initial_pos = np.array([-np.pi, 0]) + np.random.rand(nwalkers, ndim) * np.array([2*np.pi, np.pi])

    sampler = emcee.EnsembleSampler(nwalkers, ndim, logpost, args=[predictions[:, 0], predictions[:, 1], predictions[:, 2]], moves=[emcee.moves.MHMove(_custom_proposal)])

    sampler.run_mcmc(initial_pos, 1000, progress=True);
    
    samples = sampler.get_chain()


    fig, axes = plt.subplots(figsize = (17, 24), ncols = 1, nrows = ndim)

    for i in range(ndim):
        for k in range(nwalkers):
            axes[i].plot(samples[: , k, i], alpha=0.7)
        axes[i].set_xlabel("Step number")

    plt.savefig(output_folder + "walkers.png")

    flat_samples = sampler.get_chain(flat=True, discard=100)

    fig = corner.corner(flat_samples,  
                        verbose = True,
                        plot_contours = True,
                        use_math_text = True,
                        quantiles = [0.025, 0.5, 0.975], show_titles=True)
    plt.savefig(output_folder + "corner.png")

    final_theta = circmean(flat_samples[:, 0], high=np.pi, low=-np.pi)
    final_theta_std = circstd(flat_samples[:, 0], high=np.pi, low=-np.pi)
    final_phi = np.mean(flat_samples[:, 1])
    final_phi_std = np.std(flat_samples[:, 1])

    print(f"Final theta: {final_theta} +- {final_theta_std}")
    print(f"Final phi: {final_phi} +- {final_phi_std}")
    return final_theta, final_phi, final_theta_std, final_phi_std




