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
import run_vtds # Read volume clusters and create image dataset
import run_int_class # Read Main Tracks and classify interactions
import run_pointing # Read dataset and predict pointing
import run_match_clusters # Read clusters and match them
import run_pointing_tests # Read dataset and predictions and run tests
import run_loglikelihood_reconstruction # Read dataset and predictions and run tests
import general_libs # Create report
sys.path.append("/afs/cern.ch/work/h/hakins/private/online-pointing-utils/python/")
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

'''
1. clustering
2. ctds
3. mt_id
4. volume
5. vtds
6. int_class
7. matching
8. 3vctds
9. pointing
10. loglikelihood
11. pointing_tests
12. report
'''

# Run clustering
print("Running clustering")
start = time.time()
run_clustering.run(input_data, output_folder)
end = time.time()
print("Clustering done in", end - start, "seconds")

# Run match clusters
print("Running match clusters")
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
true_dir_exists = os.path.exists(output_folder + input_data["ctds"]["output_folder"] + "/dataset/dataset_label_true_dir.npy")
if true_dir_exists:
    true_dir = np.load(output_folder + input_data["ctds"]["output_folder"] + "/dataset/dataset_label_true_dir.npy")
else:
    true_dir = None
    
if ctds_dataset_img is None:
    print("No dataset_img created, exiting...")
    sys.exit(0)

# Run Main Tracks identification
print("Running Main Tracks identification")
start = time.time()
predictions = run_mt_id.run(input_data, 
                dataset_img=ctds_dataset_img[:, :, :, 2],
                output_folder=output_folder)
end = time.time()

index = np.where(predictions > input_data["mt_id"]["threshold"])[0]
ctds_dataset_img = ctds_dataset_img[index]
if true_dir_exists:
    true_dir = true_dir[index]

print("Main Tracks identification done in", end - start, "seconds")