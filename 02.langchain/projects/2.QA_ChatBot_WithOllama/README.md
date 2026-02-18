# Q&A Chatbot with Ollama (Local LLMs + LangChain + Streamlit)

A Q&A chatbot that runs entirely on your local machine using Ollama, LangChain, and Streamlit — no external API costs, no data leaving your device.

## Overview

Demonstrates how to build a local-first chatbot using Ollama for LLM inference and LangChain for prompt management. The application allows users to:

- Select any locally available Ollama model
- Control generation parameters (temperature)
- Ask natural language questions
- Receive responses generated entirely on the local machine

## Tech Stack

| Component | Technology |
|---|---|
| UI | Streamlit |
| LLM Orchestration | LangChain |
| Local LLM Runtime | Ollama |
| Prompt Management | `ChatPromptTemplate` |
| Language | Python |

## Prerequisites

- [Ollama](https://ollama.com/download) installed and running
- At least one model pulled locally

```bash
# Install a model
ollama pull llama3

# Verify available models
ollama list
```

## Project Structure

```
2.QA_ChatBot_WithOllama/
├── app.py
├── .env.example
└── README.md
```

## Setup

```bash
# 1. Ensure Ollama is running
ollama serve

# 2. Install dependencies (from repo root)
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py
```

Open your browser at `http://localhost:8501`

## Key Learnings

- **Ollama uses `num_predict`**, not `max_tokens` — check model-specific parameter support
- **Ollama response format** differs from `ChatOpenAI` — may return plain string instead of message object
- **Local-first AI** improves privacy and eliminates API costs
- `ChatOllama` (LangChain wrapper) gives chat-style message formatting if needed
- No API keys required — Ollama runs locally

## Why Local LLMs?

| Factor | Cloud LLMs | Local (Ollama) |
|---|---|---|
| Cost | Per-token billing | Free |
| Privacy | Data sent externally | Stays on device |
| Latency | Network-dependent | Hardware-dependent |
| Availability | Requires internet | Fully offline |
