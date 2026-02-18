# Fine-Tuning Techniques (LoRA / QLoRA / Lamini)

Experiments covering Parameter-Efficient Fine-Tuning (PEFT) techniques for adapting large language models to specific tasks without full model retraining.

## Overview

Full fine-tuning of LLMs requires enormous GPU memory. PEFT techniques like LoRA and QLoRA make fine-tuning accessible on consumer hardware by training only a small fraction of parameters.

## Techniques Covered

| Technique | Notebook / File | Description |
|---|---|---|
| **LoRA** | `LoRa_experiments.ipynb` | Low-Rank Adaptation — adds trainable rank-decomposition matrices |
| **QLoRA** | `QLoRa_experiments.ipynb` | Quantized LoRA — 4-bit quantization + LoRA for minimal GPU usage |
| **LoRA (Colab)** | `LoRA_colab_experiments.ipynb` | LoRA experiments designed for Google Colab |
| **Lamini** | `Lamini.py` | Fine-tuning via the Lamini API (managed fine-tuning service) |

## Tech Stack

| Component | Technology |
|---|---|
| PEFT Library | `peft` (HuggingFace) |
| Quantization | `bitsandbytes` (4-bit/8-bit) |
| Base Models | LLaMA / Mistral (via HuggingFace) |
| Training | `transformers` + `trl` |
| Managed Option | Lamini API |

## Project Structure

```
13.FineTunning_Techniques/
├── LoRa_experiments.ipynb       # LoRA from scratch
├── QLoRa_experiments.ipynb      # QLoRA with 4-bit quantization
├── LoRA_colab_experiments.ipynb # LoRA notebook for Google Colab
├── Lamini.py                    # Lamini API fine-tuning
└── README.md
```

## Key Concepts

### LoRA (Low-Rank Adaptation)
Freezes the original model weights and injects trainable low-rank matrices into attention layers. Only ~0.1–1% of parameters are trained.

```
W_original (frozen) + A × B (trainable, low-rank)
```

### QLoRA
Combines 4-bit NF4 quantization with LoRA. Reduces memory usage by ~4x compared to full-precision LoRA. Enables fine-tuning 7B+ models on a single consumer GPU.

### Lamini
Managed fine-tuning API — submit training data, Lamini handles the infrastructure.

## Requirements

- GPU with CUDA support recommended (QLoRA works on 8–16GB VRAM)
- For Colab: use a T4 or A100 GPU runtime
- HuggingFace token with access to gated models (LLaMA requires approval)

## Environment Variables

| Variable | Purpose |
|---|---|
| `HF_TOKEN` | HuggingFace token for model access |
