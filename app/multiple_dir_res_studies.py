import numpy as np
import json
import os
import sys
import argparse
import time
import healpy 

sys.path.append("../python/")

import run_clustering # Read data, run clustering, save results
import run_ctds # Read clusters and create dataset
import run_mt_id # Read dataset and identify Main Tracks
import run_volume # Read Main Tracks and calculate volume
import run_int_class # Read Main Tracks and classify interactions
import run_pointing # Read dataset and predict pointing
import run_match_clusters # Read clusters and match them
import run_pointing_tests # Read dataset and predictions and run tests
import run_loglikelihood_reconstruction # Read dataset and predictions and run tests
import general_libs # Create report
sys.path.append("../submodules/online-pointing-utils/python/")
from image_creator import *
from utils import *
from cluster import *
from dataset_creator import *

parser = argparse.ArgumentParser(description='Run the pipeline')
parser.add_argument('--input_json', type=str, help='Input json file')
parser.add_argument('--output_folder', type=str, help='Output folder')
parser.add_argument('--delete_view', type=str, help='Delete view', default="")
args = parser.parse_args()

input_json = args.input_json
output_folder = args.output_folder
delete_view = args.delete_view

# Read input json
with open(input_json) as f:
    input_data = json.load(f)

if not os.path.exists(output_folder):
    os.makedirs(output_folder)

# Dump the json file
with open(output_folder + "input.json", "w") as f:
    json.dump(input_data, f, indent=4)

overall_start = time.time()

# Run clustering
print("Running clustering")
start = time.time()
run_clustering.run(input_data, output_folder)
end = time.time()
print("Clustering done in", end - start, "seconds")

# Run cluster matching
print("Running cluster matching")
start = time.time()
run_match_clusters.run(input_data, output_folder)
end = time.time()
print("Cluster matching done in", end - start, "seconds")

# Run clusters to dataset
print("Running clusters to dataset")
ctds_dataset_img = None
start = time.time()
ctds_dataset_img = run_ctds.run(input_data, output_folder)
end = time.time()
print("Clusters to dataset done in", end - start, "seconds")

ctds_dataset_img = np.load(output_folder + input_data["ctds"]["output_folder"] + "/dataset/dataset_img.npy")
if ctds_dataset_img is None:
    print("No dataset_img created, exiting...")
    sys.exit(0)


if delete_view=="U":
    ctds_dataset_img[:,:,:,0] = np.zeros(ctds_dataset_img[:,:,:,0].shape)
elif delete_view=="V":
    ctds_dataset_img[:,:,:,1] = np.zeros(ctds_dataset_img[:,:,:,0].shape)
elif delete_view=="X":
    ctds_dataset_img[:,:,:,2] = np.zeros(ctds_dataset_img[:,:,:,0].shape)

true_dir = np.load(output_folder + input_data["ctds"]["output_folder"] + "/dataset/dataset_label_true_dir.npy")
true_x, true_y, true_z = true_dir[:,0], true_dir[:,1], true_dir[:,2]
unique_true_x = np.unique(true_x)
unique_true_y = np.unique(true_y)
unique_true_z = np.unique(true_z)

if len(unique_true_x) != len(unique_true_y) or len(unique_true_x) != len(unique_true_z) or len(unique_true_y) != len(unique_true_z):
    print("Error: true_x, true_y and true_z are not the same")
    sys.exit(0)


omega_resolutions = []
true_errors = []
reso_distances = []
true_dirs = []
n_tracks = []
total_predictions = np.array([])
total_true_dirs = np.array([])
total_energies = np.array([])

