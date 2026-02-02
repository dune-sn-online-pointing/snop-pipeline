#!/usr/bin/env python3
"""
CT analysis script: compute metrics and generate plots for channel tagging results.
"""

import sys
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix, roc_curve, auc, precision_recall_curve


def load_predictions(predictions_path):
    data = np.load(predictions_path)
    # expected fields: y_true (0/1), y_pred_proba
    return data


def analyze(predictions_npz, output_dir="results/ct_analysis"):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    data = load_predictions(predictions_npz)
    y_true = data['y_true']
    y_pred_proba = data['y_pred_proba']

    # basic metrics
    fpr, tpr, _ = roc_curve(y_true, y_pred_proba)
    roc_auc = auc(fpr, tpr)

    # threshold 0.5
    thresh = 0.5
    y_pred = (y_pred_proba >= thresh).astype(int)
    cm = confusion_matrix(y_true, y_pred)

    # plots
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    # ROC
    ax = axes[0]
    ax.plot(fpr, tpr, label=f'AUC={roc_auc:.3f}')
    ax.plot([0,1],[0,1],'k--')
    ax.set_title('ROC Curve')
    ax.set_xlabel('FPR'); ax.set_ylabel('TPR')
    ax.legend()

    # Precision-Recall
    prec, rec, _ = precision_recall_curve(y_true, y_pred_proba)
    ax = axes[1]
    ax.plot(rec, prec)
    ax.set_title('Precision-Recall')
    ax.set_xlabel('Recall'); ax.set_ylabel('Precision')

    # Confusion matrix
    ax = axes[2]
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=ax)
    ax.set_title(f'Confusion Matrix @ {thresh}')
    ax.set_xlabel('Predicted'); ax.set_ylabel('True')

    plt.tight_layout()
    fig_path = output_dir / 'ct_analysis.pdf'
    plt.savefig(fig_path, bbox_inches='tight', dpi=150)
    print(f"Saved CT analysis to: {fig_path}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: analyze_ct_results.py <predictions.npz> [output_dir]')
        sys.exit(1)
    predictions = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else 'results/ct_analysis'
    analyze(predictions, out)
