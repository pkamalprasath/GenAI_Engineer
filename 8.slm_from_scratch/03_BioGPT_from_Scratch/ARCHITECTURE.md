# Architecture: BioGPT Domain-Specific Language Model

## System Overview

```
BioMedical Corpus (PubMed abstracts + papers)

Preprocessing (Entity recognition, tokenization)

GPT-2 Base Model (pretrained)

Domain Fine-Tuning Loop
 Forward pass
 Language modeling loss
 Domain-specific metrics
 Parameter updates

Evaluation (Perplexity + BioNER F1)

Production Deployment
```

## Model Architecture

### Base Model: GPT-2

```
Embedding Dim       | 768
Num Heads           | 12
Num Layers          | 12
FFN Hidden          | 3072
Vocabulary Size     | 50,257 (+ biomedical tokens)
Context Window      | 1024 tokens
Total Parameters    | 85M
Fine-tuning Params  | 5-10% (task-specific)
```

### Domain-Specific Enhancements

**Vocabulary Expansion**
```
Original GPT-2 Vocab: 50,257 tokens
Biomedical Tokens:    5,000+ specialized terms
 Drug names (e.g., "aspirin", "ibuprofen")
 Protein codes (e.g., "TP53", "BRCA1")
 Chemical compounds (e.g., "C6H12O6")
 Disease terms (ICD codes)
 Medical procedures
```

**Embedding Initialization**
```
New biomedical tokens:
 Random initialization from N(0, 0.02)
 Or: averaged embeddings from similar tokens
 Refined during fine-tuning
```

## Data Pipeline

### Biomedical Corpus Preparation

```
PubMed Abstracts (30M+)

Text Cleaning
 Remove XML tags
 Normalize whitespace
 Filter invalid entries

Entity Recognition (Named Entity Recognition)
 Identify drug names
 Identify protein/gene names
 Identify disease mentions
 Identify medical procedures

Tokenization (GPT-2 BPE + biomedical)

Chunk into sequences (max_length=512)

Create PyTorch Dataset
```

### Entity-Aware Processing

```python
# Example: Mark biomedical entities
Original:  "The protein TP53 regulates apoptosis"
Entities:  "The protein [PROTEIN:TP53] regulates [PROCESS:apoptosis]"
Tokens:    ["The", "protein", "[PROTEIN:TP53]", "regulates", "[PROCESS:apoptosis]"]
```

## Fine-Tuning Strategy

### Transfer Learning Approach

```
1. Start with pretrained GPT-2
 Already knows language structure
   
2. Fine-tune on biomedical domain
 Low learning rate (1e-5 to 5e-5)
 Fewer epochs (3-5)
 Focus on domain vocabulary
   
3. Evaluation on biomedical benchmarks
 Perplexity on PubMed text
 Named entity recognition F1
 Domain-specific QA tasks
```

### Training Configuration

```
Learning Rate:       5e-5 (lower than pretraining)
Batch Size:         16-32
Epochs:             3-5
Weight Decay:       0.01
Warmup Steps:       500
Total Steps:        10,000-20,000
Checkpoint Interval: 1,000 steps
```

### Early Stopping Criteria

```
Monitor: Validation Perplexity
Patience: 2 epochs
Restore: Best checkpoint
```

## Evaluation Metrics

### Perplexity on Biomedical Text

```
Perplexity = exp(average_negative_log_likelihood)

Lower perplexity Better understanding of domain language
Expected range: 15-25 (depends on domain text complexity)
```

### Biomedical Named Entity Recognition (BioNER)

```
Task: Identify and classify medical entities
 Proteins: [PROTEIN] TP53, BRCA1
 Genes: [GENE] TP53, EGFR
 Diseases: [DISEASE] cancer, diabetes
 Drugs: [DRUG] aspirin, metformin

Evaluation: Precision, Recall, F1 score
```

### Domain-Specific QA

```
Question: "What is the treatment for hypertension?"
Expected: Model generates medically accurate completions
Evaluation: Human review of response quality
```

## Model Fine-Tuning Layers

### Selective Layer Freezing

```
Option 1: Fine-tune all layers
 More computationally expensive
 Better adaptation (if sufficient data)

Option 2: Fine-tune upper layers only
 Faster training
 Lower compute requirements
 Preserves lower-level linguistic knowledge

Option 3: LoRA adaptation (recommended)
 Add low-rank matrices to attention
 Minimal parameter overhead
 Better efficiency
```

### Recommended: LoRA for BioGPT

```python
# Apply LoRA to attention layers
model = apply_lora(
    model,
    rank=8,
    alpha=16.0,
    target_modules=['q_proj', 'v_proj']
)

# Only 0.3% additional parameters
# Maintains domain knowledge from pretraining
```

## Biomedical-Specific Features

### Domain Vocabulary Handling

```
Initialization options:
1. WordPiece subword tokenization for compounds
   "N-acetyl-L-cysteine" ["N", "-", "acetyl", "-", "L", "-", "cysteine"]
   
2. Entity type tokens
   [PROTEIN], [GENE], [DRUG], [DISEASE]
   
3. Citation tokens
   [CITE], [PUB], [DOI]
```

### Context Preservation

```
Clinical context tokens:
[PATIENT] [HOSPITAL] [PROCEDURE] [OUTCOME]

Example:
"[PATIENT] 65-year-old male [HOSPITAL] ICU [PROCEDURE] 
ventilation [OUTCOME] improved"
```

## Inference Applications

### 1. Literature Analysis

```
Task: Summarize biomedical abstracts
Input: Full PubMed abstract
Output: Concise summary highlighting key findings
```

### 2. Medical Report Generation

```
Task: Assist in clinical documentation
Input: Patient symptoms and test results
Output: Structured medical report
```

### 3. Drug-Target Extraction

```
Task: Identify drug-protein interactions
Input: "Aspirin binds to COX-1 and COX-2 proteins"
Output: 
 Drug: Aspirin
 Targets: [COX-1, COX-2]
 Interaction: Binding
```

## Performance Considerations

### Inference Optimization

```
Method 1: Model Compression
 Quantization (INT8)
 Pruning (remove non-critical weights)
 Distillation (smaller student model)

Method 2: Caching
 Cache KV pairs for faster generation
 Batch inference for throughput
```

### Computational Requirements

```
Fine-tuning:
 GPU Memory: 12GB (batch_size=16)
 Training Time: 2-4 hours (10K steps)
 Checkpoint Size: 340MB

Inference:
 GPU Memory: 6GB (generation)
 Latency: ~100ms per token
 Throughput: 10 tokens/second
```

## File Organization

```
src/
 model.py BioGPT model definition
 dataset.py Biomedical data handling
 training.py Fine-tuning loop
 evaluation.py Domain metrics
 biomed_utils.py Entity recognition, processing

config/
 model_config.py Model architecture
 training_config.py Fine-tuning hyperparameters

scripts/
 train.py Training entry point
 evaluate.py Evaluation entry point
 generate.py Text generation & inference

docs/
 DOMAIN_GUIDE.md Biomedical NLP guide
```

---

**Status**: Production-Ready  
**Last Updated**: May 2026
