# Build Small Language Model from Scratch

Educational implementation of a small language model (SLM) built completely from first principles. This project is ideal for learning transformer architectures, optimization, and language modeling fundamentals.

## Project Overview

**Goal**: Build a small language model from scratch to understand core concepts  
**Model Size**: 10M-50M parameters (tunable)  
**Dataset**: Common text datasets (Wikitext, TinyStories)  
**Focus**: Educational clarity and understanding

## Educational Objectives

- Understand transformer architecture fundamentals
- Implement attention mechanisms from scratch
- Learn tokenization and data preprocessing
- Master optimization and training loops
- Explore model scaling and efficiency

##Å Project Structure

```
04_Build_SLM_from_Scratch/
 README.md
 ARCHITECTURE.md
 requirements.txt
 LICENSE
 .gitignore
Ç
 notebooks/
Ç 01_Build_SLM_from_Scratch_Main.ipynb
Ç
 src/
Ç __init__.py
Ç tokenizer.py           (Custom tokenizer)
Ç model.py               (SLM architecture)
Ç dataset.py             (Data handling)
Ç training.py            (Training loop)
Ç evaluation.py          (Metrics & evaluation)
Ç
 config/
Ç __init__.py
Ç model_config.py
Ç training_config.py
Ç
 scripts/
Ç __init__.py
Ç train.py
Ç evaluate.py
Ç generate.py
Ç
 docs/
 ARCHITECTURE.md
 TRAINING_GUIDE.md
 DEPLOYMENT.md
```

## Quick Start

### 1. Setup
```bash
cd 04_Build_SLM_from_Scratch
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Train Model
```bash
python scripts/train.py \
    --vocab_size 10000 \
    --hidden_dim 256 \
    --num_layers 6 \
    --epochs 10
```

### 3. Evaluate & Generate
```bash
python scripts/generate.py \
    --prompt "The future of AI is" \
    --max_tokens 50
```

## Architecture Overview

### Model Components

```
Input Tokens

Token Embedding (vocab_size hidden_dim)

Positional Encoding

Transformer Blocks (N layers)
 Multi-Head Self-Attention
 Feed-Forward Network
 Layer Normalization & Residuals

Output Linear Layer (hidden_dim vocab_size)

Logits & Probability Distribution
```

### Key Hyperparameters

| Parameter | Default | Range |
|-----------|---------|-------|
| vocab_size | 10,000 | 5K-50K |
| hidden_dim | 256 | 64-768 |
| num_heads | 4 | 2-12 |
| num_layers | 6 | 3-12 |
| context_length | 256 | 128-1024 |
| batch_size | 32 | 8-128 |
| learning_rate | 1e-3 | 1e-5-1e-2 |

## Training Dynamics

### Loss Curve
```
Epoch 1:  Loss = 5.2 (random predictions)
Epoch 2:  Loss = 4.1 (learning patterns)
Epoch 3:  Loss = 3.2 (improving predictions)
...
Epoch 10: Loss = 2.1 (convergence)
```

### Learning Progression
- **Early epochs**: Model learns character/word patterns
- **Mid epochs**: Sentence structure emerges
- **Late epochs**: Semantic understanding develops

## Learning Path

### Beginner Level
1. Read ARCHITECTURE.md for concepts
2. Run notebook with default config
3. Observe loss convergence
4. Experiment with batch_size

### Intermediate Level
1. Modify model_config.py parameters
2. Implement custom tokenizer
3. Add new layers (LayerNorm, Dropout)
4. Train on different datasets

### Advanced Level
1. Implement attention visualizations
2. Add quantization/pruning
3. Multi-GPU training
4. Custom optimizers

## Experiments

### Model Size Comparison
```python
configs = [
    {'hidden_dim': 128, 'num_layers': 3},   # 2M params
    {'hidden_dim': 256, 'num_layers': 6},   # 10M params
    {'hidden_dim': 512, 'num_layers': 12},  # 50M params
]

for config in configs:
    train_and_evaluate(config)
```

### Learning Rate Study
```python
learning_rates = [1e-5, 1e-4, 1e-3, 1e-2]

for lr in learning_rates:
    train_model(learning_rate=lr)
    plot_convergence()
```

## Expected Results

| Setting | Loss | Perplexity | Time |
|---------|------|-----------|------|
| Tiny (2M) | 2.8 | 16.4 | 10 min |
| Small (10M) | 2.1 | 8.2 | 30 min |
| Medium (50M) | 1.8 | 6.0 | 2 hours |

## Requirements

- Python 3.8+
- PyTorch 1.9+
- NumPy & Pandas
- Matplotlib for visualization

See `requirements.txt` for pinned versions.

## Implementation Highlights

### Custom Tokenizer (BPE)
```python
from src.tokenizer import BPETokenizer

tokenizer = BPETokenizer(vocab_size=10000)
tokens = tokenizer.encode("Hello, world!")
```

### Clean Training Loop
```python
from src.training import train

history = train(
    model=model,
    train_loader=train_loader,
    val_loader=val_loader,
    epochs=10,
    learning_rate=1e-3
)
```

### Text Generation
```python
from src.model import generate

text = generate(
    model=model,
    tokenizer=tokenizer,
    prompt="The story begins",
    max_tokens=100
)
```

##ñ Learning Resources

- **Chapter 1**: Token embeddings and positional encoding
- **Chapter 2**: Attention mechanism step-by-step
- **Chapter 3**: Transformer blocks and stacking
- **Chapter 4**: Training optimization techniques
- **Chapter 5**: Generation and decoding strategies

## Project Goals Achieved

 Understand transformer architecture  
 Implement from scratch without heavy frameworks  
 Learn optimization and convergence  
 Practical experience with PyTorch  
 Foundation for advanced LLM work  

## License

MIT License - See LICENSE file

---

**Status**: Educational & Complete  
**Last Updated**: May 2026  
**Author**: Kamal Prasath  
**Ideal For**: Students, researchers, ML engineers
