import os
import numpy as np
import healpy
import matplotlib.pyplot as plt
# set the font size of the plots
plt.rcParams.update({'font.size': 18})
# and of the ticks
plt.rcParams.update({'xtick.labelsize': 18})
plt.rcParams.update({'ytick.labelsize': 18})
# and of the legend
plt.rcParams.update({'legend.fontsize': 16})
# and of the axes
plt.rcParams.update({'axes.labelsize': 18})
# set figure size
plt.rcParams.update({'figure.figsize': (13, 13)})


def run(input_data, predictions, output_folder, final_theta=None, final_phi=None, final_theta_std=None, final_phi_std=None):
    true_dir_exists = os.path.exists(output_folder + input_data["ctds"]["output_folder"] + "/dataset/dataset_label_true_dir.npy")

    if not true_dir_exists:
        true_dir = None
    else:
        true_dir = np.load(output_folder + input_data["ctds"]["output_folder"] + "/dataset/dataset_label_true_dir.npy")

    study(predictions=predictions, true_dir=true_dir, output_folder=output_folder, final_theta=final_theta, final_phi=final_phi, final_theta_std=final_theta_std, final_phi_std=final_phi_std)

def study(predictions, true_dir=None, output_folder="", final_theta=None, final_phi=None, final_theta_std=None, final_phi_std=None):
    output_folder = output_folder + "pointing_results/"
    x, y, z = predictions[:, 0], predictions[:, 1], predictions[:, 2]
    print(f"Predictions: {predictions.shape}")
    if true_dir is not None:
        x_true, y_true, z_true = true_dir[:, 0], true_dir[:, 1], true_dir[:, 2]
        print(f"True: {true_dir.shape}")

    save_labels_in_a_map(predictions, output_folder, name="map_predictions")
    if true_dir is not None:
        if final_theta is not None and final_phi is not None:
            plot_diff(true_dir, predictions, output_folder, final_theta, final_phi, final_theta_std, final_phi_std)
        else:
            plot_diff(true_dir, predictions, output_folder)
        save_labels_in_a_map(true_dir, output_folder, name="map_true")
        true_angles = from_coordinate_to_theta_phi(true_dir)
        true_theta, true_phi = true_angles[:, 0], true_angles[:, 1]
        print(f"True theta: {np.unique(true_theta)}")
        print(f"True phi: {np.unique(true_phi)}")

def from_coordinate_to_theta_phi(coords):
    # nomalize the coordinates
    coords = coords/np.linalg.norm(coords, axis=1)[:, np.newaxis]
    x, y, z = coords[:,0], coords[:,1], coords[:,2]
    r = np.sqrt(x**2 + y**2 + z**2)

    phi = np.arccos(y/r)
    theta = np.arctan2(z, x)

    return np.array([theta, phi]).T


