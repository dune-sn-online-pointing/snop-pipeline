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
    mt_id_params = input_data["mt_id"]
    # Load model
    model = keras.models.load_model(mt_id_params["model"])
    # Predict
    predictions = model.predict(dataset_img)
    # Save predictions
    id_outfolder = output_folder + mt_id_params["output_folder"]
    if not os.path.exists(id_outfolder):
        os.makedirs(id_outfolder)
    np.save(id_outfolder + "predictions.npy", predictions)

    # save in txt
    with open(id_outfolder + "predictions.txt", "w") as f:
        for i in range(len(predictions)):
            f.write(str(predictions[i][0]) + "\n")

    # Calculate metrics
    test_labels = np.load(output_folder + input_data["ctds"]["output_folder"] + "dataset/dataset_label_process.npy")
    # change the labels to 0 when they are different from 100 or 101
    test_labels = np.where(test_labels == 100, 101, test_labels)
    test_labels = np.where(test_labels == 101, 1, 0)

    log_metrics(test_labels, predictions, output_folder=output_folder+mt_id_params["output_folder"], label_names=["bkg+blips", "main tracks"], threshold=mt_id_params["threshold"])

    histogram_of_enegies(test_labels, predictions, dataset_img, threshold=mt_id_params["threshold"], output_folder=output_folder+mt_id_params["output_folder"])

    return predictions

def calculate_metrics(y_true, y_pred,threshold=0.5):
    # calculate the confusion matrix, the accuracy, and the precision and recall 
    # binary trick
    y_pred_am = np.where(y_pred > threshold, 1, 0)
    cm = confusion_matrix(y_true, y_pred_am, normalize='true')
    # compute precision matrix
    

    accuracy = accuracy_score(y_true, y_pred_am)
    precision = precision_score(y_true, y_pred_am, average='macro')
    recall = recall_score(y_true, y_pred_am, average='macro')
    f1 = f1_score(y_true, y_pred_am, average='macro')

    return cm, accuracy, precision, recall, f1
    
def log_metrics(y_true, y_pred, output_folder="", label_names=["CC", "ES"], threshold=0.5):
    cm, accuracy, precision, recall, f1 = calculate_metrics(y_true, y_pred, threshold=threshold)

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    with open(output_folder+f"metrics.txt", "w") as f:
        f.write("Confusion Matrix\n")
        f.write(str(cm)+"\n")
        f.write("Accuracy: "+str(accuracy)+"\n")
        f.write("Precision: "+str(precision)+"\n")
        f.write("Recall: "+str(recall)+"\n")
        f.write("F1: "+str(f1)+"\n")
    # save confusion matrix 
    plt.figure(figsize=(10,10))
    plt.title("Confusion matrix", fontsize=28)
    sns.heatmap(cm, annot=True, cmap="YlGnBu", xticklabels=label_names, yticklabels=label_names, annot_kws={"fontsize": 20})
    plt.ylabel('True label', fontsize=28)
    plt.xticks(fontsize=20)
    plt.yticks(fontsize=20)
    plt.xlabel('Predicted label', fontsize=28)
    plt.savefig(output_folder+f"confusion_matrix.png")
    plt.clf()
    # Binarize the output
    y_test = label_binarize(y_true, classes=np.arange(len(label_names)))
    n_classes = y_test.shape[1]
    
    plt.figure(figsize=(10,10))

    fpr, tpr, _ = roc_curve(y_true[:], y_pred[:])
    roc_auc = auc(fpr, tpr)

    # Write to file the AUC, fpr, tpr
    with open(output_folder+"roc_auc.txt", "w") as f:
        f.write("AUC: "+str(roc_auc)+"\n")
        for i in range(len(fpr)):
            f.write(str(fpr[i])+" "+str(tpr[i])+"\n")

    fpr_dc, fnr_dc, thresholds_dc = det_curve(y_true[:], y_pred[:])
    with open(output_folder+"det_curve.txt", "w") as f:
        for i in range(len(fpr_dc)):
            f.write(str(fpr_dc[i])+" "+str(fnr_dc[i])+" "+str(thresholds_dc[i])+"\n")

    plt.plot(fpr, tpr, lw=2, label='ROC curve (area = {0:0.2f})'.format(roc_auc))

    plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
    plt.xlabel('False Positive Rate', fontsize=28)
    plt.ylabel('True Positive Rate', fontsize=28)
    plt.title('ROC curve', fontsize=28)
    plt.legend(loc="lower right", fontsize=20)
    plt.savefig(output_folder+"roc_curve.png")
    plt.clf()

    plt.plot(fpr_dc, fnr_dc, lw=2, label='DET curve')
    plt.xlabel('False Positive Rate', fontsize=28)
    plt.ylabel('False Negative Rate', fontsize=28)
    plt.title('DET curve', fontsize=28)
    plt.legend(loc="upper right", fontsize=20)
    plt.savefig(output_folder+"det_curve.png")
    plt.clf()

    # create an histogram of the predictions

    y_true = np.reshape(y_true, (y_true.shape[0],))
    bkg_preds = y_pred[y_true < threshold]
    sig_preds = y_pred[y_true > threshold]

    plt.hist(bkg_preds, bins=50, alpha=0.5, label=f'{label_names[0]} (n={bkg_preds.shape[0]})')
    plt.hist(sig_preds, bins=50, alpha=0.5, label=f'{label_names[1]} (n={sig_preds.shape[0]})')
    plt.legend(loc='upper right')
    plt.xlabel('Prediction')
    plt.ylabel('Counts')
    plt.title('Predictions')
    plt.savefig(output_folder+f"predictions.png")
    plt.clf()

