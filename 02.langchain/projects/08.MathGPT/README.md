# MathGPT (LangGraph ReAct Agent + Groq + Streamlit)

A conversational math assistant that solves mathematical problems, looks up facts on Wikipedia, and provides step-by-step reasoning — powered by a LangGraph ReAct agent.

## Overview

Uses three custom tools combined with a Groq LLM inside a LangGraph ReAct (Reason + Act) agent loop to handle math, factual questions, and multi-step reasoning.

## Tools

| Tool | Purpose |
|---|---|
| `calculator` | Evaluates math expressions using `numexpr` |
| `wikipedia_search` | Fetches factual information from Wikipedia |
| `reasoning` | Provides step-by-step explanation for complex questions |

## Tech Stack

| Component | Technology |
|---|---|
| UI | Streamlit |
| LLM | Groq (`llama-3.1-8b-instant`) |
| Agent Framework | LangGraph (`create_react_agent`) |
| Math Engine | `numexpr` |
| Knowledge | Wikipedia API |

## Project Structure

```
8.MathGPT/
├── app.py
└── README.md
```

## Setup

```bash
# Install dependencies (from repo root)
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

Enter your Groq API key in the sidebar to start.

## Example Queries

- `What is the square root of 144 times pi?`
- `Explain the Pythagorean theorem step by step`
- `Who invented calculus and when?`
- `Calculate 2^10 + 500 / 25`

## How the ReAct Loop Works

```
User question
    ↓
Agent reasons: which tool (if any) to use?
    ↓
Tool executed → result returned to agent
    ↓
Agent reasons again: is the answer complete?
    ↓
Final human-readable answer generated
    ↓
Displayed in chat UI
```

## Key Learnings

- `@tool` decorator converts Python functions into LangChain-compatible tools
- ReAct agents can chain multiple tool calls in a single response
- `numexpr` safely evaluates math expressions without `eval()`
- The system prompt enforces that the agent always provides a **final human-readable answer**, not raw tool output
