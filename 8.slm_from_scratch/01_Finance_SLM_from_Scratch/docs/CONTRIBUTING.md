# Contributing Guidelines

Thank you for your interest in contributing to the Finance SLM project! This guide will help you get started.

## Development Setup

### 1. Clone the Repository
```bash
git clone https://github.com/pkamalprasath/finance-slm-fine-tuning.git
cd finance-slm-fine-tuning
```

### 2. Create Virtual Environment
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/macOS
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
pip install -e .  # Install in editable mode
```

## Development Workflow

### Making Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Follow the code style (see Code Style section)
   - Add tests for new functionality
   - Update documentation

3. **Test your changes**
   ```bash
   # Run tests
   pytest tests/
   
   # Code quality
   black src/
   pylint src/
   mypy src/
   ```

4. **Commit your changes**
   ```bash
   git commit -m "feat: add your feature description"
   ```

5. **Push and create a Pull Request**
   ```bash
   git push origin feature/your-feature-name
   ```

## Code Style

### Python Style Guide
- Follow PEP 8
- Use type hints
- Maximum line length: 88 characters

### Formatting
```bash
# Auto-format with black
black src/ config/ scripts/

# Check with pylint
pylint src/ --disable=all --enable=convention

# Type checking
mypy src/ --ignore-missing-imports
```

### Documentation
- Add docstrings to all public functions
- Use Google-style docstrings
- Include type hints in function signatures

```python
def train_model(
    model: nn.Module,
    dataset: DataLoader,
    epochs: int = 3,
) -> Dict[str, float]:
    """
    Train the model.
    
    Args:
        model: The model to train
        dataset: Training dataset loader
        epochs: Number of training epochs
        
    Returns:
        Dictionary with training metrics
    """
```

## Adding New Features

### Parameter-Efficient Techniques
To add a new parameter-efficient technique:

1. **Create new module** in `src/`
   ```python
   # src/adapter.py (example)
   class AdapterLayer(nn.Module):
       def __init__(self, ...):
           ...
   
   def apply_adapter(model, ...):
       ...
   ```

2. **Add to training config**
   ```python
   # config/training_config.py
   use_adapter = True
   adapter_dim = 64
   ```

3. **Update training script**
   ```python
   # scripts/train.py
   elif args.technique == 'adapter':
       model = apply_adapter(model, ...)
   ```

4. **Add evaluation**
   - Run evaluation on validation set
   - Compare with baselines
   - Document results

### Bug Fixes
1. **Create an issue** describing the bug
2. **Create a branch** with bug name: `bugfix/description`
3. **Add test case** that reproduces the bug
4. **Fix the code**
5. **Verify test passes**
6. **Submit PR** with reference to issue

### Documentation Updates
- Update README.md for user-facing changes
- Update ARCHITECTURE.md for design changes
- Update docs/ for operational guides
- Keep examples current

## Testing

### Unit Tests
```python
# tests/test_lora.py
import pytest
from src.lora import apply_lora

def test_lora_apply():
    model = GPT(config)
    model = apply_lora(model)
    assert hasattr(model, 'lora_modules')
    assert len(model.lora_modules) > 0
```

### Integration Tests
```python
def test_training_loop():
    # Full training cycle
    dataset = load_hf_dataset()
    train_loader, val_loader = prepare_dataset(dataset, tokenizer)
    
    model = GPT(config)
    model = apply_lora(model)
    
    history = train(
        model, train_loader, val_loader,
        num_epochs=1, checkpoint_path='test_model.pt'
    )
    
    assert 'train_loss' in history
    assert len(history['train_loss']) == 1
```

### Running Tests
```bash
pytest tests/ -v
pytest tests/ --cov=src/  # Coverage report
```

## Performance Benchmarking

When submitting changes that affect performance:

1. **Benchmark baseline**
   ```python
   import time
   start = time.time()
   # code
   elapsed = time.time() - start
   ```

2. **Document results**
   - Training time
   - Inference latency
   - Memory usage
   - F1 score

3. **Submit with PR**
   - Include benchmarks in PR description
   - Compare with baseline
   - Explain any regressions

## Pull Request Process

1. **Before submitting:**
   - [ ] Code follows style guide
   - [ ] Tests pass: `pytest tests/`
   - [ ] Code is formatted: `black src/`
   - [ ] Type checking passes: `mypy src/`
   - [ ] Documentation updated

2. **PR Description should include:**
   - Description of changes
   - Motivation and context
   - Testing done
   - Benchmark results (if applicable)
   - Screenshots (for visualization changes)

3. **Review Process:**
   - At least 1 maintainer review required
   - All conversations resolved
   - CI/CD checks pass

## Report Issues

### Bug Reports
Include:
- Python version
- PyTorch version
- Steps to reproduce
- Expected vs actual behavior
- Error messages/traceback

### Feature Requests
Include:
- Motivation and use case
- Proposed solution
- Alternative approaches
- Example usage

## Questions?

- **Documentation**: See README.md and docs/
- **Issues**: Open a GitHub issue
- **Discussions**: Use GitHub discussions

## Code of Conduct

- Be respectful and inclusive
- Assume good intent
- Give constructive feedback
- Help others learn

---

**Thank you for contributing!**

---

**Last Updated**: May 2026  
**Maintained By**: Kamal Prasath
