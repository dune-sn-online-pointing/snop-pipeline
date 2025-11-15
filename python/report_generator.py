#!/usr/bin/env python3
"""
Report Generator Module

Generates PDF reports with plots and metrics from the pipeline.
"""

import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.backends.backend_pdf
from datetime import datetime


def generate_report(metrics_tracker, mt_results, channel_results, output_path,
                   verbose=False):
    """
    Generate comprehensive PDF report with plots and metrics.
    
    Args:
        metrics_tracker: MetricsTracker instance with pipeline metrics
        mt_results: Results from MT identification step
        channel_results: Results from channel tagging step
        output_path: Path to save PDF report
        verbose: Print progress
        
    Returns:
        str: Path to generated report
    """
    
    if verbose:
        print(f"\nGenerating Report:")
        print(f"  Output: {output_path}")
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create PDF
    pdf = matplotlib.backends.backend_pdf.PdfPages(output_path)
    
    try:
        # Page 1: Title and summary
        _create_title_page(pdf, metrics_tracker)
        
        # Page 2: Sample flow diagram
        _create_flow_diagram(pdf, metrics_tracker)
        
        # Page 3: MT identification metrics
        _create_mt_metrics_page(pdf, mt_results)
        
        # Page 4: Channel tagging metrics
        _create_channel_metrics_page(pdf, channel_results)
        
        if verbose:
            print(f"  ✓ Generated report with {pdf.get_pagecount()} pages")
        
    finally:
        pdf.close()
    
    return str(output_path)


def _create_title_page(pdf, metrics_tracker):
    """Create title page with pipeline summary."""
    
    fig = plt.figure(figsize=(8.5, 11))
    ax = fig.add_subplot(111)
    ax.axis('off')
    
    # Title
    title_text = "SN Burst Pipeline Report\nData Selection & Analysis"
    ax.text(0.5, 0.9, title_text, transform=ax.transAxes,
            fontsize=20, weight='bold', ha='center', va='top')
    
    # Timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ax.text(0.5, 0.83, f"Generated: {timestamp}", transform=ax.transAxes,
            fontsize=10, ha='center', va='top', style='italic')
    
    # Summary text
    summary = metrics_tracker.get_summary()
    ax.text(0.1, 0.75, summary, transform=ax.transAxes,
            fontsize=10, ha='left', va='top', family='monospace')
    
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


def _create_flow_diagram(pdf, metrics_tracker):
    """Create sample flow diagram showing progression through pipeline."""
    
    fig, ax = plt.subplots(figsize=(8.5, 11))
    
    metrics = metrics_tracker.metrics['steps']
    
    # Extract numbers for flow
    steps = []
    
    if 'sample_selection' in metrics:
        ss = metrics['sample_selection']
        steps.append(('Sample Selection', ss.get('total_clusters', 0)))
    
    if 'mt_identification' in metrics:
        mt = metrics['mt_identification']
        steps.append(('MT Identification', mt.get('predicted_mt', 0)))
    
    if 'volume_creation' in metrics:
        vc = metrics['volume_creation']
        steps.append(('Volume Creation', vc.get('volumes_created', 0)))
    
    if 'channel_tagging' in metrics:
        ct = metrics['channel_tagging']
        steps.append(('Channel Tagging', ct.get('input_volumes', 0)))
    
    # Plot flow diagram
    y_positions = np.linspace(0.8, 0.2, len(steps))
    
    for i, ((step_name, count), y_pos) in enumerate(zip(steps, y_positions)):
        # Box
        rect = plt.Rectangle((0.15, y_pos - 0.05), 0.7, 0.08,
                             facecolor='lightblue', edgecolor='black', linewidth=2)
        ax.add_patch(rect)
        
        # Text
        ax.text(0.5, y_pos, f"{step_name}\n{count:,} samples",
               ha='center', va='center', fontsize=12, weight='bold')
        
        # Arrow to next step
        if i < len(steps) - 1:
            ax.arrow(0.5, y_pos - 0.06, 0, -0.06,
                    head_width=0.03, head_length=0.02, fc='black', ec='black')
    
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    ax.set_title('Pipeline Sample Flow', fontsize=16, weight='bold', pad=20)
    
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