def histogram_of_enegies(test_labels, predictions, images, threshold=0.5, output_folder=""):
    # check if some images are corrupted
    corrupted_images = []
    for i in range(images.shape[0]):
        if (np.sum(images[i])==0):
            corrupted_images.append(i)
    print("Corrupted images: ", len(corrupted_images))


    true_positives = []
    true_negatives = []
    false_positives = []
    false_negatives = []
    all_images = []
    for i in range(len(test_labels)):
        if test_labels[i] == 1 and predictions[i] > threshold:
            true_positives.append(np.sum(images[i]))
        elif test_labels[i] == 0 and predictions[i] < threshold:
            true_negatives.append(np.sum(images[i]))
        elif test_labels[i] == 0 and predictions[i] > threshold:
            false_positives.append(np.sum(images[i]))
        elif test_labels[i] == 1 and predictions[i] < threshold:
            false_negatives.append(np.sum(images[i]))
        all_images.append(np.sum(images[i]))
    
    print("True Positives: ", len(true_positives))
    print("True Negatives: ", len(true_negatives))
    print("False Positives: ", len(false_positives))
    print("False Negatives: ", len(false_negatives))
    print("All images: ", len(all_images))
    
    with open(output_folder + "prediction_results.txt", 'w') as file:
        file.write(f'TP, TN, FP, FN\n')
        file.write(f'{len(true_positives)}\n')
        file.write(f'{len(true_negatives)}\n')
        file.write(f'{len(false_positives)}\n')
        file.write(f'{len(false_negatives)}\n')
        file.write(f'{len(all_images)}\n')

    print(f"Results saved to {output_folder} + prediction_results.txt")

    # sum the pixel values
    plt.figure()
    plt.hist(true_positives, range=(0, 3e6), bins=50, alpha=0.5, label='True Positives (n='+str(len(true_positives))+')')
    plt.hist(true_negatives, range=(0, 3e6), bins=50, alpha=0.5, label='True Negatives (n='+str(len(true_negatives))+')')
    plt.hist(false_positives, range=(0, 3e6), bins=50, alpha=0.5, label='False Positives (n='+str(len(false_positives))+')')
    plt.hist(false_negatives, range=(0, 3e6), bins=50, alpha=0.5, label='False Negatives (n='+str(len(false_negatives))+')')

    plt.legend(loc='upper right')
    plt.xlabel('Pixel value')
    plt.ylabel('Counts')
    plt.title('Pixel value histogram')
    plt.savefig(output_folder+"pixel_value_histogram.png")
    plt.clf()
