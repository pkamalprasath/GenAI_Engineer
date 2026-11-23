# Small language model training notebooks

Four PyTorch projects on training small GPT-style language models. Notebook outputs are kept as evidence of what ran. Three of the four follow published code or guided tutorials, and each README says which.

## Built from scratch

- **LoRA written from scratch in PyTorch (no PEFT):** a hand-written `LoRALinear` module that wraps a frozen `nn.Linear` with rank and alpha, plus `merge()` in [`01_finance_gpt_lora/src/lora.py`](./01_finance_gpt_lora/src/lora.py). This claim covers the LoRA code only; the fine-tuning results in that project are under review (see below).

Nothing else in this folder is claimed as from scratch.

## Projects

### 1. [01_finance_gpt_lora](./01_finance_gpt_lora/)
A 63.8M-parameter GPT with LoRA written from scratch, for three-class financial sentiment.

- Pretraining was **not completed**: the run was interrupted after a few of 20,000 iterations and no loss was logged.
- LoRA evaluation on the validation split: F1 micro 0.656, F1 macro 0.264. The model predicts `neutral` for every example, and fine-tuning losses near zero suggest label leakage (suspected; under review).

### 2. [02_gpt2_124m_nanogpt_reimplementation](./02_gpt2_124m_nanogpt_reimplementation/)
GPT-2 124M pretraining on FineWeb-Edu, following Andrej Karpathy's [build-nanoGPT](https://github.com/karpathy/build-nanogpt).

- 8 GPUs with PyTorch DistributedDataParallel (`torchrun`), 524,288-token batches, flash attention
- A 2,000-step run of about 15 minutes: validation loss 3.6720, HellaSwag 26.0%; about 1.27M tokens/sec on normal steps

### 3. [03_biogpt_style_27m](./03_biogpt_style_27m/)
A 27M-parameter BioGPT-style model pretrained on PubMed abstracts with the BioGPT vocabulary (guided work).

- Validation loss 3.47 after 120,000 iterations
- Soft-prompt fine-tuning on HoC (cancer hallmarks): macro F1 0.42, up from 0.003

### 4. [04_tinystories_slm](./04_tinystories_slm/)
A GPT of about 30M parameters (6 layers, 6 heads, 384-dim) pretrained on TinyStories (guided work; training code adapted from nanoGPT).

- Validation loss 2.40 after 20,000 iterations; generates short stories

## Stack

PyTorch 2.x, Hugging Face Datasets and Transformers, tiktoken, scikit-learn (metrics), CUDA.

## Getting started

Each project is independent:

```bash
cd <project_folder>
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Where the code is

| Project | Code |
|---|---|
| 01_finance_gpt_lora | `src/` (model, LoRA, dataset, training, evaluation), `scripts/`, `config/`, plus the notebook run |
| 02_gpt2_124m_nanogpt_reimplementation | `src/` (training loop, FineWeb loader, HellaSwag, inference; adapted from build-nanoGPT), `train_gpt2_runpod.py`, plus the notebook run |
| 03_biogpt_style_27m | `notebooks/` (all code, with outputs) |
| 04_tinystories_slm | `notebooks/` (all code, with outputs) |

## License

MIT; see the LICENSE file in each project.
