# Finance SLM: Pretraining and Parameter-Efficient Fine-Tuning for Financial Sentiment

A GPT-style decoder written from scratch in PyTorch, pretrained on financial text, then fine-tuned for three-class financial sentiment (bearish, bullish, neutral) with several methods: LoRA (implemented from scratch in `src/lora.py`), adapter tuning, prefix tuning, simulated QLoRA, and full fine-tuning. The full run, with outputs, is in `notebooks/01_Finance_SLM_Training_Evaluation.ipynb`.

## Use Case
- **Dataset**: [zeroshot/twitter-financial-news-sentiment](https://huggingface.co/datasets/zeroshot/twitter-financial-news-sentiment) (9,543 train / 2,388 validation examples loaded)
- **Classes**: Bearish, Bullish, Neutral
- **Model in the notebook run**: 63.8M-parameter decoder (A100 40 GB, Google Colab)

## Measured Results (from the notebook outputs)

| Stage | What was measured |
|---|---|
| Pretraining on financial text | 20,000 iterations, final validation loss 2.20 (random-guess baseline 10.82) |
| LoRA | 540,672 trainable parameters (0.84%) |
| Adapter tuning | 25,600 trainable parameters (0.04%) |
| Prefix tuning | 12,633,088 trainable parameters (19.8%) |
| Full fine-tuning | 63,823,360 trainable parameters (100%) |

**Open issue:** every fine-tuning method reaches a validation loss of about 0.0000 within one or two epochs. On a noisy three-class sentiment task that almost always means the label is leaking into the model's input, so these runs cannot be used to compare methods yet. The notebook also never computes F1 or accuracy on held-out data. Next steps: check the prompt and target construction for leakage, then report macro-F1 per method on the validation split.

## Technical Approach

### 1. Data Pipeline
- **Source**: HuggingFace Datasets (`zeroshot/twitter-financial-news-sentiment`)
- **Preprocessing**:
  - Sentence tokenization
  - Prompt template: `"Sentiment: {text}. Answer: "`
  - Label token extraction at position 0 (negative), 2430 (neutral), 3231 (positive)
- **Split**: 9,543 train / 2,388 validation (as loaded in the notebook run)

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
