# HuggingFace Integration with LangChain

Experiments demonstrating how to use open-source models from HuggingFace Hub with LangChain — as an alternative to paid OpenAI/Groq APIs.

## Overview

Covers loading and running HuggingFace models for text generation and embeddings using `langchain_huggingface`. Useful for running open-source LLMs without API costs.

## Tech Stack

| Component | Technology |
|---|---|
| Model Hub | HuggingFace Hub |
| LLM Integration | `langchain_huggingface` |
| Embeddings | `HuggingFaceEmbeddings` |
| Notebook | Jupyter |

## Project Structure

```
9.WithHuggingface/
├── experiments.ipynb
└── README.md
```

## Setup

```bash
# 1. Set your HuggingFace token
cp ../../.env.example .env
# Add HF_TOKEN to .env

# 2. Install dependencies (from repo root)
pip install -r requirements.txt

# 3. Launch Jupyter
jupyter notebook experiments.ipynb
```

## Key Concepts

- **`HuggingFaceHub`** — run inference via HuggingFace Inference API (cloud)
- **`HuggingFacePipeline`** — run models locally using `transformers` pipeline
- **`HuggingFaceEmbeddings`** — generate embeddings locally (free, no API key)
- Open-source models: `mistralai/Mistral-7B`, `google/flan-t5-*`, `sentence-transformers/*`

## Environment Variables

| Variable | Purpose |
|---|---|
| `HF_TOKEN` | HuggingFace API token for gated models |
