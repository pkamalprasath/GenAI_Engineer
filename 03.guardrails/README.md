# AI Guardrails & Safety Engineering

A hands-on learning repository covering AI safety, guardrails, evaluation, and security testing for LLM-based applications.

## Overview

Production techniques for making AI systems safer, more reliable, and more secure covering input/output validation, PII protection, hallucination detection, prompt injection defense, and adversarial security testing.

## Modules

| # | Folder | Focus | Key Libraries |
|---|---|---|---|
| 01 | 01.Guardrails | Output validation, structured extraction, custom validators | guardrails-ai, pydantic |
| 02 | 02.NemoGuardRails | Rule-based guardrails with config-driven flows | nemoguardrails |
| 03 | 03.Evaluators | RAG pipeline evaluation, faithfulness, relevance | deepeval, ragas |
| 04 | 04.Prompt_Injection | Prompt injection detection using LLaMA Guard and PromptGuard | transformers, meta-llama |
| 05 | 05.Sensitive_Information | PII detection and anonymization | presidio-analyzer, presidio-anonymizer |
| 06 | 06.Hallucination | Hallucination detection and scoring | vectara, phi-3-mini |
| 07 | 07.Garak | LLM security red-teaming (encoding attacks, XSS, profanity) | garak |
| 08 | 08.Security_Testing | AI-powered penetration testing agents | crewai, zapproxy |

## Setup

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment variables
cp .env.example .env
# Edit .env and fill in your API keys
```

## Environment Variables

| Variable | Required By | Get It From |
|---|---|---|
| OPENAI_API_KEY | 01.Guardrails, 03.Evaluators, 08.Security_Testing | https://platform.openai.com/api-keys |
| HF_TOKEN | 07.Garak, 04.Prompt_Injection | https://huggingface.co/settings/tokens |

## Key Concepts

- **Guardrails AI** - Validate and correct LLM outputs against schemas and rules
- **NemoGuardRails** - Colang-based flow definitions to restrict topics and behaviors
- **Presidio** - Microsoft PII detection and anonymization engine
- **LLaMA Guard** - Meta safety classifier for detecting prompt injection
- **Garak** - Automated LLM vulnerability scanner (encoding, XSS, jailbreaks)
- **CrewAI** - Multi-agent system for orchestrating security testing workflows
- **RAG Evaluation** - Faithfulness, context relevance, and answer relevance metrics
