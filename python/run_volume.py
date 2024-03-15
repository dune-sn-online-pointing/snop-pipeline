import os
import numpy as np
import sys

# sys.path.append("/afs/cern.ch/work/d/dapullia/public/dune/online-pointing-utils/python")
sys.path.append("../submodules/online-pointing-utils/python/")
from image_creator import *
from utils import *
from cluster import *
from dataset_creator import *

def run(input_data, output_folder):
    volume_params = input_data["volume"]
    filename = output_folder+volume_params["filename"]
    predictions = output_folder+volume_params["predictions"]
    threshold = input_data["mt_id"]["threshold"]
    radius = volume_params["radius"]
    volume_output_folder = output_folder + input_data["volume"]["output_folder"]
    if not os.path.exists(volume_output_folder):
        os.makedirs(volume_output_folder)
    # execution_command = volume_params["executable"] + " -f " + filename + " -o " + volume_output_folder + " --predictions " + predictions + " --threshold " + str(threshold) + " --radius " + str(radius)
    # ./app/aggregate_clusters_within_volume -f ${FILENAME} -o ${OUTPUT_FOLDER} -r ${RADIUS} -p ${PREDICTIONS} -t ${THRESHOLD}
    execution_command = volume_params["executable"] + " -f " + filename + " -o " + volume_output_folder + " -r " + str(radius) + " -p " + predictions + " -t " + str(threshold)
    print(execution_command)
    os.system(execution_command)
    

