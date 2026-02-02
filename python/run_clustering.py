import os
import numpy as np
import json

def run(input_data, output_folder):
    clustering_params = input_data["clustering"]

    # Check if executable exists
    if not os.path.exists(clustering_params["executable"]):
        raise Exception("Executable not found")
    # Check if input file exists
    if not os.path.exists(clustering_params["filename"]):
        raise Exception("Input file not found")
    # Create output folder
    clustering_outfolder = output_folder+clustering_params["output_folder"]
    if not os.path.exists(clustering_outfolder):
        os.makedirs(clustering_outfolder)
    clustering_params["output_folder"] = clustering_outfolder
    # create a json file with the clustering parameters
    with open(clustering_outfolder + "clustering_params.json", "w") as f:
        json.dump(clustering_params, f)

    execution_command = clustering_params["executable"] + " -j " + clustering_outfolder + "clustering_params.json"
    print(execution_command)
    os.system(execution_command)
