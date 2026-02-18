# Q&A Chatbot with OpenAI (LangChain + Streamlit)

A simple, real-time Q&A chatbot built using OpenAI, LangChain, and Streamlit, with dynamic model selection and configurable generation parameters.

## Overview

Demonstrates how to build a minimal chatbot using LangChain's `ChatOpenAI` wrapper and Streamlit for the UI. The application allows users to:

- Enter their OpenAI API key at runtime (no hardcoded keys)
- Dynamically fetch available OpenAI chat models in real time
- Select a model from a dropdown
- Control temperature and maximum token limits
- Ask questions and receive AI-generated answers instantly

## Tech Stack

| Layer | Technology |
|---|---|
| UI | Streamlit |
| LLM Interface | LangChain |
| Model Provider | OpenAI |
| Model Wrapper | `ChatOpenAI` |
| Prompting | `ChatPromptTemplate` |
| Environment | Python, dotenv |
| Observability | LangSmith (optional) |

## Project Structure

```
1.QA_ChatBot_WithOpenAI/
├── app.py
├── .env.example
└── README.md
```

## Setup

```bash
# 1. Copy and fill in your API key
cp .env.example .env

# 2. Install dependencies (from repo root)
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py
```

Open your browser at `http://localhost:8501`

## How It Works

1. User enters an OpenAI API key in the sidebar
2. App fetches available models from OpenAI `/models` endpoint
3. User selects a `gpt-*` chat model from dropdown
4. User configures temperature and max tokens via sliders
5. User submits a question
6. LangChain sends the formatted prompt to OpenAI
7. Response is rendered in Streamlit

## Key Learnings

- **Dynamic model discovery** — fetch models at runtime, never hardcode
- **Model filtering** — only `gpt-*` models work with chat endpoints
- **Pass `api_key` directly** into `ChatOpenAI`, not via `OpenAI.api_key`
- **`response.content`** is sufficient; `StructuredOutputParser` is only needed for JSON output
- Simpler pipelines are easier to debug — start minimal, then extend

## Environment Variables

See [.env.example](.env.example) for required keys.

| Variable | Required | Purpose |
|---|---|---|
| `LANGCHAIN_API_KEY` | Optional | LangSmith tracing |
| `LANGCHAIN_TRACING_V2` | Optional | Enable LangSmith |