def _create_mt_metrics_page(pdf, mt_results):
    """Create page with MT identification metrics."""
    
    fig = plt.figure(figsize=(8.5, 11))
    gs = fig.add_gridspec(3, 2, hspace=0.4, wspace=0.3)
    
    metrics = mt_results['metrics']
    
    # Title
    fig.suptitle('Main Track Identification Metrics', fontsize=16, weight='bold')
    
    # 1. Confusion Matrix
    ax1 = fig.add_subplot(gs[0, 0])
    cm = metrics['confusion_matrix']
    im = ax1.imshow(cm, cmap='Blues', aspect='auto')
    ax1.set_xticks([0, 1])
    ax1.set_yticks([0, 1])
    ax1.set_xticklabels(['Not MT', 'MT'])
    ax1.set_yticklabels(['Not MT', 'MT'])
    ax1.set_xlabel('Predicted')
    ax1.set_ylabel('True')
    ax1.set_title('Confusion Matrix')
    
    # Add text annotations
    for i in range(2):
        for j in range(2):
            ax1.text(j, i, str(cm[i, j]), ha='center', va='center',
                    color='white' if cm[i, j] > cm.max()/2 else 'black',
                    fontsize=14, weight='bold')
    
    plt.colorbar(im, ax=ax1)
    
    # 2. Performance Metrics Bar Chart
    ax2 = fig.add_subplot(gs[0, 1])
    perf_metrics = ['Accuracy', 'Precision', 'Recall', 'F1-Score']
    perf_values = [metrics['accuracy'], metrics['precision'],
                  metrics['recall'], metrics['f1_score']]
    bars = ax2.bar(perf_metrics, perf_values, color='steelblue')
    ax2.set_ylim(0, 1)
    ax2.set_ylabel('Score')
    ax2.set_title('Performance Metrics')
    ax2.grid(axis='y', alpha=0.3)
    
    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.3f}', ha='center', va='bottom', fontsize=9)
    
    # 3. ROC Curve
    ax3 = fig.add_subplot(gs[1, :])
    ax3.plot(metrics['fpr'], metrics['tpr'], 'b-', linewidth=2, label=f'AUC = {metrics["auc"]:.4f}')
    ax3.plot([0, 1], [0, 1], 'r--', label='Random')
    ax3.set_xlabel('False Positive Rate')
    ax3.set_ylabel('True Positive Rate')
    ax3.set_title('ROC Curve')
    ax3.legend()
    ax3.grid(alpha=0.3)
    
    # 4. Prediction Distribution
    ax4 = fig.add_subplot(gs[2, 0])
    y_pred_proba = mt_results['y_pred_proba']
    y_true = mt_results['y_true']
    
    ax4.hist(y_pred_proba[y_true == 0], bins=30, alpha=0.5, label='Not MT (true)', color='red')
    ax4.hist(y_pred_proba[y_true == 1], bins=30, alpha=0.5, label='MT (true)', color='blue')
    ax4.set_xlabel('Prediction Probability')
    ax4.set_ylabel('Count')
    ax4.set_title('Prediction Distribution')
    ax4.legend()
    ax4.grid(axis='y', alpha=0.3)
    
    # 5. Summary Statistics
    ax5 = fig.add_subplot(gs[2, 1])
    ax5.axis('off')
    
    summary_text = f"""
    Summary Statistics:
    
    Total Samples: {len(mt_results['y_true']):,}
    Predicted MT: {mt_results['n_predicted_mt']:,}
    
    True Positives: {metrics['true_positives']:,}
    True Negatives: {metrics['true_negatives']:,}
    False Positives: {metrics['false_positives']:,}
    False Negatives: {metrics['false_negatives']:,}
    
    AUC: {metrics['auc']:.4f}
    Accuracy: {metrics['accuracy']:.4f}
    Precision: {metrics['precision']:.4f}
    Recall: {metrics['recall']:.4f}
    Specificity: {metrics['specificity']:.4f}
    """
    
    ax5.text(0.1, 0.9, summary_text, transform=ax5.transAxes,
            fontsize=9, ha='left', va='top', family='monospace')
    
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)


