import os
import numpy as np
import json

def run(clustering_params, output_folder):
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
    # Run clustering
    # os.system(clustering_params["executable"] + " " + clustering_params["filename"] + " " + clustering_outfolder + " " + str(clustering_params["tick_limit"]) + " " + str(clustering_params["channel_limit"]) + " " + str(clustering_params["min_tps_to_group"]) + " " + str(clustering_params["plane"]) + " " + str(clustering_params["supernova_option"]) + " " + str(clustering_params["main_track_option"]) + " " + str(clustering_params["max_events"]) + " " + str(clustering_params["adc_integral_cut"]))
    print(clustering_params["executable"] + " " + clustering_params["filename"] + " " + clustering_outfolder + " " + str(clustering_params["tick_limit"]) + " " + str(clustering_params["channel_limit"]) + " " + str(clustering_params["min_tps_to_group"]) + " " + str(clustering_params["plane"]) + " " + str(clustering_params["supernova_option"]) + " " + str(clustering_params["main_track_option"]) + " " + str(clustering_params["max_events"]) + " " + str(clustering_params["adc_integral_cut"]))
    os.system(clustering_params["executable"] + " " + clustering_params["filename"] + " " + clustering_outfolder + " " + str(clustering_params["tick_limit"]) + " " + str(clustering_params["channel_limit"]) + " " + str(clustering_params["min_tps_to_group"]) + " " + str(clustering_params["plane"]) + " " + str(clustering_params["supernova_option"]) + " " + str(clustering_params["main_track_option"]) + " " + str(clustering_params["max_events"]) + " " + str(clustering_params["adc_integral_cut"]))
    
