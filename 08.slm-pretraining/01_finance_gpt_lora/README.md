# Finance GPT with LoRA written from scratch

A small GPT-style decoder in PyTorch, fine-tuned for three-class financial sentiment (negative, neutral, positive) with **LoRA written from scratch** (a hand-written `LoRALinear` module, no PEFT library). The notebook also tries adapter-style tuning, prefix tuning, simulated QLoRA and full fine-tuning. The run, with outputs, is in `notebooks/01_Finance_SLM_Training_Evaluation.ipynb`.

## Status

This is unfinished work. Read the results below with that in mind.

- **Pretraining was not completed.** The pretraining cell was interrupted after a few iterations (the progress bar shows 0–11 of 20,000) and no validation loss was recorded. Fine-tuning therefore started from an almost untrained model.
- **Fine-tuning results are not usable yet.** Every method reaches a fine-tuning validation loss of about 0.0000 within one to three epochs. On a noisy three-class task this points to label leakage in the prompt/target construction (suspected; under review).
- An earlier version of the notebook generated a synthetic pretraining loss curve and a "final validation loss 2.20" from a hard-coded default. Both have been removed; they were not measurements.

## What was measured (from the notebook outputs)

| Item | Value |
|---|---|
| Model in the notebook run | 63,823,360 parameters (12 layers, 8 heads, 512-dim, 512-token context) |
| Pretraining corpus prepared | IMDB reviews + AG News: 194,998 documents, 28,965,885 GPT-2 tokens (not finance-specific) |
| Pretraining | Interrupted at 0–11 of 20,000 iterations; no loss logged |
| Fine-tuning data | `zeroshot/twitter-financial-news-sentiment`: 9,543 train / 2,388 validation examples as loaded |
| LoRA (rank 8, alpha 16, on `c_attn` and `c_proj`) | 540,672 trainable parameters (0.84%) |
| Adapter-style run (layer norms and final layers) | 25,600 trainable parameters (0.04%) |
| Prefix tuning | 12,633,088 trainable parameters (19.8%) |
| Full fine-tuning | 63,823,360 trainable parameters (100%) |
| **LoRA evaluation, validation split** | **F1 micro 0.656, F1 macro 0.264, accuracy 0.656** (suspected label leakage; under review) |

The LoRA model predicts `neutral` for all 2,388 validation examples (see the confusion matrix in the notebook), so the micro F1 equals the share of neutral examples (1,566 / 2,388). No pre-trained baseline F1 was measured, and only LoRA was evaluated with F1.

Next steps: check the prompt and target construction for leakage, re-run pretraining with real loss logging, then report macro F1 per method on the validation split.

## LoRA implementation

Written by hand in the notebook (Section 3 and the fine-tuning cells) and refactored in `src/lora.py`, which uses only PyTorch:

```
For each adapted linear layer (frozen weight W, shape d_out × d_in):
  output = W·x + (B·A)·x · (alpha / rank)

  A: rank × d_in   (trainable)
  B: d_out × rank  (trainable, initialised to zero)
  rank = 8, alpha = 16.0
```

`src/lora.py` also provides `merge()`, which folds `B·A` into `W` for inference.

## Project structure

```
01_finance_gpt_lora/
├── README.md
├── ARCHITECTURE.md            design notes
├── LICENSE                    MIT
├── requirements.txt
├── notebooks/
│   └── 01_Finance_SLM_Training_Evaluation.ipynb   the run, with outputs
├── src/
│   ├── model.py               GPT model
│   ├── lora.py                LoRA (no PEFT)
│   ├── dataset.py             dataset class
│   ├── training.py            training loop
│   └── evaluation.py          metrics
├── config/
│   ├── model_config.py        model hyperparameters
│   └── training_config.py     training hyperparameters
├── scripts/
│   ├── train.py               training entry point
│   └── evaluate.py            evaluation entry point
└── docs/
    ├── DEPLOYMENT.md          draft inference guide (not deployed)
    └── CONTRIBUTING.md
```

Note: the notebook defines its own classes inline and does not import `src/`. The `src/` default config (768-dim, 12 heads, 1,024 context) is larger than the model that ran in the notebook.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
jupyter notebook notebooks/01_Finance_SLM_Training_Evaluation.ipynb
```

The notebook was run on Google Colab (A100 40 GB) and saves checkpoints to Google Drive.

Command-line entry points:

```bash
python scripts/train.py --technique lora --epochs 3 --batch_size 32 --learning_rate 5e-5
python scripts/evaluate.py --checkpoint best_lora_lora.pt --technique lora
```

## Bugs found and fixed during the run

1. **Logits taken from the wrong position.** Evaluation first read logits at position -1 (padding), which gave F1 0.14 for every method. Fixed by reading them at the label position.
2. **Checkpoint/architecture mismatch.** LoRA checkpoints were loaded into a model without LoRA layers. Fixed by applying LoRA before `load_state_dict`.
3. **Device mismatch.** Fixed by loading checkpoints with `map_location=device`.

## References

- [LoRA: Low-Rank Adaptation of Large Language Models](https://arxiv.org/abs/2106.09685)
- [Language Models are Unsupervised Multitask Learners](https://d4mucfpksywv.cloudfront.net/better-language-models/language_models_are_unsupervised_multitask_learners.pdf) (GPT-2)

## License

MIT; see [LICENSE](LICENSE).
