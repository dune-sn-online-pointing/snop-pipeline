import sys
import os
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

def run(input_data, dataset_img, output_folder):
    int_class_params = input_data["int_class"]
    # Load model
    model = keras.models.load_model(int_class_params["model"])
    # Predict
    print(dataset_img.shape)
    predictions = model.predict(dataset_img)
    # Save predictions
    id_outfolder = output_folder + int_class_params["output_folder"]
    if not os.path.exists(id_outfolder):
        os.makedirs(id_outfolder)
    np.save(id_outfolder + "predictions.npy", predictions)

    # save in txt
    with open(id_outfolder + "predictions.txt", "w") as f:
        for i in range(len(predictions)):
            f.write(str(predictions[i][0]) + "\n")

    return predictions