def _create_channel_metrics_page(pdf, channel_results):
    """Create page with channel tagging metrics."""
    
    fig = plt.figure(figsize=(8.5, 11))
    gs = fig.add_gridspec(3, 2, hspace=0.4, wspace=0.3)
    
    metrics = channel_results['metrics']
    
    # Title
    fig.suptitle('Channel Tagging Metrics (ES vs CC)', fontsize=16, weight='bold')
    
    # 1. Confusion Matrix
    ax1 = fig.add_subplot(gs[0, 0])
    cm = metrics['confusion_matrix']
    im = ax1.imshow(cm, cmap='Greens', aspect='auto')
    ax1.set_xticks([0, 1])
    ax1.set_yticks([0, 1])
    ax1.set_xticklabels(['CC', 'ES'])
    ax1.set_yticklabels(['CC', 'ES'])
    ax1.set_xlabel('Predicted')
    ax1.set_ylabel('True')
    ax1.set_title('Confusion Matrix')
    
    # Add text annotations
    for i in range(2):
        for j in range(2):
            ax1.text(j, i, str(cm[i, j]), ha='center', va='center',
                    color='white' if cm[i, j] > cm.max()/2 else 'black',
                    fontsize=14, weight='bold')
    
    plt.colorbar(im, ax=ax1)
    
    # 2. Performance Metrics Bar Chart
    ax2 = fig.add_subplot(gs[0, 1])
    perf_metrics = ['Accuracy', 'Precision', 'Recall', 'F1-Score']
    perf_values = [metrics['accuracy'], metrics['precision'],
                  metrics['recall'], metrics['f1_score']]
    bars = ax2.bar(perf_metrics, perf_values, color='forestgreen')
    ax2.set_ylim(0, 1)
    ax2.set_ylabel('Score')
    ax2.set_title('Performance Metrics')
    ax2.grid(axis='y', alpha=0.3)
    
    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.3f}', ha='center', va='bottom', fontsize=9)
    
    # 3. ROC Curve
    ax3 = fig.add_subplot(gs[1, :])
    ax3.plot(metrics['fpr'], metrics['tpr'], 'g-', linewidth=2, label=f'AUC = {metrics["auc"]:.4f}')
    ax3.plot([0, 1], [0, 1], 'r--', label='Random')
    ax3.set_xlabel('False Positive Rate')
    ax3.set_ylabel('True Positive Rate')
    ax3.set_title('ROC Curve')
    ax3.legend()
    ax3.grid(alpha=0.3)
    
    # 4. Prediction Distribution
    ax4 = fig.add_subplot(gs[2, 0])
    y_pred_proba = channel_results['y_pred_proba']
    y_true = channel_results['y_true']
    
    ax4.hist(y_pred_proba[y_true == 0], bins=30, alpha=0.5, label='CC (true)', color='orange')
    ax4.hist(y_pred_proba[y_true == 1], bins=30, alpha=0.5, label='ES (true)', color='green')
    ax4.set_xlabel('Prediction Probability (ES)')
    ax4.set_ylabel('Count')
    ax4.set_title('Prediction Distribution')
    ax4.legend()
    ax4.grid(axis='y', alpha=0.3)
    
    # 5. Summary Statistics
    ax5 = fig.add_subplot(gs[2, 1])
    ax5.axis('off')
    
    summary_text = f"""
    Summary Statistics:
    
    Total Volumes: {len(channel_results['y_true']):,}
    Predicted ES: {channel_results['n_predicted_es']:,}
    Predicted CC: {channel_results['n_predicted_cc']:,}
    
    True Positives (ES): {metrics['true_positives']:,}
    True Negatives (CC): {metrics['true_negatives']:,}
    False Positives: {metrics['false_positives']:,}
    False Negatives: {metrics['false_negatives']:,}
    
    AUC: {metrics['auc']:.4f}
    Accuracy: {metrics['accuracy']:.4f}
    Precision: {metrics['precision']:.4f}
    Recall: {metrics['recall']:.4f}
    Specificity: {metrics['specificity']:.4f}
    """
    
    ax5.text(0.1, 0.9, summary_text, transform=ax5.transAxes,
            fontsize=9, ha='left', va='top', family='monospace')
    
    pdf.savefig(fig, bbox_inches='tight')
    plt.close(fig)
