# GPT-2 (124M) pretraining: a build-nanoGPT reimplementation

GPT-2 small (124M parameters) trained from random weights on the FineWeb-Edu sample with PyTorch DistributedDataParallel on 8 GPUs. This follows Andrej Karpathy's [build-nanoGPT](https://github.com/karpathy/build-nanogpt): the notebook clones that repository and runs its `train_gpt2.py` with `torchrun`, and the code in `src/` is adapted from it. The training data was pre-tokenised FineWeb-Edu shards from Hugging Face.

## What was run

The notebook (`notebooks/01_GPT2_from_Scratch_Main.ipynb`) clones build-nanoGPT, downloads the pre-tokenised shards, and runs `torchrun --standalone --nproc_per_node=8 train_gpt2.py`. It was a **2,000-step run** (about 1B tokens at 524,288 tokens per step). The logged learning rates fit a schedule configured for about 2,000 steps, so the run completed its full cosine schedule. From the logged step times, the run took about 15 minutes.

| Measured in the notebook | Value |
|---|---|
| Parameters | 124,354,560 decayed + 121,344 non-decayed (≈124M) |
| Training loss | 10.96 at step 0 → 3.71 at step 1,999 |
| Validation loss | 3.6720 |
| HellaSwag accuracy | 26.0% (2,612 / 10,042; random is 25%) |
| Throughput, normal steps | ≈1.27M tokens/sec on 8 GPUs (e.g. step 1,001: 411.58 ms, 1,273,830 tok/s) |
| Throughput, steps that include evaluation | ≈43K–47K tokens/sec (the step also runs validation, HellaSwag and sampling) |

HellaSwag is barely above chance after 2,000 steps, which is expected this early. The notebook does not record the GPU model.

**The committed `src/train_gpt2.py` is not the exact configuration that ran.** It sets `warmup_steps = 954` and `max_steps = 19073` (one epoch of the 10B-token sample). The logged learning rates fit warmup 715 and `max_steps` ≈ 2,000 (e.g. step 0 lr = 6e-4 / 715 = 8.39e-07; step 1,999 lr = the 6e-5 minimum).

## Files

```
02_gpt2_124m_nanogpt_reimplementation/
├── notebooks/01_GPT2_from_Scratch_Main.ipynb   # the run above, with outputs
├── src/
│   ├── train_gpt2.py        # model + DDP training loop (adapted from build-nanoGPT; config differs from the run)
│   ├── fineweb.py           # downloads and tokenises FineWeb-Edu into shards
│   ├── hellaswag.py         # HellaSwag evaluation
│   └── inference.py         # text generation from a checkpoint
├── train_gpt2_runpod.py     # variant for single- or multi-GPU cloud runs
├── ARCHITECTURE.md · DISTRIBUTED_TRAINING.md · PARAMETER_TUNING.md · RUNPOD_CONFIG.md   # planning notes; see the warning at the top of each
└── requirements.txt
```

## Run it

```bash
pip install -r requirements.txt
python src/fineweb.py                                       # writes edu_fineweb10B/ shards
torchrun --standalone --nproc_per_node=8 src/train_gpt2.py  # multi-GPU
python train_gpt2_runpod.py                                 # or a single GPU
```

To reproduce the 2,000-step run, set `max_steps = 2000` and `warmup_steps = 715` in `src/train_gpt2.py`.

## Training setup

- 12 layers, 12 heads, 768-dim embeddings, 1,024-token context, 50,257-token vocabulary (padded to 50,304)
- 524,288 tokens per step (micro-batch 64 × 1,024 on each of 8 GPUs, so 1 gradient-accumulation step)
- AdamW, max learning rate 6e-4, linear warmup and cosine decay to 6e-5
- Flash attention (`scaled_dot_product_attention`), DistributedDataParallel, periodic validation and HellaSwag checks

## Credits and references

- [build-nanoGPT](https://github.com/karpathy/build-nanogpt) by Andrej Karpathy: source of the training code and the overall method
- Pre-tokenised FineWeb-Edu shards from Hugging Face; original dataset: [FineWeb-Edu](https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu)
- [Language Models are Unsupervised Multitask Learners](https://d4mucfpksywv.cloudfront.net/better-language-models/language_models_are_unsupervised_multitask_learners.pdf) (GPT-2 paper)
- [HellaSwag](https://rowanzellers.com/hellaswag/)
