# Finance SLM: Parameter-Efficient Fine-Tuning for Financial Sentiment Classification

A comprehensive implementation of parameter-efficient fine-tuning techniques applied to a GPT-2 style language model for financial sentiment classification. This project demonstrates Low-Rank Adaptation (LoRA), Adapter tuning, and Prefix tuning approaches, achieving competitive results while minimizing trainable parameters.

## Problem Statement

Large language models (LLMs) are computationally expensive to fine-tune. Traditional full fine-tuning requires updating all model parameters, which is impractical for resource-constrained environments. This project explores **parameter-efficient fine-tuning** techniques that achieve comparable performance while training only 0.3-0.6% of model parameters.

### Use Case
- **Domain**: Financial sentiment classification
- **Dataset**: Twitter Financial News Sentiment (11,932 examples)
- **Classes**: Negative, Neutral, Positive
- **Model**: GPT-2 style decoder-only transformer (85M parameters)

## Results Summary

| Technique | F1 Score | Trainable Params | Training Time |
|-----------|----------|-----------------|---------------|
| LoRA | 0.78 | 0.3% | ~45 min |
| Adapter Tuning | 0.74 | 0.6% | ~50 min |
| Prefix Tuning | 0.71 | 0.5% | ~48 min |
| Full Fine-Tuning | 0.79 | 100% | ~180 min |

**Key Insight**: LoRA achieves 98.7% of full fine-tuning performance while reducing trainable parameters by 333x.

## Technical Approach

### 1. Data Pipeline
- **Source**: HuggingFace Datasets (`zeroshot/twitter-financial-news-sentiment`)
- **Preprocessing**:
  - Sentence tokenization
  - Prompt template: `"Sentiment: {text}. Answer: "`
  - Label token extraction at position 0 (negative), 2430 (neutral), 3231 (positive)
- **Split**: 80% train (9,938), 20% validation (2,486)

### 2. Model Architecture
- **Base**: GPT-2 style decoder-only transformer
- **Layers**: 12 hidden layers, 12 attention heads
- **Hidden Size**: 768 dimensions
- **Vocabulary**: 50,257 tokens

### 3. LoRA Implementation
```
For each attention layer:
  ŒW = BA  (Low-rank decomposition)
  W_new = W_original + Œ±ŒW
  
  where:
  - W: weight matrix (d_out √ d_in)
  - B: (d_out √ rank)
  - A: (rank √ d_in)
  - rank: 8 (0.3% of parameters)
  - Œ±: 16.0 (scaling factor)
```

### 4. Training Configuration
- **Optimizer**: AdamW
- **Learning Rate**: 5e-5
- **Batch Size**: 32
- **Epochs**: 3
- **Early Stopping**: Patience = 2 (validation F1 monitor)
- **Device**: GPU (CUDA)

##Å Project Structure

```
finance-slm-fine-tuning/
 README.md This file
 ARCHITECTURE.md Technical design details
 LICENSE MIT License
 .gitignore Git ignore rules
 requirements.txt Dependencies
Ç
 notebooks/
Ç 01_Finance_SLM_Training_Evaluation.ipynb Main notebook
Ç
 src/
Ç __init__.py
Ç model.py GPT class definition
Ç lora.py LoRA implementation
Ç dataset.py Dataset class
Ç training.py Training loop
Ç evaluation.py Evaluation metrics
Ç
 config/
Ç __init__.py
Ç model_config.py Model hyperparameters
Ç training_config.py Training hyperparameters
Ç
 scripts/
Ç __init__.py
Ç train.py Training entry point
Ç evaluate.py Evaluation entry point
Ç
 docs/
 ARCHITECTURE.md System design
 DEPLOYMENT.md Deployment guide
 CONTRIBUTING.md Contribution guidelines
```

## Quick Start

### 1. Environment Setup
```bash
# Clone repository
git clone https://github.com/pkamalprasath/finance-slm-fine-tuning.git
cd finance-slm-fine-tuning

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -r requirements.txt
```

### 2. Run in Jupyter Notebook
```bash
jupyter notebook notebooks/01_Finance_SLM_Training_Evaluation.ipynb
```

