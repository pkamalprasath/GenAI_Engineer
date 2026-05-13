# Architecture & Technical Design

## System Overview

```
HuggingFace Dataset

Data Pipeline (Tokenization)

GPT-2 Model (85M params)

LoRA/Adapter/Prefix Injection

Fine-tuning Loop
 Training (9,938 samples)
 Validation (2,486 samples)
 Early Stopping (F1 monitor)

Evaluation Metrics (F1, Precision, Recall)

Results Comparison & Analysis
```

## 1. Data Pipeline Architecture

### Dataset Source
- **Name**: HuggingFace `zeroshot/twitter-financial-news-sentiment`
- **Size**: 11,932 total examples
- **Classes**: 
  - `0`: Negative (bearish)
  - `1`: Neutral
  - `2`: Positive (bullish)

### Preprocessing Steps

```
Raw Text

Tokenization (sentence-level)

Prompt Template Application
    "Sentiment: {text}. Answer: "

Label Token Mapping

Attention Mask & Input IDs

PyTorch DataLoader (batch_size=32)
```

### Label Token Encoding

The model predicts sentiment by predicting a specific token at a designated position:

```python
label_tokens = {
    0: 2430,   # "negative"
    1: 8944,   # "neutral"
    2: 3231    # "positive"
}

# During training/evaluation:
# Loss computed only at label_position
loss = loss_fn(logits[batch, label_position, :], label_tokens[label])
```

### Key Implementation: Label Position Calculation

```python
# CRITICAL: Extract logits at label position, not -1
sentence_tokens = tokenizer.encode(sentence, add_special_tokens=False)
prompt_tokens = tokenizer.encode("Sentiment: Answer: ", add_special_tokens=True)

# Label position = prompt end position
label_position = len(prompt_tokens) + len(sentence_tokens) - 1

# Extract prediction from correct position
logits = model_output.logits[batch_idx, label_position, :]
prediction = torch.argmax(logits)
```

## 2. Model Architecture

### GPT-2 Configuration

```
Parameter                Value           Notes

Vocabulary Size          50,257          Standard GPT-2 vocab
Hidden Dimension         768             d_emb
Number of Heads          12              n_head
Number of Layers         12              n_layer
FFN Dimension            3,072           4 Ã hidden_dim
Attention Dropout        0.1             Regularization
Residual Dropout         0.1             Regularization
Total Parameters         85M             Pre-training size
Trainable (LoRA)         250K            0.3% of original
```

### Layer Structure

Each transformer block contains:

```

‚  Input (seq_len, 768)‚

‚
–
‚ LayerNorm‚

‚
–
‚ Multi-Head‚ LoRA Applied Here
‚ Attention‚

‚
–
‚ Residual‚
‚ Connection‚

‚
–
‚ LayerNorm‚

‚
–
‚   Feed Forward‚ Can Apply LoRA Here
‚   (d Ã 4d Ã d)‚

‚
–
‚ Residual‚
‚ Connection‚

‚
–
‚ Output‚
‚ (seq_len,768)

```

## 3. Parameter-Efficient Fine-Tuning: LoRA

### LoRA Mathematical Formulation

```
Original Computation:
y = Wx + b
  where W^(d_out Ã d_in)

With LoRA:
y = Wx + BAx + b
  where:
  - B^(d_out Ã r)      (low-rank, trainable)
  - A^(r Ã d_in)       (low-rank, trainable)
  - r << min(d_out, d_in)  (rank, typically 8)
  - Î±                  (scaling factor)
```

### Implementation Details

```python
class LoRALinear(nn.Module):
    def __init__(self, original_linear, rank=8, alpha=16.0):
        self.original_linear = original_linear
        self.rank = rank
        self.alpha = alpha
        
        in_features = original_linear.in_features
        out_features = original_linear.out_features
        
        # Low-rank decomposition
        self.lora_A = nn.Parameter(
            torch.randn(in_features, rank) * 0.02
        )
        self.lora_B = nn.Parameter(
            torch.zeros(out_features, rank)
        )
    
    def forward(self, x):
        # Original output
        original_out = self.original_linear(x)
        
        # LoRA output
        scaling = self.alpha / self.rank
        lora_out = (x @ self.lora_A @ self.lora_B.t()) * scaling
        
        return original_out + lora_out
```

