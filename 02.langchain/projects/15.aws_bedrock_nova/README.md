# Amazon Bedrock with Amazon Nova

A course notebook calling Amazon Bedrock directly with `boto3` (`bedrock-runtime`, `invoke_model`), with no LangChain wrapper.

## What the notebook does

| Step | Model | Task |
|---|---|---|
| 1 | `us.amazon.nova-2-lite-v1:0` (Amazon Nova 2 Lite) | Text generation from a one-line prompt |
| 2 | `amazon.nova-canvas-v1:0` (Amazon Nova Canvas) | Text-to-image generation, saved as a PNG |

Generated images are excluded from git; run the notebook to regenerate them.

## Files

```
15.aws_bedrock_nova/
├── 01.Program.ipynb
├── requirements.txt
└── README.md
```

## Setup

1. Configure AWS credentials (`aws configure`, or set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` and `AWS_DEFAULT_REGION`). The notebook uses `us-east-1`.
2. In the AWS console, enable access to the two Nova models under Amazon Bedrock → Model access.
3. Install dependencies and run the notebook:

```bash
pip install -r requirements.txt
jupyter notebook 01.Program.ipynb
```

**Source:** course labs from the Udemy course *Complete Generative AI Course With LangChain and Hugging Face* (completed 20 Jan 2026).
