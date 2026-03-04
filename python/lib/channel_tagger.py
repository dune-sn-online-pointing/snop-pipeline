#!/usr/bin/env python3
"""
Channel Tagger Module

Runs the Channel Tagging neural network on volume images to classify
ES vs CC interactions.
"""

import numpy as np
from pathlib import Path
import tensorflow as tf
from sklearn.metrics import confusion_matrix, classification_report, roc_curve, auc


def tag_channels(images, metadata, model_path, threshold=0.5,
                output_dir=None, verbose=False):
    """
    Run Channel Tagging on volume images to classify ES vs CC.
    
    Args:
        images: Volume images array (N, H, W, D, C) or (N, H, W, C)
        metadata: Metadata array (N, 13)
        model_path: Path to trained channel tagging model
        threshold: Classification threshold (default: 0.5)
        output_dir: Optional directory to save predictions
        verbose: Print detailed progress
        
    Returns:
        dict with predictions, metrics, and statistics
    """
    
    if verbose:
        print(f"\nChannel Tagging:")
        print(f"  Input volumes: {len(images)}")
        print(f"  Model: {model_path}")
        print(f"  Threshold: {threshold}")
    
    # Load model
    try:
        model = tf.keras.models.load_model(model_path, compile=False)
        if verbose:
            print(f"  ✓ Model loaded successfully")
    except Exception as e:
        raise RuntimeError(f"Failed to load model from {model_path}: {e}")
    
    # Extract truth labels from metadata (column 3)
    y_true = metadata[:, 3].astype(int)  # is_es_interaction
    
    if verbose:
        n_es = np.sum(y_true == 1)
        n_cc = np.sum(y_true == 0)
        print(f"  Truth distribution: {n_es} ES, {n_cc} CC")
    
    # Run predictions
    if verbose:
        print(f"  Running predictions...")
    
    y_pred_proba = model.predict(images, batch_size=32, verbose=0)

    # Normalize to a 1D ES-probability vector
    y_pred_proba = np.asarray(y_pred_proba)
    if y_pred_proba.ndim == 1:
        pass
    elif y_pred_proba.ndim == 2 and y_pred_proba.shape[1] == 1:
        y_pred_proba = y_pred_proba[:, 0]
    elif y_pred_proba.ndim == 2 and y_pred_proba.shape[1] >= 2:
        y_pred_proba = y_pred_proba[:, 1]
    else:
        y_pred_proba = y_pred_proba.reshape(y_pred_proba.shape[0], -1)[:, 0]
    
    y_pred = (y_pred_proba >= threshold).astype(int)
    
    # Calculate metrics
    metrics = _calculate_metrics(y_true, y_pred, y_pred_proba, verbose)
    
    if verbose:
        print(f"\n  Results:")
        print(f"    Predicted as ES: {np.sum(y_pred == 1)}")
        print(f"    Predicted as CC: {np.sum(y_pred == 0)}")
        print(f"    Accuracy: {metrics['accuracy']:.4f}")
        print(f"    Precision (ES): {metrics['precision']:.4f}")
        print(f"    Recall (ES): {metrics['recall']:.4f}")
        print(f"    F1-Score: {metrics['f1_score']:.4f}")
        print(f"    AUC: {metrics['auc']:.4f}")
    
    # Save results if output directory specified
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save predictions
        np.savez(
            output_path / 'channel_predictions.npz',
            y_true=y_true,
            y_pred=y_pred,
            y_pred_proba=y_pred_proba
        )
        
        # Save metrics
        _save_metrics_report(metrics, output_path / 'channel_metrics.txt', verbose)
        
        if verbose:
            print(f"\n  ✓ Saved predictions to {output_path}")
    
    return {
        'y_true': y_true,
        'y_pred': y_pred,
        'y_pred_proba': y_pred_proba,
        'n_predicted_es': int(np.sum(y_pred == 1)),
        'n_predicted_cc': int(np.sum(y_pred == 0)),
        'metrics': metrics
    }