for i in range(len(unique_true_x)):
    print("Event", i, "of", len(unique_true_x), "events")
    index = np.where(true_x == unique_true_x[i])
    ctds_dataset_img_i = ctds_dataset_img[index]
    n_tracks.append(ctds_dataset_img_i.shape[0])
    true_dir_i = true_dir[index]
    true_x_i = true_dir_i[0,0]
    true_y_i = true_dir_i[0,1]
    true_z_i = true_dir_i[0,2]
    true_dirs.append([true_x_i, true_y_i, true_z_i])
    if input_data["loglikelihood"]["energy_weight"]:
        # E is the sum of the pixel values in the X plane image
        E = np.sum(ctds_dataset_img_i[:,:,:,2], axis=(1,2))
        E = np.sqrt(E)
        E = E / np.max(E)
    else:
        E = None


    predictions = run_pointing.run(input_data, ctds_dataset_img_i, output_folder)

    total_predictions = np.concatenate((total_predictions, predictions))
    total_true_dirs = np.concatenate((total_true_dirs, true_dir_i))
    total_energies = np.concatenate((total_energies, np.sum(ctds_dataset_img_i[:,:,:,2], axis=(1,2))))


    final_theta, final_phi, final_theta_std, final_phi_std, omega_resolution = run_loglikelihood_reconstruction.run(input_data, predictions, E, output_folder)

    reco_x = np.sin(final_phi) * np.cos(final_theta)
    reco_z = np.sin(final_phi) * np.sin(final_theta)
    reco_y = np.cos(final_phi)

    cos_angle_diff = (reco_x * true_x_i + reco_y * true_y_i + reco_z * true_z_i) / (np.sqrt(reco_x**2 + reco_y**2 + reco_z**2) * np.sqrt(true_x_i**2 + true_y_i**2 + true_z_i**2))
    cos_angle_diff = np.array(cos_angle_diff)  # Convert cos_angle_diff to a numpy array
    cos_angle_diff = np.where(cos_angle_diff > 1, 1, cos_angle_diff)  # Correct for numerical errors
    cos_angle_diff = np.where(cos_angle_diff < -1, -1, cos_angle_diff)  # Correct for numerical errors
    angle_diff = np.arccos(cos_angle_diff)
    print("angle_diff =", angle_diff)
    print(angle_diff.shape)
    omega_resolutions.append(omega_resolution)
    true_errors.append(angle_diff)
    reso_distances.append(angle_diff/omega_resolution)


# save the results
true_errors = np.array(true_errors)
reso_distances = np.array(reso_distances)
omega_resolutions = np.array(omega_resolutions)
true_dirs = np.array(true_dirs)
n_tracks = np.array(n_tracks)
np.save(output_folder + "true_errors.npy", true_errors)
np.save(output_folder + "reso_distances.npy", reso_distances)
np.save(output_folder + "omega_resolutions.npy", omega_resolutions)
np.save(output_folder + "true_dirs.npy", true_dirs)
np.save(output_folder + "n_tracks.npy", n_tracks)


true_errors = np.load(output_folder + "true_errors.npy")
reso_distances = np.load(output_folder + "reso_distances.npy")
reso_distances = np.ones_like(reso_distances) 
omega_resolutions = np.load(output_folder + "omega_resolutions.npy")
true_dirs = np.load(output_folder + "true_dirs.npy")
n_tracks = np.load(output_folder + "n_tracks.npy")
print(f"True errors: {true_errors.shape}")
print(f"Resolution distances: {reso_distances.shape}")
print(f"Omega resolutions: {omega_resolutions.shape}")
print(f"True dirs: {true_dirs.shape}")
print(f"Number of tracks: {n_tracks.shape}")


indexes = np.argsort(true_errors)
true_errors = true_errors[indexes]
reso_distances = reso_distances[indexes]
omega_resolutions = omega_resolutions[indexes]
true_dirs = true_dirs[indexes]
n_tracks = n_tracks[indexes]

plt.figure(figsize=(10, 10))    
plt.hist(n_tracks, bins=20)
plt.xlabel("Number of tracks")
plt.ylabel("Frequency")
plt.title("Number of tracks")
plt.savefig(output_folder + "n_tracks.png")
plt.clf()



cumsum_true_errors = np.cumsum(np.ones_like(true_errors))
cumsum_true_errors = cumsum_true_errors / cumsum_true_errors[-1]
correct_quantile_index_true_errors = np.where(cumsum_true_errors > 0.68)[0][0]

plt.hist(true_errors, bins=20)
plt.axvline(true_errors[correct_quantile_index_true_errors], color="red", label=f"68% quantile: {true_errors[correct_quantile_index_true_errors]:.2f}")
plt.xlabel("True error")
plt.ylabel("Frequency")
plt.title("True error")
plt.legend()
plt.savefig(output_folder + "true_error.png")   
plt.clf()

plt.hist(true_errors*180/np.pi, bins=20)
plt.axvline(true_errors[correct_quantile_index_true_errors]*180/np.pi, color="red", label=f"68% quantile: {true_errors[correct_quantile_index_true_errors]*180/np.pi:.2f}°")
plt.xlabel("True error (degrees)")
plt.ylabel("Frequency")
plt.title("True error (degrees)")
plt.legend()
plt.savefig(output_folder + "true_error_degrees.png")
plt.clf()


