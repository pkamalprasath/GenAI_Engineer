"""
Training Configuration
"""


class TrainingConfig:
    """Training hyperparameters."""

    # Optimization
    learning_rate = 5e-5        # AdamW learning rate
    weight_decay = 0.01         # L2 regularization
    warmup_steps = 500          # Linear warmup steps
    max_grad_norm = 1.0         # Gradient clipping

    # Training dynamics
    num_epochs = 3              # Number of epochs
    batch_size = 32             # Batch size
    gradient_accumulation_steps = 1

    # Evaluation
    eval_steps = 100            # Validation frequency
    eval_strategy = 'epoch'     # 'steps', 'epoch', 'no'

    # Early stopping
    patience = 2                # Patience for early stopping
    monitor_metric = 'val_loss' # Metric to monitor
    metric_mode = 'min'         # 'min' or 'max'

    # Data
    val_split = 0.2             # Train/val split
    max_length = 128            # Max sequence length
    seed = 42                   # Random seed

    # Logging
    log_steps = 10              # Log frequency
    save_steps = 100            # Save checkpoint frequency

    # Checkpoint
    checkpoint_dir = './checkpoints'
    checkpoint_name = 'best_model.pt'
    log_path = 'training_log.json'

    # LoRA specific
    use_lora = True             # Use LoRA
    lora_rank = 8               # LoRA rank
    lora_alpha = 16.0           # LoRA scaling (2 * rank)
    lora_dropout = 0.1          # LoRA dropout

    def __repr__(self):
        return (
            f"TrainingConfig(\n"
            f"  learning_rate={self.learning_rate},\n"
            f"  batch_size={self.batch_size},\n"
            f"  num_epochs={self.num_epochs},\n"
            f"  lora_rank={self.lora_rank},\n"
            f"  patience={self.patience}\n"
            f")"
        )

    def to_dict(self):
        """Convert to dictionary."""
        return {
            'learning_rate': self.learning_rate,
            'weight_decay': self.weight_decay,
            'warmup_steps': self.warmup_steps,
            'max_grad_norm': self.max_grad_norm,
            'num_epochs': self.num_epochs,
            'batch_size': self.batch_size,
            'gradient_accumulation_steps': self.gradient_accumulation_steps,
            'eval_steps': self.eval_steps,
            'eval_strategy': self.eval_strategy,
            'patience': self.patience,
            'monitor_metric': self.monitor_metric,
            'metric_mode': self.metric_mode,
            'val_split': self.val_split,
            'max_length': self.max_length,
            'seed': self.seed,
            'use_lora': self.use_lora,
            'lora_rank': self.lora_rank,
            'lora_alpha': self.lora_alpha,
            'lora_dropout': self.lora_dropout,
        }
