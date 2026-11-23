# Architecture: Building Small Language Model from Scratch

## Educational Philosophy

This project teaches **bottom-up understanding** of language models by implementing each component from first principles using NumPy and PyTorch, avoiding high-level abstractions.

## System Architecture

```
Raw Text Dataset

Custom Tokenizer (BPE from scratch)

SLM Architecture (12-layer transformer)
 Token Embedding
 Positional Encoding
 Transformer Blocks (Multi-head attention + FFN)
 Output Linear Layer

Training Loop (Causal language modeling)
 Forward pass
 Loss computation
 Backward pass
 Weight updates

Evaluation & Generation
 Perplexity
 Text generation
 Analysis
```

## Component 1: Tokenizer

The notebook uses the GPT-2 byte-pair-encoding tokenizer from `tiktoken` (50,257 tokens) rather than training its own. Each story is encoded to token IDs and written to memory-mapped `train.bin` / `validation.bin` arrays, so batches can be sampled without loading the whole dataset into RAM.

## Component 2: Embeddings

### Token Embedding Layer

```
Token ID: 105

Embedding Matrix: (vocab_size, hidden_dim)

Embedding: [0.25, -0.12, 0.89, ..., 0.34]  (dimension: hidden_dim)

Shape: (batch_size, seq_length, hidden_dim)
```

### Positional Encoding

**Problem**: Transformer lacks inherent position awareness
**Solution**: Add position information to embeddings

```python
# Sinusoidal positional encoding
PE(pos, 2i)     = sin(pos / 10000^(2i/d))
PE(pos, 2i+1)   = cos(pos / 10000^(2i/d))

# Applied to every embedding:
embedding = token_embedding + positional_embedding
```

### Encoding Visualization

```
Position 0: [sin(0/10000^0), cos(0/10000^0), sin(0/10000^2), ...]
Position 1: [sin(1/10000^0), cos(1/10000^0), sin(1/10000^2), ...]
Position 2: [sin(2/10000^0), cos(2/10000^0), sin(2/10000^2), ...]
...
```

## Component 3: Self-Attention Mechanism

### Attention in 4 Steps

```
Step 1: Project to Q, K, V
  Q = Linear(x)  # Query (batch, seq, hidden)
  K = Linear(x)  # Key
  V = Linear(x)  # Value

Step 2: Compute attention scores
  scores = Q @ K.T / sqrt(d_k)
         = (batch, seq, seq)

Step 3: Apply causal mask (for autoregressive)
  # Prevent attending to future tokens
  scores[i, j] = -inf  for j > i

Step 4: Normalize and apply to values
  attn_weights = softmax(scores, dim=-1)
  output = attn_weights @ V
```

### Multi-Head Attention

```python
# Single head: seq_len Ã seq_len attention
# Multiple heads: process in parallel

for head in range(num_heads):
    Q_h = linear_proj_q(x)[:, head_slice]
    K_h = linear_proj_k(x)[:, head_slice]
    V_h = linear_proj_v(x)[:, head_slice]
    
    output_h = attention(Q_h, K_h, V_h)
    outputs.append(output_h)

output = concat(outputs)  # (batch, seq, hidden)
```

### Causal Masking

```
Regular attention (bidirectional):
  Position 0 attends to: [0]
  Position 1 attends to: [0, 1]
  Position 2 attends to: [0, 1, 2]
  
Causal attention (autoregressive):
  Position 0 attends to: [0]
  Position 1 attends to: [0, 1]
  Position 2 attends to: [0, 1, 2] Can't see future!

Mask matrix (lower triangular):
  [1 0 0]
  [1 1 0]
  [1 1 1]
  
scores = scores + (-inf * (1 - mask))
```

## Component 4: Feed-Forward Network

### FFN Architecture

```
Input: (batch, seq, hidden_dim)

Linear 1: hidden_dim ffn_hidden (4 Ã hidden_dim)

ReLU/GELU activation

Linear 2: ffn_hidden hidden_dim

Output: (batch, seq, hidden_dim)
```

### Implementation

```python
def ffn(x, linear1, linear2, activation):
    x = linear1(x)           # Expand
    x = activation(x)        # Activate
    x = linear2(x)           # Project back
    return x
```

## Component 5: Transformer Block

### Block Structure

```
Input x

LayerNorm

MultiHeadAttention

Residual Connection: x + attn_output

LayerNorm

FeedForward

Residual Connection: + ffn_output

Output
```

### Code Structure

```python
class TransformerBlock(nn.Module):
    def __init__(self, hidden_dim, num_heads, ffn_dim):
        self.ln1 = LayerNorm(hidden_dim)
        self.attn = MultiHeadAttention(hidden_dim, num_heads)
        self.ln2 = LayerNorm(hidden_dim)
        self.ffn = FeedForward(hidden_dim, ffn_dim)
    
    def forward(self, x):
        x = x + self.attn(self.ln1(x))      # Pre-norm
        x = x + self.ffn(self.ln2(x))       # Pre-norm
        return x
```

## Component 6: Complete Model

### SLM Architecture

```
Input Tokens: (batch_size, seq_length)

Token Embedding: (batch, seq, hidden_dim)

Positional Encoding: Add position info

Dropout

Transformer Blocks (N layers):
 Block 1: attention + ffn
 Block 2: attention + ffn
 ...
 Block N: attention + ffn

LayerNorm

Output Linear: (batch, seq, vocab_size)

Logits Softmax Probabilities
```

### Configuration Used

```
vocab_size: 50,257 (GPT-2 tokenizer via tiktoken)
block_size: 128
n_layer:    6
n_head:     6
n_embd:     384
dropout:    0.1
Total:      ~30M params (computed; mostly the token embedding)
```

## Training: Language Modeling

### Causal Language Modeling Task

```
Input sequence:  "The quick brown"
Target sequence: "quick brown fox"

Model predicts: P(quick | The)
                P(brown | The, quick)
                P(fox | The, quick, brown)
```

### Loss Function

```python
# Cross-entropy loss on shifted targets
input_ids  = [BOS, token_1, token_2, ..., token_n]
target_ids = [token_1, token_2, ..., token_n, EOS]

logits = model(input_ids)  # (batch, seq, vocab)
loss = cross_entropy(logits[:-1], target_ids[1:])
```

### Training Loop

```
For each epoch:
  For each batch:
    1. Forward: logits = model(input_ids)
    2. Loss: loss = criterion(logits, targets)
    3. Backward: loss.backward()
    4. Optimize: optimizer.step()
    5. Clear: optimizer.zero_grad()
  
  Validate on holdout set
  Check for convergence
```

### Loss Progression

Measured in the notebook (evaluated every 500 iterations):

```
Step    500: train 9.47 | val 9.48
Step  5,000: train 4.30 | val 4.31
Step 10,000: train 3.18 | val 3.19
Step 19,500: train 2.39 | val 2.40
```

## Evaluation

### Perplexity

```
Perplexity = exp(average_negative_log_likelihood)
           = exp(-1/N * Î£ log(P(token_i)))

Lower perplexity = better predictions
Random baseline: exp(log(vocab_size))
```

### Text Generation

```
Sampling:
1. Get logits from model
2. Apply temperature (softness)
3. Sample from probability distribution
4. Append token to sequence
5. Repeat until EOS or max_length
```

### Sampling with Temperature

```
temperature = 0.1 confident (sharp distribution)
temperature = 1.0 balanced
temperature = 2.0 uncertain (flat distribution)
```

## File Organization

```
notebooks/01_Build_SLM_from_Scratch_Main.ipynb   # tokenization, model, training, loss plots, generation
```
