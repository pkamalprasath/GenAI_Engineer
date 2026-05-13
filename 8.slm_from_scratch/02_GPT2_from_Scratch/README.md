# GPT-2 Training from Scratch

Complete implementation of GPT-2 model training from scratch using the FineWeb dataset. This project demonstrates transformer architecture fundamentals, efficient data loading, and language model training best practices.

## Project Overview

**Goal**: Build and train a GPT-2 style language model from scratch  
**Dataset**: FineWeb (web-scale high-quality text)  
**Model Size**: 85M parameters (GPT-2 small)  
**Framework**: PyTorch + Transformers

## Key Features

- Custom data pipeline for efficient streaming
- Multi-GPU training support
- Evaluation with HellaSwag benchmark
- Inference utilities with sampling
- Checkpointing and resumable training

##Å Project Structure

```
02_GPT2_from_Scratch/
 README.md
 ARCHITECTURE.md
 requirements.txt
 LICENSE
 .gitignore
Ç
 notebooks/
Ç 01_GPT2_from_Scratch_Main.ipynb
Ç
 src/
Ç __init__.py
Ç train_gpt2.py          (Main training script)
Ç fineweb.py             (Data loading)
Ç hellaswag.py           (Evaluation)
Ç inference.py           (Inference utilities)
Ç
 config/
Ç __init__.py
Ç training_config.py
Ç
 scripts/
Ç __init__.py
Ç train.py               (Training entry point)
Ç evaluate.py            (Evaluation entry point)
Ç
 docs/
 ARCHITECTURE.md
 DEPLOYMENT.md
```

## Quick Start

### 1. Setup
```bash
cd 02_GPT2_from_Scratch
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Train
```bash
python scripts/train.py \
    --batch_size 64 \
    --learning_rate 6e-4 \
    --num_iterations 100000
```

### 3. Evaluate
```bash
python scripts/evaluate.py \
    --checkpoint best_model.pt
```

### 4. Inference
```python
from src.inference import generate_text

generated = generate_text(
    prompt="The future of AI",
    max_tokens=100
)
print(generated)
```

## Technical Details

### Model Architecture
- **Embedding Dimension**: 768
- **Attention Heads**: 12
- **Layers**: 12
- **Context Window**: 1024 tokens
- **Vocabulary**: 50,257 (GPT-2 tokenizer)

### Training Configuration
- **Optimizer**: AdamW
- **Learning Rate**: 6e-4 (with cosine decay)
- **Batch Size**: 64 (with gradient accumulation)
- **Warmup Steps**: 2,000
- **Total Steps**: 100,000

### Data Pipeline
- **Source**: FineWeb dataset (10B tokens)
- **Preprocessing**: Tokenization with GPT-2 tokenizer
- **Efficiency**: Streaming + memory-mapped files

### Evaluation
- **HellaSwag**: 4-way multiple choice benchmark
- **Perplexity**: Validation set monitoring
- **Checkpoint**: Best model saved based on validation loss

## Expected Results

| Metric | Value |
|--------|-------|
| Validation Perplexity | ~20-25 |
| HellaSwag Accuracy | ~32-35% (2x random) |
| Training Time | ~24-48 hours (single A100) |
| Final Checkpoint Size | ~340 MB |

## Key Implementation Details

### Efficient Data Loading
```python
# Streaming data from FineWeb
for batch in dataloader:
    tokens = batch['input_ids']  # (batch_size, seq_len)
    logits = model(tokens)
    loss = compute_loss(logits, tokens)
```

### Multi-GPU Training
```python
# Distributed data parallel
model = torch.nn.parallel.DistributedDataParallel(model)
```

### Gradient Accumulation
```python
# Effective batch size = batch_size * accumulation_steps
loss = loss / accumulation_steps
loss.backward()
```

## Requirements

- Python 3.10+
- PyTorch 2.0+
- CUDA 11.8+ (for GPU training)
- 24GB+ GPU memory (recommended)

See `requirements.txt` for all dependencies.

##ñ Learning Outcomes

By studying this project, you'll understand:
1. **Transformer architecture** from ground up
2. **Large-scale data handling** and preprocessing
3. **Distributed training** with PyTorch
4. **Model checkpointing** and resumable training
5. **Evaluation metrics** for language models

## References

- [Language Models are Unsupervised Multitask Learners](https://d4mucfpksywv.cloudfront.net/better-language-models/language_models_are_unsupervised_multitask_learners.pdf) - GPT-2 Paper
- [FineWeb Dataset](https://huggingface.co/datasets/HuggingFaceFW/fineweb) - Data source
- [HellaSwag Benchmark](https://rowanzellers.com/hellaswag/) - Evaluation

## License

MIT License - See LICENSE file

---

**Status**: Complete & Functional  
**Last Updated**: May 2026  
**Author**: Kamal Prasath
