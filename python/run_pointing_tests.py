import os
import numpy as np
import healpy
import matplotlib.pyplot as plt


def run(input_data, predictions, output_folder):    
    true_dir_exists = os.path.exists(output_folder + input_data["ctds"]["output_folder"] + "/dataset/dataset_label_true_dir.npy")

    if not true_dir_exists:
        true_dir = None
    else:
        true_dir = np.load(output_folder + input_data["ctds"]["output_folder"] + "/dataset/dataset_label_true_dir.npy")

    study(predictions=predictions, true_dir=true_dir, output_folder=output_folder)

def study(predictions, true_dir=None, output_folder=""):
    output_folder = output_folder + "pointing_results/"
    x, y, z = predictions[:, 0], predictions[:, 1], predictions[:, 2]
    x_true, y_true, z_true = true_dir[:, 0], true_dir[:, 1], true_dir[:, 2]
    print(f"Predictions: {predictions.shape}")
    print(f"True: {true_dir.shape}")

    save_labels_in_a_map(true_dir, predictions, output_folder)
    if true_dir is not None:
        plot_diff(true_dir, predictions, output_folder)

def from_coordinate_to_theta_phi(coords):
    # nomalize the coordinates
    coords = coords/np.linalg.norm(coords, axis=1)[:, np.newaxis]
    x, y, z = coords[:,0], coords[:,1], coords[:,2]
    r = np.sqrt(x**2 + y**2 + z**2)

    phi = np.arccos(y/r)
    theta = np.arctan2(z, x)

    return np.array([theta, phi]).T

def plot_diff(test_labels, predictions, output_folder):
    pred_x, pred_y, pred_z = predictions[:, 0], predictions[:, 1], predictions[:, 2]
    true_x, true_y, true_z = test_labels[:, 0], test_labels[:, 1], test_labels[:, 2]

    # norm predictions
    r = np.sqrt(pred_x**2 + pred_z**2)
    pred_x = pred_x/r
    pred_y = pred_y/r
    pred_z = pred_z/r

    true_angles = from_coordinate_to_theta_phi(test_labels)
    true_theta, true_phi = true_angles[:, 0], true_angles[:, 1]
    pred_angles = from_coordinate_to_theta_phi(predictions) 
    pred_theta, pred_phi = pred_angles[:, 0], pred_angles[:, 1]
   
    plt.hist(true_theta, bins=50, alpha=0.5, label="True", range=(-np.pi, np.pi))   
    plt.hist(pred_theta, bins=50, alpha=0.5, label="Predicted", range=(-np.pi, np.pi))
    plt.title("True and Predicted thetas")
    plt.legend()
    plt.xlabel("Theta [Rad]")
    plt.legend(loc='upper right')
    plt.savefig(output_folder+'thetas.png')
    plt.clf()

    plt.hist(true_phi, bins=50, alpha=0.5, label="True", range=(0, np.pi))
    plt.hist(pred_phi, bins=50, alpha=0.5, label="Predicted", range=(0, np.pi))
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

    # flat distribution
    theta_flat = np.random.uniform(-np.pi, np.pi, len(true_x))
    cosines_flat = np.cos(theta_flat)
    cosines = (true_x * pred_x + true_z * pred_z) / (np.sqrt(true_x**2 + true_z**2) * np.sqrt(pred_x**2 + pred_z**2))

    plt.hist(cosines, bins=50, alpha=1, label="Cos($\\theta_{true}-\\theta_{pred}$)")
    plt.hist(cosines_flat, bins=50, alpha=0.2, label="Cos($\\theta_{true}-\\theta_{flat}$)", hatch='xx')
    plt.xlabel("Cos($\\theta$)")
    plt.title("Cosine between true and predicted direction")
    plt.legend()
    plt.savefig(output_folder+'cosine.png')
    plt.clf()

    # plot the difference
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
    plt.title("Angle difference between true and predicted direction")
    plt.legend()
    plt.savefig(output_folder+'difference.png')
    plt.clf()

    plt.hist(true_theta-pred_theta, bins=50, alpha=0.5, label="True")
    plt.hist(true_theta-theta_flat, bins=50, alpha=0.5, label="Flat")
    plt.xlabel("True - Predicted")
    plt.legend()
    plt.savefig(output_folder+'difference_not_correct.png')
    plt.clf()
    
def save_labels_in_a_map(true_dir, predictions, output_folder):
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

    # if true_dir is not None:
    #     angle_true = from_coordinate_to_theta_phi(true_dir)
    #     thetas_true, phis_true = angle_true[:,0], angle_true[:,1]
    #     indices_true = healpy.ang2pix(nside, phis_true, thetas_true)
    #     for index in indices_true:
    #         map[index] += 1


    map_hp = healpy.smoothing(map_hp, fwhm=0.1)
    healpy.mollview(map_hp, title="Predictions", cmap="viridis")
    healpy.graticule()




    plt.savefig(output_folder+"map.png")
    plt.close()