Follow the notebook cells in order:
1. **Setup**: Load dependencies, configure GPU
2. **Data**: Download and prepare HuggingFace dataset
3. **Model**: Initialize GPT-2 and apply LoRA
4. **Training**: Fine-tune with early stopping
5. **Evaluation**: Compute F1, precision, recall metrics
6. **Comparison**: Benchmark LoRA vs baselines

### 3. Training from Command Line
```bash
python scripts/train.py \
    --technique lora \
    --epochs 3 \
    --batch_size 32 \
    --learning_rate 5e-5
```

### 4. Evaluation
```bash
python scripts/evaluate.py \
    --checkpoint best_lora_lora.pt \
    --technique lora
```

## Key Implementation Details

### LoRA Fine-Tuning
- Applies to query and value projections in attention layers
- Rank: 8 (balance between expressiveness and efficiency)
- Initialization: A ~ N(0, 1), B ~ 0
- Scaling: Œ± = 2 √ rank = 16.0

### Early Stopping Strategy
- Monitor: Validation F1 score
- Patience: 2 epochs
- Restore: Best weights after training

### Label Token Extraction
```python
# Critical for evaluation accuracy
label_position = len(prompt_tokens) + len(sentence_tokens)
logits = logits[0, label_position, :]  # Extract at label position
predicted_class = torch.argmax(logits)  # Predict class
```

## Performance Analysis

### F1 Score Breakdown by Class
- **Negative**: 0.76
- **Neutral**: 0.81 (best performance)
- **Positive**: 0.75

### Why LoRA Outperforms Adapters
1. **Parameter Efficiency**: Adapters use dense bottleneck layers (less efficient)
2. **Gradient Flow**: LoRA maintains original parameter gradients (better optimization)
3. **Inference Speed**: LoRA can merge weights into original model (no overhead)

## Bug Fixes & Lessons Learned

### 1. Logits Extraction Bug (CRITICAL)
**Problem**: Evaluation extracted logits from position -1 instead of label position
**Impact**: F1 appeared as 0.14 across all techniques
**Fix**: Extract logits at `label_position = len(sentence_tokens) + len(prompt_tokens)`
**Lesson**: Always validate evaluation logic before benchmark comparisons

### 2. Model Architecture Mismatch
**Problem**: Loading checkpoint to model without LoRA applied first
**Fix**: Apply LoRA architecture before loading checkpoint state_dict
**Code**: `model = apply_lora(model)` before `model.load_state_dict(...)`

### 3. Device Mismatch (CPU/GPU)
**Problem**: Checkpoint loaded to CPU, tensors on GPU during inference
**Fix**: Load checkpoint directly to target device with `map_location=device`
**Code**: Include `model.to(device)` after loading weights

## Dependencies

### Core
- **torch**: Deep learning framework
- **transformers**: HuggingFace model hub
- **datasets**: HuggingFace datasets

### Utilities
- **scikit-learn**: Metrics computation (F1, precision, recall)
- **pandas**: Data manipulation
- **tqdm**: Progress bars
- **matplotlib/seaborn**: Visualization

See `requirements.txt` for pinned versions.

##§ Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Follow the code style (black, pylint)
4. Add tests for new functionality
5. Submit a pull request

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for detailed guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Academic Inspiration

- **LoRA Paper**: [LoRA: Low-Rank Adaptation of Large Language Models](https://arxiv.org/abs/2106.09685)
- **Parameter-Efficient Methods**: [Comparative Study of Parameter-Efficient Transfer Learning for NLP](https://arxiv.org/abs/2104.08691)
- **GPT-2**: [Language Models are Unsupervised Multitask Learners](https://d4mucfpksywv.cloudfront.net/better-language-models/language_models_are_unsupervised_multitask_learners.pdf)

## Future Enhancements

- [ ] Add quantization (int8, fp16)
- [ ] Implement distributed training
- [ ] Add more parameter-efficient techniques (QLoRA, DoRA)
- [ ] Benchmark on other financial datasets
- [ ] Deploy as REST API

---

**Author**: Kamal Prasath  
**Last Updated**: May 2026  
**Status**: Ready for Production
