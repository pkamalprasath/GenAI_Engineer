"""
Evaluation Entry Point

Usage:
    python scripts/evaluate.py --checkpoint best_model_lora.pt --technique lora
"""
import sys
import argparse
sys.path.insert(0, '.')

from config.model_config import ModelConfig
from src.model import GPT
from src.lora import apply_lora
from src.dataset import load_hf_dataset, prepare_dataset
from src.evaluation import evaluate, print_metrics
import torch
from transformers import GPT2Tokenizer


def main():
    parser = argparse.ArgumentParser(description='Evaluate Finance SLM')
    parser.add_argument('--checkpoint', required=True, help='Path to checkpoint')
    parser.add_argument('--technique', default='lora', choices=['lora', 'adapter', 'prefix', 'full'])
    parser.add_argument('--batch_size', type=int, default=32)
    parser.add_argument('--device', default='cuda' if torch.cuda.is_available() else 'cpu')
    args = parser.parse_args()

    device = torch.device(args.device)

    print("[INFO] Loading configuration...")
    model_config = ModelConfig()

    # Load tokenizer
    print("[INFO] Loading tokenizer...")
    tokenizer = GPT2Tokenizer.from_pretrained('gpt2')

    # Load dataset
    print("[INFO] Loading dataset...")
    try:
        dataset = load_hf_dataset()
        _, val_loader = prepare_dataset(
            dataset,
            tokenizer,
            batch_size=args.batch_size,
            max_length=128,
        )
        print(f"[OK] Validation samples: {len(val_loader.dataset)}")
    except Exception as e:
        print(f"[ERROR] Failed to load dataset: {e}")
        return

    # Initialize model
    print("[INFO] Initializing model...")
    model = GPT(model_config).to(device)

    # Apply technique
    if args.technique == 'lora':
        print("[INFO] Applying LoRA...")
        model = apply_lora(model)

    # Load checkpoint
    print(f"[INFO] Loading checkpoint: {args.checkpoint}")
    try:
        checkpoint = torch.load(args.checkpoint, map_location=device)
        if isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
            model.load_state_dict(checkpoint['model_state_dict'])
        else:
            model.load_state_dict(checkpoint)
        print("[OK] Checkpoint loaded")
    except Exception as e:
        print(f"[ERROR] Failed to load checkpoint: {e}")
        return

    # Evaluate
    print("[INFO] Evaluating...")
    try:
        predictions, labels, metrics = evaluate(model, val_loader, device)
        print_metrics(metrics)
    except Exception as e:
        print(f"[ERROR] Evaluation failed: {e}")
        return

    print("[OK] Evaluation complete!")


if __name__ == '__main__':
    main()
