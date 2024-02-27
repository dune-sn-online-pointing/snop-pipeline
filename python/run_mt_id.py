import sys
import os
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

def run(mt_id_params, output_folder):
    # Load dataset
    dataset_img = np.load(mt_id_params["dataset_img"])
    # Load model
    model = keras.models.load_model(mt_id_params["model"])
    # Predict
    predictions = model.predict(dataset_img)
    # Save predictions
    np.save(output_folder + "predictions.npy", predictions)

