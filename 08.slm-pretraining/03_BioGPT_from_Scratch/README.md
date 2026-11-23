# BioGPT-style Biomedical Language Model from Scratch

A small GPT-style model (27M parameters) pretrained from random weights on PubMed abstracts using the BioGPT vocabulary, then fine-tuned with a soft prompt to classify cancer hallmarks on the HoC dataset. Everything is in one notebook with its outputs.

## What the notebook does

**Part 1: Pretraining**
1. Downloads a PubMed baseline XML subset and extracts titles and abstracts
2. Cleans text with the Moses tokenizer, then applies BioGPT's BPE codes and vocabulary
3. Trains a 6-layer, 6-head, 384-dim decoder (128-token context) for 120,000 iterations
   (batch 32, AdamW at 1e-4, warmup then cosine decay)

**Part 2: Fine-tuning on HoC (Hallmarks of Cancer)**
1. Loads the HoC train/valid/test splits from Microsoft's BioGPT repo
2. Adds trainable soft-prompt embeddings in front of the input and restricts generation to label tokens
3. Fine-tunes and evaluates per-class precision, recall and F1

## Measured results (from the notebook outputs)

| | Value |
|---|---|
| Parameters | 26,970,624 (≈27M) |
| Pretraining loss | train 9.75 / val 9.78 at step 500 → train 3.56 / val 3.47 at step 119,500 |
| HoC before fine-tuning (pretrained model + cue) | micro F1 0.005, macro F1 0.003 |
| HoC after soft-prompt fine-tuning | micro F1 0.29, macro F1 0.42 (hallmark labels only) |

For scale, Microsoft's BioGPT (347M parameters) reports much higher HoC scores. This project shows the full pipeline at small scale, not state-of-the-art accuracy.

## Files

```
03_BioGPT_from_Scratch/
├── notebooks/01_BioGPT_from_Scratch_Main.ipynb   # all code, with outputs
├── ARCHITECTURE.md
└── requirements.txt
```

Run the notebook top to bottom. It was written for Google Colab with a GPU, and Part 1 downloads about 10 GB of PubMed XML.

## References

- [BioGPT: generative pre-trained transformer for biomedical text generation and mining](https://academic.oup.com/bib/article/23/6/bbac409/6713511)
- [microsoft/BioGPT](https://github.com/microsoft/BioGPT) (vocabulary, BPE codes and HoC data)
- [PubMed baseline](https://ftp.ncbi.nlm.nih.gov/pubmed/baseline/)
