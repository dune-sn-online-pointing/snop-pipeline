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
import general_libs # Create report
sys.path.append("../submodules/online-pointing-utils/python/")
from image_creator import *
from utils import *
from cluster import *
from dataset_creator import *

parser = argparse.ArgumentParser(description='Run the pipeline')
parser.add_argument('--input_json', type=str, help='Input json file')
parser.add_argument('--output_folder', type=str, help='Output folder')
args = parser.parse_args()

input_json = args.input_json
output_folder = args.output_folder

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


# Run clusters to dataset
print("Running clusters to dataset")
ctds_dataset_img = None
start = time.time()
ctds_dataset_img = run_ctds.run(input_data, output_folder)
end = time.time()
print("Clusters to dataset done in", end - start, "seconds")

if ctds_dataset_img is None:
    print("No dataset_img created, exiting...")
    sys.exit(0)

# Run pointing
print("Running pointing")
start = time.time()
predictions = run_pointing.run(input_data, ctds_dataset_img, output_folder)
end = time.time()
print("Pointing done in", end - start, "seconds")

# name_to_read = np.loadtxt(input_data["clustering"]["filename"], dtype=str)[0]
# # separate the name of the file to read the data
# name_to_read = name_to_read.split("/")

bins_weights = np.load('/afs/cern.ch/work/d/dapullia/public/dune/plot_making/test_pointing/bins_weights.npy')
bins_true = np.load('/afs/cern.ch/work/d/dapullia/public/dune/plot_making/test_pointing/bins_true.npy')
def apply_weights(pred_angle, bins_weights, bins_true):
    # create the weights
    weights = np.ones(len(pred_angle))
    for i in range(len(bins_true)-1):
        idx = np.where((pred_angle >= bins_true[i]) & (pred_angle < bins_true[i+1]))[0]
        weights[idx] = bins_weights[i]
    return weights






# true_x =  -0.5720104283109433
# true_z =  -0.7636383678836225
true_x = 0
true_z = 1



x, z = predictions[:, 0], predictions[:, -1]

# calculate the angle
angle = np.arctan2(z, x)
angle_weights = apply_weights(angle, bins_weights, bins_true)

true_angle = np.arctan2(true_z, true_x)
avg_angle, module= run_pointing.average_angles(angle)
weighted_avg_angle, weighted_module = run_pointing.average_angles(angle, angle_weights)


plt.figure()
plt.hist(angle, bins=50, alpha=0.5, label="Predicted")
plt.hist(angle, bins=50, alpha=0.5, weights=angle_weights, label="Weighted")
plt.axvline(x=true_angle, color="r", label="True angle")
plt.axvline(x=avg_angle, color="g", label="Average angle, module = " + str(module))
plt.axvline(x=weighted_avg_angle, color="b", label="Weighted average angle, module = " + str(weighted_module))

plt.xlabel("Angle")
plt.ylabel("Frequency")
plt.title("Angle distribution")
plt.legend()
plt.savefig(output_folder + input_data["pointing"]["output_folder"] + "angle_distribution.png")

# cosine 
true_x = np.ones(len(predictions)) * true_x
true_z = np.ones(len(predictions)) * true_z

print("True x", true_x.shape)
print("True z", true_z.shape)
print("x", x.shape)
print("z", z.shape)

cosine = (true_x * x + true_z * z) / (np.sqrt(true_x**2 + true_z**2) * np.sqrt(x**2 + z**2))

plt.figure()
plt.hist(cosine, bins=50, alpha=0.5, label="Cosine")
plt.hist(cosine, bins=50, alpha=0.5, weights=angle_weights, label="Weighted")
plt.xlabel("Cosine")
plt.ylabel("Frequency")
plt.title("Cosine distribution")
plt.legend()
plt.savefig(output_folder + input_data["pointing"]["output_folder"] + "cosine_distribution.png")
plt.clf()


