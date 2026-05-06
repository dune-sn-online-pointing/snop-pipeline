#!/usr/bin/env python3
"""
Channel Tagger Module

Runs the Channel Tagging neural network on volume images to classify
ES vs CC interactions.
"""

import numpy as np
from pathlib import Path

# Conditionally import TensorFlow only when needed
try:
    import tensorflow as tf
    _TENSORFLOW_AVAILABLE = True
except ImportError as e:
    _TENSORFLOW_AVAILABLE = False
    _TF_IMPORT_ERROR = str(e)
    
try:
    from sklearn.metrics import confusion_matrix, classification_report, roc_curve, auc
    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False


def tag_channels(images, metadata, model_path, threshold=0.5,
                output_dir=None, verbose=False, vol_refs=None):
    """
    Run Channel Tagging on volume images to classify ES vs CC.

    Args:
        images: Volume images - either array (N, H, W, D, C) or (N, H, W, C),
                or dict with 'X', 'U', 'V' keys (uses X-plane for CT).
                Ignored when vol_refs is provided.
        metadata: Metadata array (N, 13+)
        model_path: Path to trained channel tagging model
        threshold: Classification threshold (default: 0.5)
        output_dir: Optional directory to save predictions
        verbose: Print detailed progress
        vol_refs: Optional list of (vol_file_path_str, match_id) tuples, one per cluster.
                  When provided, volume images are loaded file-by-file (memory-efficient)
                  instead of from the pre-loaded `images` array.

    Returns:
        dict with predictions, metrics, and statistics
    """
    if verbose:
        print(f"\nChannel Tagging:")
        print(f"  Model: {model_path}")
        print(f"  Threshold: {threshold}")

    # Check TensorFlow availability
    if not _TENSORFLOW_AVAILABLE:
        raise RuntimeError(f"TensorFlow is not available for Channel Tagging: {_TF_IMPORT_ERROR}")

    # Load model
    try:
        model = tf.keras.models.load_model(model_path, compile=False)
        if verbose:
            print(f"  ✓ Model loaded successfully")
    except Exception as e:
        raise RuntimeError(f"Failed to load model from {model_path}: {e}")

    n_samples = len(metadata)
    if verbose:
        print(f"  Input volumes: {n_samples}")

    # Extract truth labels from metadata (column 3)
    y_true = metadata[:, 3].astype(int)  # is_es_interaction

    if verbose:
        n_es = np.sum(y_true == 1)
        n_cc = np.sum(y_true == 0)
        print(f"  Truth distribution: {n_es} ES, {n_cc} CC")

    # Run predictions
    if verbose:
        print(f"  Running predictions...")

    if vol_refs is not None:
        # Memory-efficient path: load volume images file-by-file grouped by source file
        y_pred_proba = _predict_from_vol_refs(model, vol_refs, n_samples, verbose)
    else:
        # Pre-loaded images path
        # Handle 3-plane mode: extract X-plane for CT classification
        if isinstance(images, dict) and 'X' in images:
            if verbose:
                print(f"  3-plane mode detected: using X-plane for channel tagging")
            images = images['X']

        images_input = _preprocess_ct_images(np.array(images, dtype=np.float32))
        y_pred_proba = model.predict(images_input, batch_size=32, verbose=0)

    # Normalize to a 1D ES-probability vector.
    # Training label encoding: ES=0, CC=1 → class 0 output = P(ES)
    y_pred_proba = np.asarray(y_pred_proba)
    if y_pred_proba.ndim == 1:
        pass  # already a 1D probability (assume P(ES) if single output)
    elif y_pred_proba.ndim == 2 and y_pred_proba.shape[1] == 1:
        y_pred_proba = 1.0 - y_pred_proba[:, 0]  # single sigmoid: 1=CC → flip
    elif y_pred_proba.ndim == 2 and y_pred_proba.shape[1] >= 2:
        y_pred_proba = y_pred_proba[:, 0]  # 2-class softmax: index 0 = P(ES)
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


def _preprocess_ct_images(images):
    """Prepare CT images for model input: add channel dimension only.
    The ct_volume_v52 model was trained on raw ADC values with no external normalization."""
    images = np.asarray(images, dtype=np.float32)
    if images.ndim == 3:
        images = images[..., np.newaxis]  # (N, H, W, 1)
    return images


def _predict_from_vol_refs(model, vol_refs, n_samples, verbose=False):
    """Load volume images file-by-file and run CT inference, returning probabilities in original order."""
    from collections import defaultdict

    # Group sample indices by source file to load each file only once
    file_to_indices = defaultdict(list)
    for idx, (vol_file, match_id) in enumerate(vol_refs):
        file_to_indices[vol_file].append((idx, match_id))

    y_pred_proba = np.zeros(n_samples, dtype=np.float32)
    files_processed = 0

    for vol_file, entries in file_to_indices.items():
        try:
            vol_data = np.load(vol_file, allow_pickle=True)
            vol_images = vol_data['images']  # shape (N_vols, H, W)
        except Exception as e:
            if verbose:
                print(f"\n  Warning: Could not load {vol_file}: {e}")
            # Leave probabilities at 0 for this file's entries
            files_processed += 1
            continue

        # Build batch: (vol_image, original_index) for each entry in this file
        batch_imgs = []
        batch_indices = []
        for orig_idx, match_id in entries:
            if match_id < len(vol_images):
                batch_imgs.append(vol_images[match_id])
                batch_indices.append(orig_idx)

        if batch_imgs:
            batch_arr = np.array(batch_imgs, dtype=np.float32)
            batch_arr = _preprocess_ct_images(batch_arr)  # log1p + per-image scale
            preds = model.predict(batch_arr, batch_size=32, verbose=0)
            preds = np.asarray(preds)
            # Training label encoding: ES=0, CC=1 → class 0 output = P(ES)
            if preds.ndim == 2 and preds.shape[1] >= 2:
                preds = preds[:, 0]  # P(ES)
            elif preds.ndim == 2 and preds.shape[1] == 1:
                preds = 1.0 - preds[:, 0]  # single sigmoid: 1=CC → flip to get P(ES)
            else:
                preds = preds.ravel()
            for i, orig_idx in enumerate(batch_indices):
                y_pred_proba[orig_idx] = float(preds[i])

        files_processed += 1
        if verbose and files_processed % 20 == 0:
            print(f"  CT inference: {files_processed}/{len(file_to_indices)} files", end='\r')

    if verbose:
        print(f"  CT inference: {files_processed}/{len(file_to_indices)} files done")

    return y_pred_proba


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