def plot_diff(true_dir, predictions, output_folder, final_theta=None, final_phi=None, final_theta_std=None, final_phi_std=None):
    pred_x, pred_y, pred_z = predictions[:, 0], predictions[:, 1], predictions[:, 2]
    true_x, true_y, true_z = true_dir[:, 0], true_dir[:, 1], true_dir[:, 2]

    # norm predictions
    r = np.sqrt(pred_x**2 + pred_z**2 + pred_y**2)
    pred_x = pred_x/r
    pred_y = pred_y/r
    pred_z = pred_z/r

    true_angles = from_coordinate_to_theta_phi(true_dir)
    true_theta, true_phi = true_angles[:, 0], true_angles[:, 1]
    pred_angles = from_coordinate_to_theta_phi(predictions) 
    pred_theta, pred_phi = pred_angles[:, 0], pred_angles[:, 1]
   
    plt.hist(pred_theta, bins=50, alpha=0.5, label="Predicted", range=(-np.pi, np.pi))
    unique_true_theta = np.unique(true_theta)
    if len(unique_true_theta) > 1:
        plt.hist(true_theta, bins=50, alpha=0.5, label="True", range=(-np.pi, np.pi))
    else:
        plt.axvline(unique_true_theta[0], color='b', linestyle='solid', linewidth=2, label="True Theta")

    if final_theta is not None:
        # add a line with the final theta 
        plt.axvline(final_theta, color='r', linestyle='dashed', linewidth=2, label="Final Theta")
        upper_bound = (final_theta + final_theta_std + np.pi) % (2 * np.pi) - np.pi
        lower_bound = (final_theta - final_theta_std + np.pi) % (2 * np.pi) - np.pi
        plt.axvline(upper_bound, color='r', linestyle='dotted', linewidth=2, label="Final Theta + Std")
        plt.axvline(lower_bound, color='r', linestyle='dotted', linewidth=2, label="Final Theta - Std")

    plt.title("True and Predicted thetas")
    plt.legend()
    plt.xlabel("Theta [Rad]")
    plt.legend(loc='upper right')
    plt.savefig(output_folder+'thetas.png')
    plt.clf()


    plt.hist(pred_phi, bins=50, alpha=0.5, label="Predicted", range=(0, np.pi))
    unique_true_phi = np.unique(true_phi)
    if len(unique_true_phi) > 1:
        plt.hist(true_phi, bins=50, alpha=0.5, label="True", range=(0, np.pi))
    else:
        plt.axvline(unique_true_phi[0], color='b', linestyle='solid', linewidth=2, label="True Phi")

    if final_phi is not None:
        # add a line with the final phi 
        plt.axvline(final_phi, color='r', linestyle='dashed', linewidth=2, label="Final Phi")
        plt.axvline(np.min([final_phi + final_phi_std, np.pi]), color='r', linestyle='dotted', linewidth=2, label="Final Phi + Std")
        plt.axvline(np.max([final_phi - final_phi_std, 0]), color='r', linestyle='dotted', linewidth=2, label="Final Phi - Std")       

    plt.title("True and Predicted phis")
    plt.legend()
    plt.xlabel("Phi [Rad]")
    plt.legend(loc='upper right')
    plt.savefig(output_folder+'phis.png')
    plt.clf()

    plt.hist(true_x, bins=50, alpha=0.5, label="True")
    plt.hist(pred_x, bins=50, alpha=0.5, label="Predicted")
    plt.title("X")
    plt.legend(loc='upper right')
    plt.savefig(output_folder+'x.png')
    plt.clf()

    plt.hist(true_y, bins=50, alpha=0.5, label="True")
    plt.hist(pred_y, bins=50, alpha=0.5, label="Predicted")
    plt.title("Y")
    plt.legend(loc='upper right')
    plt.savefig(output_folder+'y.png')
    plt.clf()

    plt.hist(true_z, bins=50, alpha=0.5, label="True")
    plt.hist(pred_z, bins=50, alpha=0.5, label="Predicted")
    plt.title("Z")
    plt.legend(loc='upper right')
    plt.savefig(output_folder+'z.png')
    plt.clf()

    # plot the difference in theta
    # flat distribution
    theta_flat = np.random.uniform(-np.pi, np.pi, len(true_x))
    cosines_flat = np.cos(theta_flat)
    cosines = (true_x * pred_x + true_z * pred_z) / (np.sqrt(true_x**2 + true_z**2) * np.sqrt(pred_x**2 + pred_z**2))

    plt.hist(cosines, bins=50, alpha=1, label="Cos($\\theta_{true}-\\theta_{pred}$)")
    plt.hist(cosines_flat, bins=50, alpha=0.2, label="Cos($\\theta_{true}-\\theta_{flat}$)", hatch='xx')
    plt.xlabel("Cos($\\theta$)")
    plt.title("Cosine between true and predicted theta")
    plt.legend()
    plt.savefig(output_folder+'cosine_theta.png')
    plt.clf()

    mins = np.minimum(true_theta, pred_theta)
    maxs = np.maximum(true_theta, pred_theta)
    true_diff = maxs - mins
    true_diff = np.where(true_diff > np.pi, 2*np.pi - true_diff, true_diff)

    mins_flat = np.minimum(true_theta, theta_flat)
    maxs_flat = np.maximum(true_theta, theta_flat)
    flat_diff = maxs_flat - mins_flat
    flat_diff = np.where(flat_diff > np.pi, 2*np.pi - flat_diff, flat_diff)

    plt.hist(true_diff, bins=50, alpha=1, label="$\\theta_{true}-\\theta_{pred}$")
    plt.hist(flat_diff, bins=50, alpha=0.2, label="$\\theta_{true}-\\theta_{flat}$", hatch='xx')
    plt.xlabel("Angle Difference [Rad]")
    plt.title("Angle difference between true and predicted theta")
    plt.legend()
    plt.savefig(output_folder+'difference_theta.png')
    plt.clf()

    plt.hist(true_theta-pred_theta, bins=50, alpha=0.5, label="True")
    plt.hist(true_theta-theta_flat, bins=50, alpha=0.5, label="Flat")
    plt.xlabel("True - Predicted")
    plt.legend()
    plt.savefig(output_folder+'difference_theta_not_correct.png')
    plt.clf()

    # plot the difference in phi
    # flat distribution
    phi_flat = np.random.uniform(0, np.pi, len(true_x))
    cosines_flat = np.cos(phi_flat)
    phi_true = np.arccos(true_y/np.sqrt(true_x**2 + true_y**2 + true_z**2))
    phi_pred = np.arccos(pred_y/np.sqrt(pred_x**2 + pred_y**2 + pred_z**2))
    diff_phi = np.abs(phi_true - phi_pred)    
    cosine_diff_phi = np.cos(diff_phi)

    plt.hist(cosine_diff_phi, bins=50, alpha=1, label="Cos($\\phi_{true}-\\phi_{pred}$)")
    plt.hist(cosines_flat, bins=50, alpha=0.2, label="Cos($\\phi_{true}-\\phi_{flat}$)", hatch='xx')
    plt.xlabel("Cos($\\phi$)")
    plt.title("Cosine between true and predicted phi")
    plt.legend()
    plt.savefig(output_folder+'cosine_phi.png')
    plt.clf()

    plt.hist(diff_phi, bins=50, alpha=1, label="$\\phi_{true}-\\phi_{pred}$")
    plt.hist(np.abs(phi_true - phi_flat), bins=50, alpha=0.2, label="$\\phi_{true}-\\phi_{flat}$", hatch='xx')
    plt.xlabel("Angle Difference [Rad]")
    plt.title("Angle difference between true and predicted phi")
    plt.legend()
    plt.savefig(output_folder+'difference_phi.png')
    plt.clf()

    # plot the difference in the 3D space
    flat_omega = np.random.uniform(0, np.pi, len(true_x))
    complete_cos_omega = (true_x * pred_x + true_y * pred_y + true_z * pred_z) / (np.sqrt(true_x**2 + true_y**2 + true_z**2) * np.sqrt(pred_x**2 + pred_y**2 + pred_z**2))
    complete_omega = np.arccos(complete_cos_omega)
    plt.hist(complete_cos_omega, bins=50, alpha=1, label="Cos($\\omega$)")
    plt.hist(np.cos(flat_omega), bins=50, alpha=0.2, label="Cos($\\omega_{flat}$)", hatch='xx')
    plt.xlabel("Cos($\\omega$)")
    plt.title("Cosine between true and predicted direction in the 3D space")
    plt.legend()
    plt.savefig(output_folder+'cosine_3D.png')
    plt.clf()

    omega_weight = 1/np.sin(complete_omega)
    flat_omega_weight = 1/np.sin(flat_omega)
    plt.hist(complete_omega, bins=50, alpha=1, label="$\\omega$", weights=omega_weight)
    plt.hist(flat_omega, bins=50, alpha=0.2, label="$\\omega_{flat}$", hatch='xx', weights=flat_omega_weight)
    plt.xlabel("$\\omega$")
    plt.title("Angle between true and predicted direction in the 3D space")
    plt.legend()
    plt.savefig(output_folder+'angle_3D.png')
    plt.clf()


def save_labels_in_a_map(predictions, output_folder, name="map"):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    nside = 64
    npix = healpy.nside2npix(nside)
    # create a map with the number of pixels
    map_hp = np.zeros(npix)
    angles = from_coordinate_to_theta_phi(predictions)
    thetas, phis = angles[:,0], angles[:,1]

    plt.figure(figsize=(10, 10))
    plt.title("Labels map")
    thetas = np.mod(thetas, 2*np.pi)
    phis = np.mod(phis, np.pi)
    # get the indices
    indices = healpy.ang2pix(nside, phis, thetas)
    # fill the map
    for index in indices:
        map_hp[index] += 1

    map_hp = healpy.smoothing(map_hp, fwhm=0.1)
    healpy.mollview(map_hp, title=name, cmap="viridis")
    healpy.graticule()
    plt.savefig(output_folder+name+".png")
    plt.close()