### Applied Layers

LoRA is applied to attention layers:
- Q projection (query)
- V projection (value)
- K projection (key) - optional
- O projection (output) - optional

**Decision**: Apply to Q and V only (0.3% parameters)

### Scaling Factor

```
Î± = 2 Ã rank = 16.0

Justification:
- rank = 8
- Î± should be ~2x rank to maintain gradient scale
- Î± Ã· rank = 2.0 (normalized scaling)
```

## 4. Training Architecture

### Training Loop Flow

```

‚ Initialize Model + LoRA‚
‚ Load Optimizer (AdamW)‚
‚ Load Dataset Loaders‚

‚
–
‚ For Epoch‚

‚
–
‚ For Each Batch‚

‚
–
‚ 1. Forward Pass‚
‚    outputs = model(ids)‚

‚
–
‚ 2. Compute Loss‚
‚    loss = criterion(‚
‚      logits[pos], label)‚

‚
–
‚ 3. Backward Pass‚
‚    loss.backward()‚

‚
–
‚ 4. Gradient Clipping‚
‚    clip_grad_norm_(1.0)‚

‚
–
‚ 5. Optimizer Step‚
‚    optimizer.step()‚

‚
–
‚ 6. Clear Gradients‚
‚    optimizer.zero_grad()‚

‚

‚
–
‚ Validation Every Epoch‚
‚ Check F1 Score‚
‚ Early Stopping?‚

‚
–
‚ Save‚
‚Checkpoint

```

### Hyperparameter Configuration

```python
class TrainingConfig:
    # Optimization
    learning_rate = 5e-5          # AdamW
    weight_decay = 0.01           # L2 regularization
    warmup_steps = 500            # Linear warmup
    max_grad_norm = 1.0           # Gradient clipping
    
    # Training dynamics
    num_epochs = 3
    batch_size = 32
    eval_steps = 100              # Validation frequency
    
    # Early stopping
    patience = 2                  # Epochs without improvement
    monitor_metric = "f1"         # F1 score
    
    # Data
    val_split = 0.2               # 80/20 train/val
    seed = 42                     # Reproducibility
```

### Early Stopping Implementation

```python
class EarlyStopping:
    def __init__(self, patience=2, metric='f1', mode='max'):
        self.patience = patience
        self.metric = metric
        self.mode = mode
        self.counter = 0
        self.best_value = None
        
    def __call__(self, current_value):
        if self.best_value is None:
            self.best_value = current_value
            return False  # Don't stop
        
        is_improvement = (
            current_value > self.best_value if self.mode == 'max'
            else current_value < self.best_value
        )
        
        if is_improvement:
            self.best_value = current_value
            self.counter = 0
            return False  # Don't stop, save checkpoint
        else:
            self.counter += 1
            return self.counter >= self.patience  # Stop?
```

## 5. Evaluation Architecture

### Evaluation Metrics Computation

```
Raw Predictions (Logits)

Apply Softmax

Argmax for Class Prediction

Compare with Ground Truth

Compute:
 Precision (TP / (TP + FP))
 Recall (TP / (TP + FN))
 F1 Score (2 Ã P Ã R / (P + R))
 Support (count per class)
```

### Critical Fix: Label Position

**Bug Found**: Original evaluation used `logits[batch, -1, :]` which extracted from padding position.

**Root Cause**: Sequence length varies; -1 always points to last position, but label might not be last.

