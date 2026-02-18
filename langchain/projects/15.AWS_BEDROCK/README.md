# AWS Bedrock Integration

Experiments using AWS Bedrock to access foundation models (Claude, Titan, Nova) via Amazon's managed AI infrastructure.

## Overview

AWS Bedrock provides serverless access to foundation models from Anthropic, Amazon, Meta, and others. This project demonstrates how to invoke Bedrock models for text generation and image generation.

## Models Covered

| Model Family | Provider | Use Case |
|---|---|---|
| Claude (claude-*) | Anthropic | Text generation, reasoning |
| Amazon Titan | Amazon | Text + image embeddings |
| Amazon Nova Canvas | Amazon | Image generation |
| LLaMA | Meta | Open-source text generation |

## Tech Stack

| Component | Technology |
|---|---|
| Cloud Provider | AWS |
| Service | Amazon Bedrock |
| SDK | `boto3` |
| LangChain Integration | `langchain_aws` (`BedrockChat`) |
| Notebook | Jupyter |

## Project Structure

```
15.AWS_BEDROCK/
├── Program.ipynb      # Bedrock experiments notebook
├── requirements.txt   # Bedrock-specific dependencies
└── README.md
```

> **Note:** Image generation outputs (`.png` files) are excluded from git. Run the notebook to regenerate them.

## Setup

### 1. Configure AWS credentials

```bash
aws configure
# Enter: Access Key ID, Secret Access Key, Region (e.g. us-east-1)
```

Or set environment variables:

```bash
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
export AWS_DEFAULT_REGION="us-east-1"
```

### 2. Enable Bedrock model access

In the AWS Console → Amazon Bedrock → Model Access → enable the models you want to use.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the notebook

```bash
jupyter notebook Program.ipynb
```

## Environment Variables

| Variable | Purpose |
|---|---|
| `AWS_ACCESS_KEY_ID` | AWS authentication |
| `AWS_SECRET_ACCESS_KEY` | AWS authentication |
| `AWS_DEFAULT_REGION` | Bedrock region (default: `us-east-1`) |

## Key Concepts

- **Bedrock is serverless** — no model deployment needed; pay per token
- **`InvokeModel` API** — low-level boto3 call with model-specific JSON body
- **`BedrockChat`** (LangChain) — higher-level LangChain wrapper for chat models
- **Model IDs** must match exactly (e.g., `anthropic.claude-3-sonnet-20240229-v1:0`)
- **Cross-region inference** — some models require a specific region
