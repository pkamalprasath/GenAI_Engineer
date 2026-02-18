# Tool-based Q&A Chatbot (LangChain Agent + Groq + Streamlit)

A conversational AI agent that can search the web (DuckDuckGo), Wikipedia, and Arxiv to answer user questions, with persistent chat history.

## Overview

Uses a LangChain/LangGraph ReAct agent with external search tools to answer questions that go beyond static model knowledge. The agent dynamically decides which tool to call based on the question.

- Multi-turn conversation with persistent chat history
- Web search via DuckDuckGo
- Wikipedia and Arxiv lookups
- Real-time tool execution displayed in the Streamlit UI

## Tech Stack

| Component | Technology |
|---|---|
| UI | Streamlit |
| LLM | Groq (LLaMA 3) |
| Agent Framework | LangChain / LangGraph |
| Tools | DuckDuckGo, Wikipedia, Arxiv |
| State Management | `st.session_state` |
| Callbacks | `StreamlitCallbackHandler` |

## Project Structure

```
5.QA_ChatBot_Tool_based/
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

## How It Works

```
User question
    ↓
Chat history loaded from session_state
    ↓
LangChain ReAct agent decides: answer directly OR use a tool
    ↓
Tool called (DuckDuckGo / Wikipedia / Arxiv)
    ↓
Tool result passed back to LLM
    ↓
Final answer extracted from AIMessage
    ↓
Answer saved to history + displayed
```

## Key Learnings

- **`st.session_state`** preserves chat history across Streamlit reruns
- **Agent output is structured** — extract `AIMessage.content` from the last message for clean display
- **`StreamlitCallbackHandler`** shows agent reasoning steps inline in the UI
- Tool-based agents improve answer quality for factual, time-sensitive, or domain-specific questions
