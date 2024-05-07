import sys
import os
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import matplotlib.pyplot as plt
import matplotlib.pylab as pylab
import seaborn as sns
from mpl_toolkits.axes_grid1 import ImageGrid
from sklearn.metrics import roc_curve, auc, det_curve
from sklearn.metrics import confusion_matrix, accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from sklearn.preprocessing import label_binarize


def run(input_data, dataset_img, output_folder):
    pointing_params = input_data["pointing"]
    # Load model
    model = keras.models.load_model(pointing_params["model"], compile=False)    
    # Predict
    predictions = model.predict(dataset_img)
    # Save predictions
    id_outfolder = output_folder + pointing_params["output_folder"]
    if not os.path.exists(id_outfolder):
        os.makedirs(id_outfolder)
    np.save(id_outfolder + "predictions.npy", predictions)

    # save in txt
    with open(id_outfolder + "predictions.txt", "w") as f:
        for i in range(len(predictions)):
            f.write(str(predictions[i][0]) + "\n")


    return predictions

def average_angles(angles, weights=None):
    if weights is None:
        weights = np.ones(len(angles))

    x, z = np.cos(angles), np.sin(angles)
    avg_x = np.sum(x * weights) / np.sum(weights)
    avg_z = np.sum(z * weights) / np.sum(weights)
    return np.arctan2(avg_z, avg_x), np.sqrt(avg_x**2 + avg_z**2)

