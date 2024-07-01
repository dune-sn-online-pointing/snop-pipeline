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

# ctds_dataset_img = ctds_dataset_img[:int(ctds_dataset_img.shape[0]*0.5),:,:,:]


if delete_view=="U":
    ctds_dataset_img[:,:,:,0] = np.zeros(ctds_dataset_img[:,:,:,0].shape)
elif delete_view=="V":
    ctds_dataset_img[:,:,:,1] = np.zeros(ctds_dataset_img[:,:,:,0].shape)
elif delete_view=="X":
    ctds_dataset_img[:,:,:,2] = np.zeros(ctds_dataset_img[:,:,:,0].shape)


# Run pointing
print("Running pointing")
start = time.time()
predictions = run_pointing.run(input_data, ctds_dataset_img, output_folder)

if input_data["loglikelihood"]["energy_weight"]:
    # E is the sum of the pixel values in the X plane image
    E = np.sum(ctds_dataset_img[:,:,:,2], axis=(1,2))
    # E = np.sqrt(E)
    # E = E / np.max(E)
else:
    E = None


end = time.time()
print("Pointing done in", end - start, "seconds")

true_dir_exists = os.path.exists(output_folder + input_data["ctds"]["output_folder"] + "/dataset/dataset_label_true_dir.npy")
final_theta, final_phi, final_theta_std, final_phi_std, omega_resolution = None, None, None, None, None
if true_dir_exists:
    true_dir = np.load(output_folder + input_data["ctds"]["output_folder"] + "/dataset/dataset_label_true_dir.npy")
    true_x = true_dir[:, 0]
    if len(np.unique(true_x)) > 1:
        print("More than one true direction, loglikelihood reconstruction not possible")
    else:
        print("Running Loglikelihood reconstruction")
        start = time.time()
        final_theta, final_phi, final_theta_std, final_phi_std, omega_resolution = run_loglikelihood_reconstruction.run(input_data, predictions, E, output_folder)
        end = time.time()
        print("Loglikelihood reconstruction done in", end - start, "seconds")
else:
    print("Running Loglikelihood reconstruction")
    start = time.time()
    final_theta, final_phi, final_theta_std, final_phi_std, omega_resolution = run_loglikelihood_reconstruction.run(input_data, predictions, E, output_folder)
    end = time.time()
    print("Loglikelihood reconstruction done in", end - start, "seconds")

# Run pointing tests
print("Running pointing tests")
start = time.time()
run_pointing_tests.run(input_data, predictions, output_folder, final_theta=final_theta, final_phi=final_phi, final_theta_std=final_theta_std, final_phi_std=final_phi_std)
end = time.time()
print("Pointing done in", end - start, "seconds")

print("Pipeline done in", time.time() - overall_start, "seconds")

