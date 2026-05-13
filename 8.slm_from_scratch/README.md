# Small Language Models (SLM) Portfolio

**A comprehensive exploration of modern AI/ML engineering through production-grade projects**

---

## Quick Overview

This portfolio contains **4 complete, independent projects** demonstrating expertise in:
- Parameter-efficient fine-tuning (LoRA)
- Large-scale model training
- Domain specialization & transfer learning
- Foundational ML architecture understanding

**For detailed overview: Read [README_PORTFOLIO.md](./README_PORTFOLIO.md)**

---

## The 4 Projects

### 1. **Finance_SLM_from_Scratch** [START HERE]
**Parameter-Efficient Fine-Tuning for Financial Sentiment Classification**

- **Achievement**: 0.78 F1 with only 0.3% trainable parameters
- **Techniques**: LoRA, Adapter Tuning, Prefix Tuning comparison
- **Status**: Production-ready
- **[Explore Project](./01_Finance_SLM_from_Scratch/)**

```
Comparison: LoRA (0.78 F1) vs Full Fine-Tuning (0.79 F1)
Using 333x fewer parameters!
```

---

### 2. **GPT2_from_Scratch**
**Training Language Models from Scratch at Scale**

- **Achievement**: Full training pipeline with 10B token FineWeb dataset
- **Features**: Multi-GPU support, HellaSwag evaluation, resumable training
- **Status**: Complete
- **[Explore Project](./02_GPT2_from_Scratch/)**

```
Infrastructure: Streaming data pipelines + checkpoint management
Scale: 85M parameter model training
```

---

### 3. **BioGPT_from_Scratch**
**Domain-Specific Language Model for Biomedical NLP**

- **Achievement**: Specialized model for scientific literature analysis
- **Features**: Entity recognition, biomedical vocabulary, transfer learning
- **Status**: Complete
- **[Explore Project](./03_BioGPT_from_Scratch/)**

```
Application: Clinical documentation, drug discovery, literature analysis
Specialization: Real-world biomedical NLP challenges
```

---

### 4. **Build_SLM_from_Scratch**
**Transformers From First Principles (Educational Deep-Dive)**

- **Achievement**: Complete SLM implementation without high-level abstractions
- **Features**: Custom BPE tokenizer, attention from scratch, multiple scales
- **Status**: Complete
- **[Explore Project](./04_Build_SLM_from_Scratch/)**

```
Purpose: Deep understanding of transformer internals
Variants: 2M, 10M, 50M parameter models
```

---

## Key Skills Demonstrated

### 1. Algorithm Implementation
- LoRA (Low-Rank Adaptation) mathematical formulation
- Multi-head self-attention from first principles
- Feed-forward networks and residual connections

### 2. Large-Scale Training
- Data pipelines (streaming, chunking, batching)
- Distributed training infrastructure
- Checkpointing and resumable training
- Gradient accumulation and optimization

### 3. Production Engineering
- Modular, type-hinted Python code
- Configuration management (not hardcoding)
- Comprehensive error handling
- Professional documentation

### 4. Experimental Design
- Fair comparison framework
- Multiple baseline implementations
- Proper evaluation metrics
- Bug detection and fixing

### 5. Deep Learning Concepts
- Transformer architecture internals
- Parameter efficiency techniques
- Transfer learning strategies
- Domain adaptation approaches

---

## Technical Achievements

| Project | Focus | Key Result | Status |
|---------|-------|-----------|--------|
| **Finance_SLM** | Parameter efficiency | 0.78 F1 (0.3% trainable) | Ready |
| **GPT2** | Training at scale | 10B token dataset | Complete |
| **BioGPT** | Domain specialization | Biomedical NLP | Complete |
| **Build_SLM** | From-scratch learning | Custom tokenizer + transformers | Complete |

---

## Get Started

### Option 1: Start with Finance_SLM (Recommended)
```bash
cd 01_Finance_SLM_from_Scratch
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Run training
python scripts/train.py --epochs 3 --batch_size 32

# Evaluate
python scripts/evaluate.py --checkpoint best_model.pt
```

### Option 2: Explore Project Structure
```bash
# Each project has the same professional structure:
each_project/
 notebooks/          # Jupyter notebooks
 src/               # Python modules
 config/            # Configuration classes
 scripts/           # Entry points
 docs/              # Documentation
 README.md          # Project overview
 ARCHITECTURE.md    # Technical design
 requirements.txt   # Dependencies
```

