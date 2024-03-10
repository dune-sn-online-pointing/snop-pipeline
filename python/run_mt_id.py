import sys
import os
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

def run(mt_id_params, dataset_img, output_folder):
    # Load model
    model = keras.models.load_model(mt_id_params["model"])
    # Predict
    predictions = model.predict(dataset_img)
    # Save predictions
    id_outfolder = output_folder + mt_id_params["output_folder"]
    if not os.path.exists(id_outfolder):
        os.makedirs(id_outfolder)
    np.save(id_outfolder + "predictions.npy", predictions)

    return predictions