# GPT-2 (124M) Pretraining from Scratch

Pretraining a GPT-2 small model (124M parameters) from random weights on the FineWeb-Edu 10B-token sample, following Andrej Karpathy's [build-nanoGPT](https://github.com/karpathy/build-nanogpt). The training code in `src/` is adapted from that repository, and `train_gpt2_runpod.py` is a variant for RunPod single- or multi-GPU runs.

## What was run

The notebook clones build-nanoGPT, downloads the pre-tokenized FineWeb-Edu shards, and trains with `torchrun` on 8 GPUs. The run stopped at **step 2,000 of the 19,073 planned** (about 1B of the 10B tokens, roughly 10% of one epoch).

| Measured in the notebook | Value |
|---|---|
| Parameters | 124,354,560 decayed + 121,344 non-decayed (≈124M) |
| Training loss | 10.96 at step 0 → 3.71 at step 1,999 |
| Validation loss | 3.67 |
| HellaSwag accuracy | 26.0% (2,612 / 10,042; random is 25%) |
| Throughput | ≈43K tokens/sec |

HellaSwag is barely above chance at this point, which is expected this early. The fully trained GPT-2 124M reaches about 29–30%.

## Files

```
02_GPT2_from_Scratch/
├── notebooks/01_GPT2_from_Scratch_Main.ipynb   # the run above, with outputs
├── src/
│   ├── train_gpt2.py        # model + DDP training loop (adapted from build-nanoGPT)
│   ├── fineweb.py           # downloads and tokenizes FineWeb-Edu into shards
│   ├── hellaswag.py         # HellaSwag evaluation
│   └── inference.py         # text generation from a checkpoint
├── train_gpt2_runpod.py     # RunPod variant (single GPU or torchrun)
├── ARCHITECTURE.md · DISTRIBUTED_TRAINING.md · PARAMETER_TUNING.md · RUNPOD_CONFIG.md
└── requirements.txt
```

## Run it

```bash
pip install -r requirements.txt
python src/fineweb.py                                       # writes edu_fineweb10B/ shards
torchrun --standalone --nproc_per_node=8 src/train_gpt2.py  # multi-GPU
python train_gpt2_runpod.py                                 # or a single GPU
```

## Training setup (from `src/train_gpt2.py`)

- 12 layers, 12 heads, 768-dim embeddings, 1,024-token context, 50,257-token vocabulary (padded to 50,304)
- Batch of 524,288 tokens per step (micro-batch 64 × 1,024, with gradient accumulation across GPUs)
- AdamW, max learning rate 6e-4 with 954 warmup steps and cosine decay to 6e-5
- Flash attention (`scaled_dot_product_attention`), DistributedDataParallel, HellaSwag and validation checks during training

## References

- [build-nanoGPT](https://github.com/karpathy/build-nanogpt) by Andrej Karpathy (source of the training code)
- [Language Models are Unsupervised Multitask Learners](https://d4mucfpksywv.cloudfront.net/better-language-models/language_models_are_unsupervised_multitask_learners.pdf) (GPT-2 paper)
- [FineWeb-Edu](https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu) · [HellaSwag](https://rowanzellers.com/hellaswag/)