cos_true_errors = np.cos(true_errors)
indexes_cos_true_errors = np.argsort(cos_true_errors)   
cos_true_errors = cos_true_errors[indexes_cos_true_errors]
reso_distances = reso_distances[indexes_cos_true_errors]
omega_resolutions = omega_resolutions[indexes_cos_true_errors]
true_dirs = true_dirs[indexes_cos_true_errors]

cumsum_cos_true_errors = np.cumsum(np.ones_like(cos_true_errors))
cumsum_cos_true_errors = cumsum_cos_true_errors / cumsum_cos_true_errors[-1]
correct_quantile_index_cos = np.where(cumsum_cos_true_errors > 0.32)[0][0]


plt.hist(np.cos(true_errors), bins=50, range=(0.975, 1))
plt.axvline(cos_true_errors[correct_quantile_index_cos], color="red", label=f"68% quantile: cos({np.arccos(cos_true_errors[correct_quantile_index_cos])*180/np.pi:.2f}°)")
plt.xticks(np.linspace(0.975, 1, 5))
plt.gca().set_xticklabels([f"cos({np.arccos(x)*180/np.pi:.2f}°)" for x in np.linspace(0.975, 1, 5)])
plt.xlabel("cos(True error)")
plt.ylabel("Frequency")
plt.legend()
plt.title("cos(True error)")
plt.savefig(output_folder + "cos_true_error.png")
plt.clf()

plt.hist(omega_resolutions, bins=20)
plt.xlabel("Omega resolution")
plt.ylabel("Frequency")
plt.title("Omega resolution")
plt.savefig(output_folder + "omega_resolution.png")
plt.clf()

plt.hist(reso_distances, bins=20)
plt.xlabel("Resolution distance")
plt.ylabel("Frequency")
plt.title("Resolution distance")
plt.savefig(output_folder + "reso_distance.png")
plt.clf()

total_cos = np.sum(total_predictions * total_true_dirs, axis=1)/(np.linalg.norm(total_predictions, axis=1)*np.linalg.norm(total_true_dirs, axis=1))

plt.hist(total_cos, bins=40, range=(-1, 1))
plt.xlabel("Cos(angle)")
plt.ylabel("Frequency")
plt.title("Cosine between predicted and true direction")
plt.savefig(output_folder + "cos.png")
plt.clf()


# make a 2D plot with energies and total cos
plt.hist2d(total_cos, total_energies, bins=30)
plt.xlabel("Cos(angle)")
plt.ylabel("Energy [ADC Counts]")
plt.title("Cos(angle) vs Energy")
plt.savefig(output_folder + "cos_vs_energy.png")
plt.clf()

# plot true dirs in a map
true_dirs = np.array(true_dirs)

thetas = np.arctan2(true_dirs[:,2], true_dirs[:,0])
phis = np.arccos(true_dirs[:,1])
nside = 3
npix = healpy.nside2npix(nside)
# create a map with the number of pixels
map_hp = np.zeros(npix)
map_errors = np.zeros(npix)
plt.figure(figsize=(10, 10))
plt.title("Labels map")
thetas = np.mod(thetas, 2*np.pi)
phis = np.mod(phis, np.pi)
# get the indices
indices = healpy.ang2pix(nside, phis, thetas)
# fill the map
for i, index in enumerate(indices):
    map_hp[index] += 1
    map_errors[index] += true_errors[i]*180/np.pi
# normalize the errors
map_errors = np.where(map_hp == 0, 0, map_errors/map_hp)

map_hp = np.where(map_hp == 0, healpy.UNSEEN, map_hp)
map_errors = np.where(map_errors == 0, healpy.UNSEEN, map_errors)

# plot the map
plt.figure(figsize=(10, 10))
healpy.mollview(map_hp, title="True Direction Map", cmap="viridis")
plt.savefig(output_folder + "labels_map.png")
plt.clf()

# plot the errors map
plt.figure(figsize=(10, 10))
plt.title("Errors map")
healpy.mollview(map_errors, title="Error Map", cmap="viridis")
plt.savefig(output_folder + "errors_map.png")
plt.clf()

