"""
Model Evaluation & Metrics
"""
import torch
import torch.nn as nn
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
import numpy as np
from typing import Dict, List, Tuple


def evaluate(
    model: nn.Module,
    loader,
    device: torch.device,
    label_position_fn=None,
    label_tokens: Dict[int, int] = None,
) -> Tuple[List, List, Dict]:
    """
    Evaluate model on a dataset.

    Args:
        model: Model to evaluate
        loader: Data loader
        device: Device (cuda/cpu)
        label_position_fn: Function to compute label position
        label_tokens: Mapping from class to token ID

    Returns:
        Tuple of (predictions, labels, metrics)
    """
    if label_tokens is None:
        label_tokens = {0: 2430, 1: 8944, 2: 3231}

    model.eval()
    all_preds = []
    all_labels = []
    error_count = 0

    with torch.no_grad():
        for batch in loader:
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['labels'].to(device)

            try:
                # Forward pass
                outputs = model(input_ids, attention_mask=attention_mask)
                logits = outputs.logits

                # Extract predictions at label position
                batch_size = input_ids.shape[0]

                for i in range(batch_size):
                    # Get label position
                    if label_position_fn:
                        label_pos = label_position_fn(input_ids[i], attention_mask[i])
                    else:
                        label_pos = (attention_mask[i].sum() - 1).item()

                    # Get logits at label position
                    label_logits = logits[i, label_pos, :]

                    # Get prediction (argmax of label token logits)
                    label_token_ids = torch.tensor(
                        [label_tokens[k] for k in sorted(label_tokens.keys())],
                        device=device
                    )
                    label_token_logits = label_logits[label_token_ids]
                    pred = torch.argmax(label_token_logits).item()

                    all_preds.append(pred)
                    all_labels.append(labels[i].item())

            except Exception as e:
                print(f"Error processing batch: {e}")
                error_count += 1
                continue

    all_preds = np.array(all_preds)
    all_labels = np.array(all_labels)

    # Compute metrics
    metrics = compute_metrics(all_labels, all_preds)
    metrics['error_count'] = error_count

    return all_preds, all_labels, metrics


def compute_metrics(
    labels: np.ndarray,
    predictions: np.ndarray,
    target_names: List[str] = None,
    output_dict: bool = False,
) -> Dict:
    """
    Compute classification metrics.

    Args:
        labels: Ground truth labels
        predictions: Predicted labels
        target_names: Names of classes
        output_dict: Return as dictionary

    Returns:
        Dictionary with metrics
    """
    if target_names is None:
        target_names = ['Negative', 'Neutral', 'Positive']

    # Generate report
    report = classification_report(
        labels,
        predictions,
        target_names=target_names,
        output_dict=True,
        zero_division=0,
    )

    # Add overall metrics
    metrics = {
        'f1_macro': f1_score(labels, predictions, average='macro', zero_division=0),
        'f1_weighted': f1_score(labels, predictions, average='weighted', zero_division=0),
        'precision_macro': precision_score(labels, predictions, average='macro', zero_division=0),
        'recall_macro': recall_score(labels, predictions, average='macro', zero_division=0),
        'accuracy': np.mean(labels == predictions),
        'per_class': report,
    }

    return metrics


def print_metrics(metrics: Dict, class_names: List[str] = None):
    """Pretty print metrics."""
    if class_names is None:
        class_names = ['Negative', 'Neutral', 'Positive']

    print("\n" + "="*60)
    print("EVALUATION METRICS")
    print("="*60)

    print(f"\nOverall Metrics:")
    print(f"  Accuracy:        {metrics['accuracy']:.4f}")
    print(f"  F1 (Macro):      {metrics['f1_macro']:.4f}")
    print(f"  F1 (Weighted):   {metrics['f1_weighted']:.4f}")
    print(f"  Precision:       {metrics['precision_macro']:.4f}")
    print(f"  Recall:          {metrics['recall_macro']:.4f}")

    print(f"\nPer-Class Metrics:")
    print(f"{'Class':<12} {'Precision':<12} {'Recall':<12} {'F1':<12} {'Support':<10}")
    print("-" * 60)

    for class_name in class_names:
        class_metrics = metrics['per_class'].get(class_name, {})
        precision = class_metrics.get('precision', 0.0)
        recall = class_metrics.get('recall', 0.0)
        f1 = class_metrics.get('f1-score', 0.0)
        support = int(class_metrics.get('support', 0))

        print(f"{class_name:<12} {precision:>11.4f} {recall:>11.4f} {f1:>11.4f} {support:>9}")

    print("-" * 60)

    # Macro averages
    class_metrics = metrics['per_class'].get('macro avg', {})
    print(f"{'Macro Avg':<12} {class_metrics.get('precision', 0):.4f}         "
          f"{class_metrics.get('recall', 0):.4f}         "
          f"{class_metrics.get('f1-score', 0):.4f}")

    if 'error_count' in metrics:
        print(f"\nProcessing Errors: {metrics['error_count']}")
    print("="*60 + "\n")


def generate_report(
    labels: np.ndarray,
    predictions: np.ndarray,
    class_names: List[str] = None,
) -> str:
    """Generate text report of metrics."""
    if class_names is None:
        class_names = ['Negative', 'Neutral', 'Positive']

    report = classification_report(
        labels,
        predictions,
        target_names=class_names,
        zero_division=0,
    )
    return report


def plot_confusion_matrix(
    labels: np.ndarray,
    predictions: np.ndarray,
    class_names: List[str] = None,
    save_path: str = None,
):
    """Plot confusion matrix."""
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError:
        print("matplotlib and seaborn required for plotting")
        return

    if class_names is None:
        class_names = ['Negative', 'Neutral', 'Positive']

    cm = confusion_matrix(labels, predictions)

    plt.figure(figsize=(8, 6))
    sns.heatmap(
        cm,
        annot=True,
        fmt='d',
        cmap='Blues',
        xticklabels=class_names,
        yticklabels=class_names,
    )
    plt.title('Confusion Matrix')
    plt.ylabel('True Label')
    plt.xlabel('Predicted Label')
    plt.tight_layout()

    if save_path:
        plt.savefig(save_path)
        print(f"Confusion matrix saved to {save_path}")

    plt.show()
