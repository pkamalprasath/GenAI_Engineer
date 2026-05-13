# Architecture: GPT-2 Training from Scratch

## System Overview

```
FineWeb Dataset (10B tokens)

Data Pipeline (Tokenization + Streaming)

GPT-2 Model (85M parameters)

Training Loop (AdamW optimizer)
 Forward pass
 Loss computation (language modeling)
 Backward pass
 Parameter updates

Evaluation (HellaSwag benchmark)

Checkpointing & Inference
```

## Model Architecture

### GPT-2 Configuration

```
Component           | Value

Embedding Dim       | 768
Num Heads           | 12
Num Layers          | 12
FFN Hidden          | 3072
Vocabulary Size     | 50,257
Context Window      | 1024 tokens
Total Parameters    | 85M
```

### Transformer Block Structure

```

‚ Layer Normalization‚

‚
–
‚ Multi-Head‚
‚ Self-Attention‚
‚ (12 heads)‚

‚
–
‚ Residual‚
‚ Connection‚

‚
–
‚ Layer Normalization‚

‚
–
‚ Feed-Forward‚
‚ (768 3072 768)‚

‚
–
‚ Residual‚
‚ Connection‚

‚
         Output
```

## Data Pipeline

### FineWeb Dataset

- **Source**: Hugging Face FineWeb
- **Size**: 10 billion tokens
- **Quality**: High-quality web text
- **Preprocessing**: Tokenization, filtering, formatting

### Data Loading Strategy

```
Dataset (on disk)

Streaming Reader (lazy loading)

Tokenizer (GPT-2 BPE)

Chunking (seq_length = 1024)

DataLoader (batching)

Training Loop
```

### Efficient Streaming

```python
# Memory-efficient batch loading
for batch in dataloader:
    input_ids = batch['input_ids']      # (batch_size, 1024)
    # Process one batch at a time
    # No need to load entire dataset
```

## Training Configuration

### Hyperparameters

```
Learning Rate:        6e-4 (with cosine decay)
Batch Size:          64
Gradient Accumulation: 4 (effective: 256)
Weight Decay:        0.1
Beta1, Beta2:        0.9, 0.95
Warmup Steps:        2,000
Total Steps:         100,000
Checkpoint Interval: 5,000 steps
```

### Learning Rate Schedule

```
LR value
‚
 6e-4
‚‚ (cosine decay)
‚ 0 (annealing)
‚
 0 (warmup) 6e-4
  0           2000  steps
```

### Gradient Accumulation

```
Effective Batch Size = Batch Size Ã Accumulation Steps
                     = 64 Ã 4
                     = 256
```

## Training Loop

### Forward Pass

```python
# Input: (batch_size, seq_len)
input_ids = batch['input_ids']

# Embedding: (batch_size, seq_len, 768)
x = token_embedding(input_ids)
x = x + positional_embedding(positions)

# Transformer blocks (12 layers)
for block in transformer_blocks:
    x = block(x)  # (batch_size, seq_len, 768)

# Output projection: (batch_size, seq_len, vocab_size)
logits = output_projection(x)
```

### Loss Computation

```python
# Shift targets (causal language modeling)
# Input:  [BOS, token_1, token_2, ..., token_n]
# Target: [token_1, token_2, ..., token_n, EOS]

loss = cross_entropy(logits[:, :-1, :], targets[:, 1:])
# Only compute loss on actual tokens (not padding)
```

### Backward Pass

```python
loss.backward()
torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
optimizer.step()
optimizer.zero_grad()
```

## Evaluation Strategy

### HellaSwag Benchmark

- **Task**: 4-way multiple choice question answering
- **Evaluation**: Zero-shot on validation set
- **Metric**: Accuracy (random baseline: 25%)
- **Expected**: 32-35% for trained GPT-2 small

### Validation Loss Monitoring

```
Epoch Loss
‚
 5.2 (initial - random)
 4.1 (early learning)
 3.2 (pattern recognition)
 2.8 (semantic understanding)
 2.5 (convergence)
```

## Checkpointing Strategy

### What to Save

```python
checkpoint = {
    'step': current_step,
    'model_state_dict': model.state_dict(),
    'optimizer_state_dict': optimizer.state_dict(),
    'learning_rate_scheduler': scheduler.state_dict(),
    'training_loss': training_loss,
    'validation_loss': validation_loss,
    'config': model_config
}
```

### Resumable Training

```python
# Load checkpoint
checkpoint = torch.load('checkpoint_50000.pt')
model.load_state_dict(checkpoint['model_state_dict'])
optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
start_step = checkpoint['step']

# Resume from step 50000
for step in range(start_step, total_steps):
    # Training continues...
```

## Performance Optimization

### Multi-GPU Training

```python
# Distributed Data Parallel
model = torch.nn.parallel.DistributedDataParallel(model)

# Each GPU gets a data shard
# Gradients synchronized across GPUs
```

### Mixed Precision Training

```python
# Using Automatic Mixed Precision (AMP)
scaler = torch.cuda.amp.GradScaler()

with torch.cuda.amp.autocast():
    logits = model(input_ids)
    loss = criterion(logits, targets)

scaler.scale(loss).backward()
scaler.step(optimizer)
scaler.update()
```

### Gradient Checkpointing

```python
# Trade memory for compute (useful for large models)
# Store only activations at checkpoints
# Recompute intermediate activations on backward pass
model.gradient_checkpointing_enable()
```

## Inference Utilities

### Sampling Strategy

```
Logits Softmax Sample Token
                 (temperature scaling)
```

### Sampling with Temperature

```python
logits = logits / temperature  # Lower temp = more confident

# Top-K sampling
top_k_logits, top_k_indices = torch.topk(logits, k=50)
probs = torch.softmax(top_k_logits, dim=-1)
next_token = top_k_indices[torch.multinomial(probs, 1)]
```

### Generation Loop

```python
input_ids = [BOS_TOKEN_ID]

for step in range(max_tokens):
    # Get next token probabilities
    logits = model(input_ids)[:, -1, :]
    
    # Sample next token
    next_token = sample(logits, temperature=0.7)
    
    # Append to sequence
    input_ids.append(next_token)
    
    if next_token == EOS_TOKEN_ID:
        break
```

## File Organization

```
src/
 train_gpt2.py Main training script
 fineweb.py Data loading from FineWeb
 hellaswag.py HellaSwag evaluation
 inference.py Sampling and generation

config/
 training_config.py Hyperparameters

scripts/
 train.py Entry point for training
 evaluate.py Entry point for evaluation
```

---

**Status**: Complete & Documented  
**Last Updated**: May 2026
