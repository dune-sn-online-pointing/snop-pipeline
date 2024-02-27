import numpy as np
import json
import os
import sys
import argparse
import time

# assumes that upper level is home of the project
sys.path.append("../python/")
sys.path.append("../submodules/online-pointing-utils/python/")

import run_clustering # Read data, run clustering, save results
import run_ctds # Read clusters and create dataset
import run_mt_id # Read dataset and identify Main Tracks
import run_volume # Read Main Tracks and calculate volume
import run_int_class # Read Main Tracks and classify interactions

# import cluster # works

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
clustering_params = input_data["clustering"]
run_clustering.run(clustering_params, output_folder)
end = time.time()
print("Clustering done in", end - start, "seconds")

# Run clusters to dataset
print("Running clusters to dataset")
start = time.time()
ctds_params = input_data["ctds"]
run_ctds.run(ctds_params, output_folder)
end = time.time()
print("Clusters to dataset done in", end - start, "seconds")

# Run Main Tracks identification
print("Running Main Tracks identification")
start = time.time()
mt_id_params = input_data["mt_id"]
run_mt_id.run(mt_id_params, output_folder)
end = time.time()
print("Main Tracks identification done in", end - start, "seconds")

# # Run volume group creation
# print("Running volume group creation")
# start = time.time()
# volume_params = input_data["volume"]
# run_volume.run(volume_params, output_folder)
# end = time.time()
# print("Volume group creation done in", end - start, "seconds")





print("Overall done in", time.time() - overall_start, "seconds")


