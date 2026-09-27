# Small Language Model from Scratch (TinyStories)

A small GPT-style decoder (about 30M parameters) written in PyTorch and pretrained from random weights on the TinyStories dataset, then used to generate short stories. Everything is in one notebook with its outputs.

## What the notebook does

1. Loads [TinyStories](https://huggingface.co/datasets/roneneldan/TinyStories) (about 2.1M training stories)
2. Tokenizes with the GPT-2 tokenizer (tiktoken, 50,257 tokens) into memory-mapped arrays
3. Builds random input/target batches (128-token context, batch 32)
4. Defines the model: token and position embeddings, 6 transformer blocks (6 heads, 384-dim), causal self-attention, weight tying
5. Trains for 20,000 iterations with AdamW at 1e-4, warmup then cosine decay, mixed precision and gradient clipping
6. Plots training and validation loss, then generates text

## Measured results (from the notebook outputs)

| | Value |
|---|---|
| Parameters | ≈30M (computed from the config; mostly the 50,257 × 384 embedding) |
| Loss | train 9.47 / val 9.48 at step 500 → train 2.39 / val 2.40 at step 19,500 |
| Sample output | "The little boy knocked another one of his shadow and she smiled. The little girl thanked her mom…" |

Train and validation loss stay close, so the model is not overfitting at this size.

## Files

```
04_Build_SLM_from_Scratch/
├── notebooks/01_Build_SLM_from_Scratch_Main.ipynb   # all code, with outputs
├── ARCHITECTURE.md
└── requirements.txt
```

Run the notebook top to bottom on a GPU (it was written for Google Colab).

## References

- [TinyStories: How Small Can Language Models Be and Still Speak Coherent English?](https://arxiv.org/abs/2305.07759)
- [nanoGPT](https://github.com/karpathy/nanoGPT) (model structure follows the same GPT design)
