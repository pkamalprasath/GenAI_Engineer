"""
Training Loop Implementation
"""
import torch
import torch.nn as nn
import torch.optim as optim
from typing import Optional, Dict, Tuple
from tqdm import tqdm
import json
from pathlib import Path


class EarlyStopping:
    """Early stopping based on validation metric."""

    def __init__(self, patience: int = 2, mode: str = 'max'):
        """
        Initialize early stopping.

        Args:
            patience: Number of epochs without improvement before stopping
            mode: 'max' for maximizing metric (F1), 'min' for minimizing (loss)
        """
        self.patience = patience
        self.mode = mode
        self.counter = 0
        self.best_value = None
        self.best_epoch = None

    def __call__(self, current_value: float, epoch: int) -> Tuple[bool, bool]:
        """
        Check if should stop training.

        Args:
            current_value: Current metric value
            epoch: Current epoch number

        Returns:
            Tuple of (should_stop, is_improvement)
        """
        if self.best_value is None:
            self.best_value = current_value
            self.best_epoch = epoch
            return False, True

        is_improvement = (
            current_value > self.best_value if self.mode == 'max'
            else current_value < self.best_value
        )

        if is_improvement:
            self.best_value = current_value
            self.best_epoch = epoch
            self.counter = 0
            return False, True
        else:
            self.counter += 1
            should_stop = self.counter >= self.patience
            return should_stop, False


def train_epoch(
    model: nn.Module,
    loader,
    optimizer: optim.Optimizer,
    device: torch.device,
    label_position_fn=None,
) -> float:
    """
    Train for one epoch.

    Args:
        model: Model to train
        loader: Training dataloader
        optimizer: Optimizer
        device: Device (cuda/cpu)
        label_position_fn: Function to get label position for each sample

    Returns:
        Average training loss
    """
    model.train()
    total_loss = 0.0
    num_batches = 0

    progress_bar = tqdm(loader, desc="Training")
    for batch in progress_bar:
        # Move to device
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels = batch['labels'].to(device)
        label_tokens = batch['label_tokens'].to(device)

        # Forward pass
        optimizer.zero_grad()
        outputs = model(input_ids, attention_mask=attention_mask)
        logits = outputs.logits

        # Compute loss at label position
        batch_size = input_ids.shape[0]
        loss = 0.0

        for i in range(batch_size):
            # Get label position for this sample
            if label_position_fn:
                label_pos = label_position_fn(input_ids[i], attention_mask[i])
            else:
                label_pos = (attention_mask[i].sum() - 1).item()

            # Get logits at label position
            label_logits = logits[i, label_pos, :]

            # Compute cross-entropy loss
            sample_loss = nn.functional.cross_entropy(
                label_logits.unsqueeze(0),
                label_tokens[i].unsqueeze(0),
            )
            loss += sample_loss

        # Average loss over batch
        loss = loss / batch_size

        # Backward pass
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()

        total_loss += loss.item()
        num_batches += 1

        progress_bar.set_postfix({'loss': f'{loss.item():.4f}'})

    return total_loss / num_batches


def validate(
    model: nn.Module,
    loader,
    device: torch.device,
    label_position_fn=None,
) -> float:
    """
    Validate model on validation set.

    Args:
        model: Model to validate
        loader: Validation dataloader
        device: Device (cuda/cpu)
        label_position_fn: Function to get label position

    Returns:
        Average validation loss
    """
    model.eval()
    total_loss = 0.0
    num_batches = 0

    with torch.no_grad():
        for batch in loader:
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            label_tokens = batch['label_tokens'].to(device)

            # Forward pass
            outputs = model(input_ids, attention_mask=attention_mask)
            logits = outputs.logits

            # Compute loss
            batch_size = input_ids.shape[0]
            loss = 0.0

            for i in range(batch_size):
                if label_position_fn:
                    label_pos = label_position_fn(input_ids[i], attention_mask[i])
                else:
                    label_pos = (attention_mask[i].sum() - 1).item()

                label_logits = logits[i, label_pos, :]
                sample_loss = nn.functional.cross_entropy(
                    label_logits.unsqueeze(0),
                    label_tokens[i].unsqueeze(0),
                )
                loss += sample_loss

            loss = loss / batch_size
            total_loss += loss.item()
            num_batches += 1

    return total_loss / num_batches


def train(
    model: nn.Module,
    train_loader,
    val_loader,
    num_epochs: int = 3,
    learning_rate: float = 5e-5,
    device: str = 'cuda',
    checkpoint_path: str = 'best_model.pt',
    log_path: str = 'training_log.json',
    patience: int = 2,
    label_position_fn=None,
) -> Dict:
    """
    Full training loop with early stopping.

    Args:
        model: Model to train
        train_loader: Training dataloader
        val_loader: Validation dataloader
        num_epochs: Number of epochs
        learning_rate: Learning rate
        device: Device name
        checkpoint_path: Path to save best checkpoint
        log_path: Path to save training log
        patience: Early stopping patience
        label_position_fn: Function to compute label position

    Returns:
        Dictionary with training history
    """
    device = torch.device(device)
    model = model.to(device)

    # Optimizer (only LoRA parameters if available)
    if hasattr(model, 'lora_modules'):
        params = [p for n, p in model.named_parameters() if 'lora' in n]
        print(f"Training {len(params)} LoRA parameters")
    else:
        params = model.parameters()

    optimizer = optim.AdamW(params, lr=learning_rate, weight_decay=0.01)

    # Early stopping
    early_stopping = EarlyStopping(patience=patience, mode='max')

    # Training history
    history = {
        'train_loss': [],
        'val_loss': [],
        'val_f1': [],
    }

    for epoch in range(num_epochs):
        print(f"\n{'='*50}")
        print(f"Epoch {epoch+1}/{num_epochs}")
        print(f"{'='*50}")

        # Train
        train_loss = train_epoch(
            model, train_loader, optimizer, device,
            label_position_fn=label_position_fn
        )
        history['train_loss'].append(train_loss)
        print(f"Training Loss: {train_loss:.4f}")

        # Validate
        val_loss = validate(
            model, val_loader, device,
            label_position_fn=label_position_fn
        )
        history['val_loss'].append(val_loss)
        print(f"Validation Loss: {val_loss:.4f}")

        # Save checkpoint
        checkpoint = {
            'epoch': epoch,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'train_loss': train_loss,
            'val_loss': val_loss,
        }
        torch.save(checkpoint, checkpoint_path)

        # Early stopping check
        should_stop, is_improvement = early_stopping(val_loss, epoch)
        if is_improvement:
            print(f"✓ Validation loss improved to {val_loss:.4f}")
        else:
            print(f"✗ No improvement (best: {early_stopping.best_value:.4f})")

        if should_stop:
            print(f"\nEarly stopping at epoch {epoch+1} (patience exhausted)")
            break

    # Save training log
    with open(log_path, 'w') as f:
        json.dump(history, f, indent=2)
    print(f"\nTraining log saved to {log_path}")
    print(f"Best checkpoint saved to {checkpoint_path}")

    return history