### Option 3: Read Documentation
- **Portfolio Overview**: [README_PORTFOLIO.md](./README_PORTFOLIO.md)
- **Project 1 Details**: [Finance_SLM README](./01_Finance_SLM_from_Scratch/README.md)
- **Project 1 Architecture**: [Finance_SLM ARCHITECTURE](./01_Finance_SLM_from_Scratch/ARCHITECTURE.md)

---

## Quick Insights

### Why Finance_SLM Matters
```
Problem: Fine-tune models costs billions in compute
Solution: Use LoRA (0.3% trainable params)
Result: Same performance, 333x fewer parameters! 
```

### Why GPT2_from_Scratch Matters
```
Problem: Training LLMs requires understanding data pipelines
Solution: Build full pipeline from FineWeb data
Result: Production-grade training infrastructure
```

### Why BioGPT Matters
```
Problem: General models don't work well on specialized domains
Solution: Domain-specific vocabulary + fine-tuning
Result: Biomedical NLP specialized model
```

### Why Build_SLM Matters
```
Problem: Deep understanding hidden behind frameworks
Solution: Implement everything from first principles
Result: Unshakeable fundamentals
```

---

## Portfolio Strengths

- **Breadth**: 4 different projects covering different aspects  
- **Depth**: Each project explores techniques thoroughly  
- **Quality**: Production-grade code and documentation  
- **Communication**: Clear, well-written architecture docs  
- **Learning**: Shows growth from theory to practice  
- **Reproducibility**: Version control, configs, requirements  
- **Problem-Solving**: Includes debugging complex issues  

---

## Project Progression

```
Theory Practice Scale Specialization

Build_SLM  Finance   GPT2     BioGPT
(from      (efficient (large   (domain
scratch)   fine-tune) scale)   adapt)
```

Each project builds on knowledge from previous projects.

---

## For Hiring Managers

### What This Shows

| Dimension | Evidence |
|-----------|----------|
| Technical Depth | Implemented LoRA, transformers, training loops |
| Problem-Solving | Found/fixed critical bugs, designed experiments |
| Production Mindset | Modular code, config, docs, error handling |
| Learning Agility | 4 projects with different focuses |
| Communication | Professional code + comprehensive documentation |

### Time to Review
- **Quick scan**: 15-20 minutes (skim READMEs)
- **Code review**: 1-2 hours (read architecture + code)
- **Deep dive**: 2-3 hours (run projects, understand fully)

---

## Navigation

### For Different Audiences

**Decision Makers / HR**
 Read this README + [README_PORTFOLIO.md](./README_PORTFOLIO.md) (20 min)

**Technical Reviewers**
 Read all ARCHITECTURE.md files + review src/ (1-2 hours)

**ML Researchers**
 Run projects locally + understand algorithms (2-3 hours)

**DevOps / Infrastructure Engineers**
 Check deployment docs + training pipelines (1 hour)

---

## Project READMEs

1. [Finance_SLM_from_Scratch](./01_Finance_SLM_from_Scratch/README.md)
2. [GPT2_from_Scratch](./02_GPT2_from_Scratch/README.md)
3. [BioGPT_from_Scratch](./03_BioGPT_from_Scratch/README.md)
4. [Build_SLM_from_Scratch](./04_Build_SLM_from_Scratch/README.md)

---

## Key Technologies

- **Deep Learning**: PyTorch 2.0+
- **NLP**: Transformers, Datasets, Tokenizers
- **Evaluation**: scikit-learn, scipy
- **Tools**: Git, Jupyter, VS Code
- **Infrastructure**: CUDA, GPU acceleration

---

## Questions?

Each project has detailed documentation:
- **README.md** - Project overview and quick start
- **ARCHITECTURE.md** - Technical design and implementation details
- **DEPLOYMENT.md** - Production deployment guide
- **CONTRIBUTING.md** - Development guidelines

---

## License

All projects are licensed under MIT License. See individual project LICENSE files.

---

## Summary

This portfolio demonstrates that I'm a **complete ML engineer**:
- Can understand and implement cutting-edge techniques (LoRA)
- Can build production-grade systems (training infrastructure)
- Can solve real-world problems (biomedical NLP)
- Can communicate complex ideas clearly (documentation)
- Can learn deeply and continuously (4 different projects)

**Ready to contribute to teams that value both theoretical understanding and practical engineering excellence.**

---

**Last Updated**: May 2026  
**Portfolio Status**: Complete & Professional  

**[Start with Finance_SLM](./01_Finance_SLM_from_Scratch/)** or **[Read Detailed Overview](./README_PORTFOLIO.md)**
