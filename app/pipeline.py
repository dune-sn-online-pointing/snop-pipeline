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

# # Check if clustering was successful
# filename = output_folder + input_data["ctds"]["filename"]
# clusters, event_number = read_root_file_to_clusters(filename)
# labels = np.array([c.get_true_label() for c in clusters])
# print("Unique labels:", np.unique(labels, return_counts=True))
# exit(0)
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

# Run Main Tracks identification
print("Running Main Tracks identification")
start = time.time()
predictions = run_mt_id.run(input_data, 
                dataset_img=ctds_dataset_img,
                output_folder=output_folder)
end = time.time()
print("Main Tracks identification done in", end - start, "seconds")


# # Run volume group creation
# print("Running volume group creation")
# start = time.time()
# run_volume.run(input_data, output_folder)
# end = time.time()
# print("Volume group creation done in", end - start, "seconds")

# # Run volume cluster to dataset
# print("Running volume cluster to dataset")
# start = time.time()
# vtds_dataset_img = run_volume.run_vtds(input_data, output_folder)
# end = time.time()

# Run interaction classification
print("Running interaction classification")
start = time.time()
index = np.where(predictions > input_data["mt_id"]["threshold"] )[0]
print(ctds_dataset_img.shape)
# filter only images with index. dataset shape (493, 250, 40, 1)
mt_id_dataset_img = ctds_dataset_img[index]

print("mt_id_dataset_img shape:", mt_id_dataset_img.shape)
predictions_class = run_int_class.run(input_data, 
                                    dataset_img=mt_id_dataset_img,
                                    output_folder=output_folder)
end = time.time()
print("Interaction classification done in", end - start, "seconds")




# Create report
print("Creating report")
start = time.time()
general_libs.create_report(input_data, output_folder)
end = time.time()
print("Report done in", end - start, "seconds")


print("Overall done in", time.time() - overall_start, "seconds")


