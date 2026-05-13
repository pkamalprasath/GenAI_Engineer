# Small Language Models (SLM) Portfolio

A comprehensive collection of four independent ML projects demonstrating expertise in parameter efficiency, large-scale training, domain specialization, and foundational deep learning.

---

## Projects Overview

### 1. Finance_SLM_from_Scratch
Parameter-Efficient Fine-Tuning for Financial Sentiment Classification

- Result: 0.78 F1 with 0.3% trainable parameters (98.7% of full fine-tuning performance)
- Techniques: LoRA, Adapter Tuning, Prefix Tuning
- Key Achievement: 333x parameter reduction vs full fine-tuning
- Status: Production-ready
- [Project Details](./01_Finance_SLM_from_Scratch/)

### 2. GPT2_from_Scratch
Large-Scale Language Model Training Infrastructure

- Dataset: 10B tokens from FineWeb
- Model: 85M parameters with multi-GPU support
- Features: Streaming pipelines, checkpoint management, resumable training
- Benchmark: HellaSwag evaluation
- Status: Complete
- [Project Details](./02_GPT2_from_Scratch/)

### 3. BioGPT_from_Scratch
Domain-Specialized NLP Model for Biomedical Applications

- Application: Biomedical entity recognition and relation extraction
- Specialization: Domain vocabulary expansion, fine-tuning on PubMed abstracts
- Results: 88% F1 on biomedical NER (vs 68% with general model)
- Status: Complete
- [Project Details](./03_BioGPT_from_Scratch/)

### 4. Build_SLM_from_Scratch
Transformer Implementation from First Principles

- Implementation: BPE tokenizer, multi-head self-attention, feed-forward networks
- Variants: 2M, 10M, 50M parameter models
- Approach: No high-level abstractions, pure mathematical foundations
- Purpose: Deep understanding of transformer internals
- Status: Complete
- [Project Details](./04_Build_SLM_from_Scratch/)

---

## Skills Demonstrated

**Algorithm Implementation**
- LoRA (Low-Rank Adaptation) mathematical formulation and implementation
- Multi-head self-attention mechanisms
- Residual connections and layer normalization

**Large-Scale Training**
- Data pipeline design for billion-token datasets
- Distributed training infrastructure
- Checkpoint management and resumable training
- Gradient accumulation and optimization strategies

**Production Engineering**
- Modular code architecture with type hints
- Configuration management without hardcoding
- Comprehensive error handling
- Professional documentation

**Experimental Design**
- Fair comparison frameworks with proper baselines
- Multiple implementation approaches for evaluation
- Proper validation and benchmark selection

---

## Technical Stack

- PyTorch 2.0+
- HuggingFace Transformers and Datasets
- scikit-learn for evaluation metrics
- CUDA for GPU acceleration

---

## Getting Started

Each project is independent with its own setup:

```bash
cd [project_folder]
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Detailed setup instructions in each project's README.

---

## Project Structure

```
project_folder/
 README.md - Project overview
 ARCHITECTURE.md - Technical design details
 requirements.txt - Dependencies with pinned versions
 
 src/ - Source code modules
 config/ - Configuration classes
 scripts/ - Entry points (train, evaluate)
 notebooks/ - Jupyter experiments (optional)
```

---

## Documentation

Each project includes:
- README.md: Overview and quick start
- ARCHITECTURE.md: Technical design and implementation
- Type hints throughout source code
- Professional documentation

For detailed portfolio overview: [README_PORTFOLIO.md](./README_PORTFOLIO.md)

---


## Quality Assurance

- Type hints: 100% coverage
- Error handling: Comprehensive with recovery strategies
- Documentation: Professional README and ARCHITECTURE files
- Code organization: Modular with clear separation of concerns
- Reproducibility: Configuration-driven, no hardcoding

---

## License

MIT License - See individual project LICENSE files

---

Last Updated: May 2026