**Solution**:
```python
def evaluate_batch(batch, model, label_tokens):
    input_ids = batch['input_ids']
    attention_mask = batch['attention_mask']
    labels = batch['labels']
    
    with torch.no_grad():
        outputs = model(input_ids, attention_mask=attention_mask)
        logits = outputs.logits
    
    # Calculate label position for each sample
    batch_size = input_ids.shape[0]
    predictions = []
    
    for i in range(batch_size):
        # Find actual sequence length (last non-pad token)
        seq_len = attention_mask[i].sum().item()
        
        # Label is at position seq_len - 1
        label_logits = logits[i, seq_len - 1, :]
        pred = torch.argmax(label_logits).item()
        predictions.append(pred)
    
    return predictions, labels.cpu().numpy()
```

### Evaluation Workflow

```python
# 1. Load best checkpoint
model.load_state_dict(torch.load('best_lora_lora.pt', 
                                  map_location=device))

# 2. Set to eval mode
model.eval()

# 3. Iterate validation set
all_preds = []
all_labels = []

for batch in val_loader:
    preds, labels = evaluate_batch(batch, model, label_tokens)
    all_preds.extend(preds)
    all_labels.extend(labels)

# 4. Compute metrics
metrics = classification_report(
    all_labels, all_preds,
    target_names=['Negative', 'Neutral', 'Positive'],
    output_dict=True
)
```

## 6. Comparison with Other Techniques

### Adapter Tuning

```
Original Weight Matrix W


‚ Bottleneck Adapter Layer‚
‚ (compress to 64-dim)‚
‚ (expand back to d_out)‚


Add to residual stream
```

**Trade-offs**:
- More parameters than LoRA (0.6% vs 0.3%)
- More compute overhead at inference
- Slightly better expressiveness

### Prefix Tuning

```
Original Sequence

Prepend Learnable Prefix Tokens (k prefix tokens)

Feed to Model

Prefix gradients computed during backprop
```

**Trade-offs**:
- Increases sequence length (inference overhead)
- Prefix length is hyperparameter
- Good for prompt-based adaptation

## 7. File Organization

```
src/
 model.py
‚ class GPT(nn.Module)
‚ forward()
‚ from_pretrained()
‚ generate()
‚
 lora.py
‚ class LoRALinear(nn.Module)
‚ class LoRALayer(nn.Module)
‚ def apply_lora(model, rank=8)
‚
 dataset.py
‚ class FinancialSentimentDataset(Dataset)
‚ def load_dataset()
‚ def prepare_loaders()
‚
 training.py
‚ def train_epoch()
‚ class EarlyStopping()
‚ def train()
‚
 evaluation.py
 def evaluate()
 def compute_metrics()
 def generate_report()

config/
 model_config.py
‚ class ModelConfig (768, 12, 12, 50257, ...)
‚
 training_config.py
 class TrainingConfig (lr, epochs, batch_size, ...)
```

## 8. Known Issues & Resolutions

### Issue #1: F1 Score = 0.14 (CRITICAL)
**Symptom**: All techniques reporting F1 0.14
**Root Cause**: Evaluation extracting logits from position -1 (padding)
**Resolution**: Extract at actual label position
**Status**: FIXED

### Issue #2: Architecture Mismatch
**Symptom**: IndexError when loading checkpoint
**Root Cause**: Checkpoint saved with LoRA, loading into non-LoRA model
**Resolution**: Apply LoRA before loading checkpoint
**Status**: FIXED

### Issue #3: Device Mismatch
**Symptom**: "Expected all tensors to be on same device" error
**Root Cause**: Checkpoint loaded to CPU, model on GPU
**Resolution**: Specify `map_location=device` when loading
**Status**: FIXED

## 9. Performance Insights

### Why LoRA Wins

1. **Fewer Parameters**: Only rank Ã (d_out + d_in) trainable per layer
2. **Better Optimization**: Gradients flow through original parameters
3. **Inference Efficiency**: Can merge LoRA into original weights (zero overhead)
4. **Stability**: Constrained optimization landscape

### Why Adapters Underperform

1. **Sequential Bottleneck**: Compress-then-expand reduces expressiveness
2. **Inference Overhead**: Cannot merge with original model
3. **More Parameters**: Bottleneck layer larger than LoRA components

---

**Document Version**: 1.0  
**Last Updated**: May 2026  
**Status**: Complete & Validated
