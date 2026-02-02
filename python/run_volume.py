import os
import numpy as np
import sys
import json

# sys.path.append("/afs/cern.ch/work/d/dapullia/public/dune/online-pointing-utils/python")
sys.path.append("../submodules/online-pointing-utils/python/")
from image_creator import *
from utils import *
from cluster import *
from dataset_creator import *

def run(input_data, output_folder):
    volume_params = input_data["volume"]
    volume_output_folder = output_folder + input_data["volume"]["output_folder"]
    if not os.path.exists(volume_output_folder):
        os.makedirs(volume_output_folder)
    volume_params["output_folder"] = volume_output_folder
    volume_params["cluster_filename"] = output_folder + volume_params["cluster_filename"]
    volume_params["predictions"] = output_folder + volume_params["predictions"]
    # create a json file with the volume parameters
    with open(volume_output_folder + "volume_params.json", "w") as f:
        json.dump(volume_params, f)
    execution_command = volume_params["executable"] + " -j " + volume_output_folder + "volume_params.json"
    print(execution_command)
    os.system(execution_command)
    

