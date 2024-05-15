import os
import numpy as np
import json

def run(input_data, output_folder):
    match_clusters_params = input_data["match_clusters"]

    # Check if executable exists
    if not os.path.exists(match_clusters_params["executable"]):
        raise Exception("Executable not found")
    # Create output folder
    match_clusters_outfolder = output_folder+match_clusters_params["output_folder"]
    if not os.path.exists(match_clusters_outfolder):
        os.makedirs(match_clusters_outfolder)
    
    match_clusters_params["clusters_u"] = output_folder + match_clusters_params["clusters_u"]
    match_clusters_params["clusters_v"] = output_folder + match_clusters_params["clusters_v"]
    match_clusters_params["clusters_x"] = output_folder + match_clusters_params["clusters_x"] 

    match_clusters_params["output_folder"] = match_clusters_outfolder
    # create a json file with the match_clusters parameters
    with open(match_clusters_outfolder + "match_clusters_params.json", "w") as f:
        json.dump(match_clusters_params, f)

    execution_command = match_clusters_params["executable"] + " -j " + match_clusters_outfolder + "match_clusters_params.json"
    print(execution_command)
    os.system(execution_command)
