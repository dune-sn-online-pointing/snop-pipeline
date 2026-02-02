#!/usr/bin/env python3
"""
Main Track Identifier Module

Runs the Main Track identification neural network on X-plane clusters
and calculates performance metrics.
"""

import numpy as np
from pathlib import Path
import tensorflow as tf
from sklearn.metrics import confusion_matrix, classification_report, roc_curve, auc


def identify_main_tracks(images, metadata, model_path, threshold=0.5,
                        output_dir=None, verbose=False):
    """
    Run Main Track identification on X-plane cluster images.
    
    Args:
        images: Cluster images array (N, H, W, C)
        metadata: Metadata array (N, 13)
        model_path: Path to trained MT identification model
        threshold: Classification threshold (default: 0.5)
        output_dir: Optional directory to save predictions
        verbose: Print detailed progress
        
    Returns:
        dict with predictions, metrics, and statistics
    """
    
    if verbose:
        print(f"\nMain Track Identification:")
        print(f"  Input clusters: {len(images)}")
        print(f"  Model: {model_path}")
        print(f"  Threshold: {threshold}")
    
    # Load model
    try:
        model = tf.keras.models.load_model(model_path, compile=False)
        if verbose:
            print(f"  ✓ Model loaded successfully")
    except Exception as e:
        raise RuntimeError(f"Failed to load model from {model_path}: {e}")
    
    # Extract truth labels from metadata (column 2)
    y_true = metadata[:, 2].astype(int)  # is_main_track
    
    if verbose:
        n_mt = np.sum(y_true == 1)
        n_not_mt = np.sum(y_true == 0)
        print(f"  Truth distribution: {n_mt} MT, {n_not_mt} non-MT")
    
    # Run predictions
    if verbose:
        print(f"  Running predictions...")
    
    y_pred_proba = model.predict(images, batch_size=32, verbose=0)
    
    # Handle both (N,) and (N,1) output shapes
    if len(y_pred_proba.shape) > 1:
        y_pred_proba = y_pred_proba.squeeze()
    
    y_pred = (y_pred_proba >= threshold).astype(int)
    
    # Calculate metrics
    metrics = _calculate_metrics(y_true, y_pred, y_pred_proba, verbose)
    
    # Identify which clusters are predicted as main tracks
    mt_indices = np.where(y_pred == 1)[0]
    
    if verbose:
        print(f"\n  Results:")
        print(f"    Predicted as MT: {len(mt_indices)}")
        print(f"    Accuracy: {metrics['accuracy']:.4f}")
        print(f"    Precision: {metrics['precision']:.4f}")
        print(f"    Recall: {metrics['recall']:.4f}")
        print(f"    F1-Score: {metrics['f1_score']:.4f}")
        print(f"    AUC: {metrics['auc']:.4f}")
    
    # Save results if output directory specified
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save predictions
        np.savez(
            output_path / 'mt_predictions.npz',
            y_true=y_true,
            y_pred=y_pred,
            y_pred_proba=y_pred_proba,
            mt_indices=mt_indices
        )
        
        # Save metrics
        _save_metrics_report(metrics, output_path / 'mt_metrics.txt', verbose)
        
        if verbose:
            print(f"\n  ✓ Saved predictions to {output_path}")
    
    return {
        'y_true': y_true,
        'y_pred': y_pred,
        'y_pred_proba': y_pred_proba,
        'mt_indices': mt_indices,
        'n_predicted_mt': len(mt_indices),
        'metrics': metrics
    }


def _calculate_metrics(y_true, y_pred, y_pred_proba, verbose=False):
    """Calculate comprehensive classification metrics."""
    
    # Confusion matrix
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
        'true_positives': int(tp),
        'true_negatives': int(tn),
        'false_positives': int(fp),
        'false_negatives': int(fn),
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
        f.write("Main Track Identification Metrics\n")
        f.write("=" * 60 + "\n\n")
        
        f.write("Confusion Matrix:\n")
        f.write(f"  True Negatives:  {metrics['true_negatives']}\n")
        f.write(f"  False Positives: {metrics['false_positives']}\n")
        f.write(f"  False Negatives: {metrics['false_negatives']}\n")
        f.write(f"  True Positives:  {metrics['true_positives']}\n\n")
        
        f.write("Performance Metrics:\n")
        f.write(f"  Accuracy:    {metrics['accuracy']:.4f}\n")
        f.write(f"  Precision:   {metrics['precision']:.4f}\n")
        f.write(f"  Recall:      {metrics['recall']:.4f}\n")
        f.write(f"  Specificity: {metrics['specificity']:.4f}\n")
        f.write(f"  F1-Score:    {metrics['f1_score']:.4f}\n")
        f.write(f"  AUC:         {metrics['auc']:.4f}\n")
    
    if verbose:
        print(f"  ✓ Saved metrics report to {output_path}")


def select_main_tracks(images, metadata, mt_indices, output_dir=None, verbose=False):
    """
    Select only the clusters identified as main tracks.
    
    Args:
        images: All cluster images
        metadata: All cluster metadata
        mt_indices: Indices of predicted main tracks
        output_dir: Optional directory to save selected data
        verbose: Print progress
        
    Returns:
        dict with selected images and metadata
    """
    
    selected_images = images[mt_indices]
    selected_metadata = metadata[mt_indices]
    
    if verbose:
        print(f"\n  Selected {len(mt_indices)} main track clusters")
    
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        np.savez(
            output_path / 'selected_main_tracks.npz',
            images=selected_images,
            metadata=selected_metadata
        )
        
        if verbose:
            print(f"  ✓ Saved selected main tracks to {output_path}")
    
    return {
        'images': selected_images,
        'metadata': selected_metadata,
        'n_selected': len(mt_indices)
    }