def _calculate_metrics(y_true, y_pred, y_pred_proba, verbose=False):
    """Calculate comprehensive classification metrics."""
    
    # Confusion matrix
    # For channel tagging: 0=CC (negative), 1=ES (positive)
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel()
    
    # Basic metrics
    accuracy = (tp + tn) / (tp + tn + fp + fn)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    # ROC curve and AUC
    fpr, tpr, thresholds = roc_curve(y_true, y_pred_proba)
    roc_auc = auc(fpr, tpr)
    
    return {
        'confusion_matrix': cm,
        'true_positives': int(tp),  # Correctly identified ES
        'true_negatives': int(tn),  # Correctly identified CC
        'false_positives': int(fp),  # CC misclassified as ES
        'false_negatives': int(fn),  # ES misclassified as CC
        'accuracy': float(accuracy),
        'precision': float(precision),
        'recall': float(recall),
        'specificity': float(specificity),
        'f1_score': float(f1_score),
        'auc': float(roc_auc),
        'fpr': fpr,
        'tpr': tpr,
        'roc_thresholds': thresholds
    }


def _save_metrics_report(metrics, output_path, verbose=False):
    """Save detailed metrics report to text file."""
    
    with open(output_path, 'w') as f:
        f.write("Channel Tagging Metrics\n")
        f.write("=" * 60 + "\n\n")
        
        f.write("Confusion Matrix (ES=1, CC=0):\n")
        f.write(f"  True Negatives (CC→CC):  {metrics['true_negatives']}\n")
        f.write(f"  False Positives (CC→ES): {metrics['false_positives']}\n")
        f.write(f"  False Negatives (ES→CC): {metrics['false_negatives']}\n")
        f.write(f"  True Positives (ES→ES):  {metrics['true_positives']}\n\n")
        
        f.write("Performance Metrics:\n")
        f.write(f"  Accuracy:    {metrics['accuracy']:.4f}\n")
        f.write(f"  Precision:   {metrics['precision']:.4f} (ES identification)\n")
        f.write(f"  Recall:      {metrics['recall']:.4f} (ES identification)\n")
        f.write(f"  Specificity: {metrics['specificity']:.4f} (CC identification)\n")
        f.write(f"  F1-Score:    {metrics['f1_score']:.4f}\n")
        f.write(f"  AUC:         {metrics['auc']:.4f}\n")
    
    if verbose:
        print(f"  ✓ Saved metrics report to {output_path}")


def analyze_channel_distribution(y_true, y_pred, verbose=False):
    """
    Analyze the distribution of channel predictions vs ground truth.
    
    Args:
        y_true: Ground truth labels (0=CC, 1=ES)
        y_pred: Predicted labels (0=CC, 1=ES)
        verbose: Print analysis
        
    Returns:
        dict with distribution statistics
    """
    
    # Count correct and incorrect predictions for each class
    cc_correct = np.sum((y_true == 0) & (y_pred == 0))
    cc_incorrect = np.sum((y_true == 0) & (y_pred == 1))
    es_correct = np.sum((y_true == 1) & (y_pred == 1))
    es_incorrect = np.sum((y_true == 1) & (y_pred == 0))
    
    total = len(y_true)
    
    if verbose:
        print(f"\nChannel Distribution Analysis:")
        print(f"  Total samples: {total}")
        print(f"\n  CC (ground truth): {np.sum(y_true == 0)}")
        print(f"    Correctly identified: {cc_correct}")
        print(f"    Misclassified as ES: {cc_incorrect}")
        print(f"\n  ES (ground truth): {np.sum(y_true == 1)}")
        print(f"    Correctly identified: {es_correct}")
        print(f"    Misclassified as CC: {es_incorrect}")
    
    return {
        'total': int(total),
        'cc_total': int(np.sum(y_true == 0)),
        'cc_correct': int(cc_correct),
        'cc_incorrect': int(cc_incorrect),
        'es_total': int(np.sum(y_true == 1)),
        'es_correct': int(es_correct),
        'es_incorrect': int(es_incorrect),
        'overall_accuracy': float((cc_correct + es_correct) / total)
    }
