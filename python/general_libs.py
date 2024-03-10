import os
import numpy as np
import sys
import json

sys.path.append("./submodules/online-pointing-utils/python")
from image_creator import *
from utils import *
from cluster import *
from dataset_creator import *

def create_report(input_data, output_folder):
    with open(output_folder + "report.txt", "w") as f:
        f.write("Output folder:\n")
        f.write(output_folder)
        f.write("\n")
        labels = np.load(output_folder+input_data["ctds"]["output_folder"] + 'dataset/dataset_label_process.npy')
        f.write(f"Clusters: {np.unique(labels, return_counts=True)}")
        f.write("\n")
        predictions = np.load(output_folder + input_data["mt_id"]["output_folder"] + "predictions.npy")[:, 0]
        index = np.where(predictions > input_data["mt_id"]["threshold"] )
        pred_main_tracks = predictions[index]
        print(labels.shape, predictions.shape, pred_main_tracks.shape)
        true_info = labels[index]
        f.write(f"Predicted Main Tracks: {len(pred_main_tracks)}")
        f.write("\n")
        f.write(f"True ID of Main Tracks: {np.unique(true_info, return_counts=True)}")
        f.write("\n")
        f.write("\n")       

        f.write("Input data:\n")
        f.write(json.dumps(input_data, indent=4))
        f.write("\n")