# Chatbot with LangGraph (Stateful Graph-based Agents)

Experiments building chatbots using LangGraph — a framework for stateful, multi-step LLM workflows modeled as directed graphs.

## Overview

LangGraph extends LangChain by enabling **stateful**, **cyclical** agent flows — unlike simple LCEL chains which are linear. The chatbot maintains message state across turns using a typed `State` object.

## Notebooks

| Notebook | Description |
|---|---|
| `chatbot.ipynb` | Basic LangGraph chatbot — `START → chatbot → END` |
| `With_tools.ipynb` | LangGraph chatbot with tool-calling and conditional edges |

## Architecture (Basic Chatbot)

```python
State = { messages: list }

START → chatbot (calls LLM) → END
```

The graph compiles into an executable that handles:
- State initialization
- Node execution (chatbot function calls LLM)
- Message accumulation via `add_messages`

## Architecture (With Tools)

```
START
  ↓
chatbot node
  ↓
tools node (if tool_calls present)
  ↓
back to chatbot (conditional edge loops back)
  ↓
END (when no more tool calls)
```

## Tech Stack

| Component | Technology |
|---|---|
| Graph Framework | LangGraph |
| LLM | Groq (`llama-3.1-8b-instant`) |
| State Management | `TypedDict` + `add_messages` |
| Visualization | Mermaid diagram (via `draw_mermaid_png`) |
| Notebook | Jupyter |

## Project Structure

```
14.QA_chatbot_WithLangraph/
├── chatbot.ipynb       # Simple start→chatbot→end graph
├── With_tools.ipynb    # Graph with tool-calling loop
└── README.md
```

## Setup

```bash
# Install LangGraph and dependencies
pip install langgraph
pip install -r ../../requirements.txt

# Set API keys in .env (see root .env.example)
```

## Key Concepts

- **`StateGraph`** — the core LangGraph object; nodes are Python functions, edges are transitions
- **`add_messages`** — annotator that appends new messages instead of overwriting state
- **`TypedDict`** — defines the shape of the shared state flowing through all nodes
- **Conditional edges** — route to different nodes based on state (e.g., tool call present → tools node)
- **Compilation** — `graph.compile()` produces an executable runnable
- **`graph.stream()`** — runs the graph and yields node outputs as events

## LangGraph vs LCEL Chains

| Feature | LCEL Chain | LangGraph |
|---|---|---|
| Flow type | Linear | Graph (cyclic allowed) |
| State | Stateless | Stateful (`TypedDict`) |
| Best for | Simple pipelines | Agents, multi-step flows |
| Tool loops | Not supported | Supported via conditional edges |

## Environment Variables

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY` | LLM inference |
| `LANGCHAIN_API_KEY` | LangSmith tracing (optional) |
