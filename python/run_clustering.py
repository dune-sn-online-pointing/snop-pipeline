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
    # Run clustering
    # print(clustering_params["executable"] + " " + clustering_params["filename"] + " " + clustering_outfolder + " " + str(clustering_params["tick_limit"]) + " " + str(clustering_params["channel_limit"]) + " " + str(clustering_params["min_tps_to_group"]) + " " + str(clustering_params["plane"]) + " " + str(clustering_params["supernova_option"]) + " " + str(clustering_params["main_track_option"]) + " " + str(clustering_params["max_events"]) + " " + str(clustering_params["adc_integral_cut"]))
    # os.system(clustering_params["executable"] + " " + clustering_params["filename"] + " " + clustering_outfolder + " " + str(clustering_params["tick_limit"]) + " " + str(clustering_params["channel_limit"]) + " " + str(clustering_params["min_tps_to_group"]) + " " + str(clustering_params["plane"]) + " " + str(clustering_params["supernova_option"]) + " " + str(clustering_params["main_track_option"]) + " " + str(clustering_params["max_events"]) + " " + str(clustering_params["adc_integral_cut"]))
    
    # execution_command="./app/cluster_to_root -f $input_file -o $output_folder --ticks-limit $TICK_LIMITS --channel-limit $CHANNEL_LIMIT --min-tps-to-cluster $MIN_TPS_TO_CLUSTER --plane $PLANE --supernova-option $SUPERNOVA_OPTION --main-track-option $MAIN_TRACK_OPTION --max-events-per-filename $MAX_EVENTS_PER_FILENAME --adc-integral-cut $ADC_INTEGRAL_CUT"
    print(clustering_params["executable"] + " -f " + clustering_params["filename"] + " -o " + clustering_outfolder + " --ticks-limit " + str(clustering_params["tick_limit"]) + " --channel-limit " + str(clustering_params["channel_limit"]) + " --min-tps-to-cluster " + str(clustering_params["min_tps_to_group"]) + " --plane " + str(clustering_params["plane"]) + " --supernova-option " + str(clustering_params["supernova_option"]) + " --main-track-option " + str(clustering_params["main_track_option"]) + " --max-events-per-filename " + str(clustering_params["max_events"]) + " --adc-integral-cut " + str(clustering_params["adc_integral_cut"]))
    os.system(clustering_params["executable"] + " -f " + clustering_params["filename"] + " -o " + clustering_outfolder + " --ticks-limit " + str(clustering_params["tick_limit"]) + " --channel-limit " + str(clustering_params["channel_limit"]) + " --min-tps-to-cluster " + str(clustering_params["min_tps_to_group"]) + " --plane " + str(clustering_params["plane"]) + " --supernova-option " + str(clustering_params["supernova_option"]) + " --main-track-option " + str(clustering_params["main_track_option"]) + " --max-events-per-filename " + str(clustering_params["max_events"]) + " --adc-integral-cut " + str(clustering_params["adc_integral_cut"]))
