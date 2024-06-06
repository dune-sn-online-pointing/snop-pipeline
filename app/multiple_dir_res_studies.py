import numpy as np
import json
import os
import sys
import argparse
import time

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

for i in range(len(unique_true_x)):
    print("Event", i, "of", len(unique_true_x), "events")
    index = np.where(true_x == unique_true_x[i])
    ctds_dataset_img_i = ctds_dataset_img[index]
    true_dir_i = true_dir[index]
    true_x_i = true_dir_i[0,0]
    true_y_i = true_dir_i[0,1]
    true_z_i = true_dir_i[0,2]
       

    predictions = run_pointing.run(input_data, ctds_dataset_img_i, output_folder)
    final_theta, final_phi, final_theta_std, final_phi_std, omega_resolution = run_loglikelihood_reconstruction.run(input_data, predictions, output_folder)

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


plt.hist(true_errors, bins=20)
plt.xlabel("True error")
plt.ylabel("Frequency")
plt.title("True error")
plt.savefig(output_folder + "true_error.png")   
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


weight_for_true_errors = 1/np.sin(true_errors)
indexes = np.argsort(true_errors)
true_errors = true_errors[indexes]
reso_distances = reso_distances[indexes]
weight_for_true_errors = weight_for_true_errors[indexes]
cumsum = np.cumsum(weight_for_true_errors)
cumsum = cumsum / cumsum[-1]
quantiles = np.quantile(cumsum, [0.68])
true_resolution = true_errors[np.where(cumsum > quantiles[0])[0][0]]

plt.hist(true_errors_copy, bins=20, weights=weight_for_true_errors)
plt.axvline(true_resolution, color="red", label=f"68% quantile for true error: {true_resolution:.2f}")
plt.xlabel("True error")
plt.ylabel("Frequency")
plt.title("True error")
plt.savefig(output_folder + "true_error_weighted.png")
plt.clf()

plt.hist(reso_distances, bins=20, weights=weight_for_true_errors)
plt.axvline(1, color="red", label=f"68% quantile for resolution distance: {1:.2f}")
plt.xlabel("Resolution distance")
plt.ylabel("Frequency")
plt.title("Resolution distance")
plt.savefig(output_folder + "reso_distance_weighted.png")
plt.clf()




