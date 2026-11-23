"""
Training Entry Point

Usage:
    python scripts/train.py --technique lora --epochs 3 --batch_size 32
"""
import sys
import argparse
sys.path.insert(0, '.')

from config.training_config import TrainingConfig
from config.model_config import ModelConfig
from src.model import GPT
from src.lora import apply_lora, count_lora_params, count_total_params
from src.dataset import load_hf_dataset, prepare_dataset
from src.training import train
import torch
from transformers import GPT2Tokenizer


def main():
    parser = argparse.ArgumentParser(description='Train Finance SLM')
    parser.add_argument('--technique', default='lora', choices=['lora', 'adapter', 'prefix', 'full'])
    parser.add_argument('--epochs', type=int, default=3)
    parser.add_argument('--batch_size', type=int, default=32)
    parser.add_argument('--learning_rate', type=float, default=5e-5)
    parser.add_argument('--device', default='cuda' if torch.cuda.is_available() else 'cpu')
    parser.add_argument('--checkpoint', default='best_model_{technique}.pt')
    args = parser.parse_args()

    print("[INFO] Loading configuration...")
    model_config = ModelConfig()
    training_config = TrainingConfig()

    # Override with CLI args
    training_config.num_epochs = args.epochs
    training_config.batch_size = args.batch_size
    training_config.learning_rate = args.learning_rate

    print(model_config)
    print(training_config)

    # Load tokenizer
    print("[INFO] Loading tokenizer...")
    tokenizer = GPT2Tokenizer.from_pretrained('gpt2')

    # Load dataset
    print("[INFO] Loading dataset...")
    try:
        dataset = load_hf_dataset()
        train_loader, val_loader = prepare_dataset(
            dataset,
            tokenizer,
            batch_size=training_config.batch_size,
            max_length=training_config.max_length,
        )
        print(f"[OK] Train samples: {len(train_loader.dataset)}")
        print(f"[OK] Val samples: {len(val_loader.dataset)}")
    except Exception as e:
        print(f"[ERROR] Failed to load dataset: {e}")
        return

    # Initialize model
    print("[INFO] Initializing model...")
    model = GPT(model_config)
    print(f"[OK] Model parameters: {count_total_params(model):,}")

    # Apply fine-tuning technique
    if args.technique == 'lora':
        print("[INFO] Applying LoRA...")
        model = apply_lora(
            model,
            rank=training_config.lora_rank,
            alpha=training_config.lora_alpha,
        )
        lora_params = count_lora_params(model)
        total_params = count_total_params(model)
        print(f"[OK] LoRA parameters: {lora_params:,} ({100*lora_params/total_params:.2f}%)")
    elif args.technique == 'adapter':
        print("[WARN] Adapter tuning not yet implemented")
    elif args.technique == 'prefix':
        print("[WARN] Prefix tuning not yet implemented")

    # Train
    print("[INFO] Starting training...")
    checkpoint_path = args.checkpoint.format(technique=args.technique)

    history = train(
        model,
        train_loader,
        val_loader,
        num_epochs=training_config.num_epochs,
        learning_rate=training_config.learning_rate,
        device=args.device,
        checkpoint_path=checkpoint_path,
        log_path=f'training_log_{args.technique}.json',
        patience=training_config.patience,
    )

    print("[OK] Training complete!")


if __name__ == '__main__':
    main()
