import os
import numpy as np
import sys

# sys.path.append("/afs/cern.ch/work/d/dapullia/public/dune/online-pointing-utils/python")
sys.path.append("/afs/cern.ch/work/h/hakins/private/online-pointing-utils/python/")
from image_creator import *
from utils import *
from cluster import *
from dataset_creator import *


def run(input_data, output_folder):
    ctds_parameters = input_data["ctds"]

    filename = output_folder+ctds_parameters["filename"]
    ctds_outfolder = output_folder+ctds_parameters["output_folder"]
    width = ctds_parameters["img_witdh"]
    height = ctds_parameters["img_height"]
    x_margin = ctds_parameters["x_margin"]
    y_margin = ctds_parameters["y_margin"]
    which_detector = ctds_parameters["which_detector"]
    min_tps_to_cluster = ctds_parameters["min_tps_to_cluster"]
    save_img_dataset = ctds_parameters["save_img_dataset"]
    save_process_label = ctds_parameters["save_process_label"]
    save_true_dir_label = ctds_parameters["save_true_dir_label"]
    only_collection = ctds_parameters['only_collection']
    dt = np.dtype([('time_start', float), 
                    ('time_over_threshold', float),
                    ('time_peak', float),
                    ('channel', int),
                    ('adc_integral', int),
                    ('adc_peak', int),
                    ('detid', int),
                    ('type', int),
                    ('algorithm', int),
                    ('version', int),
                    ('flag', int)])
    # Read the root file
    clusters, event_number = read_root_file_to_clusters(filename)

    print(f"Number of clusters: {len(clusters)}")
    # Create the channel map
    channel_map = create_channel_map_array(which_detector=which_detector)
    # Prepare the output path   
    if not os.path.exists(ctds_outfolder + 'dataset'):
        os.makedirs(ctds_outfolder + 'dataset')

    # Create the images
    dataset_img = None

    if save_img_dataset:
        print("Creating the images")
        dataset_img = create_dataset_img(clusters=clusters, channel_map=channel_map, min_tps_to_create_img=min_tps_to_cluster, make_fixed_size=True, width=width, height=height, x_margin=x_margin, y_margin=y_margin, only_collection=only_collection)
        print(f"Shape of the dataset_img: {dataset_img.shape}")
        np.save(ctds_outfolder + 'dataset/dataset_img.npy', dataset_img)
        save_samples_from_ds(dataset_img, ctds_outfolder + 'samples/', n_samples=10)
    # Create the labels
    if save_process_label:
        print("Creating the process labels")
        dataset_label_process = create_dataset_label_process(clusters)
        print(f"Shape of the dataset_label_process: {dataset_label_process.shape}")
        print(f"Unique labels: {np.unique(dataset_label_process, return_counts=True)}")
        np.save(ctds_outfolder + 'dataset/dataset_label_process.npy', dataset_label_process)
    if save_true_dir_label:
        print("Creating the true direction labels")
        dataset_label_true_dir = create_dataset_label_true_dir(clusters)
        print(f"Shape of the dataset_label_true_dir: {dataset_label_true_dir.shape}")
        np.save(ctds_outfolder + 'dataset/dataset_label_true_dir.npy', dataset_label_true_dir)

    return dataset_img

