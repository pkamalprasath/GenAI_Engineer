Analyze the current GenAI/ML project and generate a comprehensive, professional README.md.

## Usage
`/genai-readme [--overwrite]`

Without `--overwrite`, shows a preview and asks before replacing an existing README.md.
With `--overwrite`, replaces the existing README.md directly.

## Steps to Perform

### 1. Scan the Project

Collect information by reading:
- All `.py` files → extract imports, class/function names, main entry points
- All `.ipynb` files → read first markdown cell + first few code cells per notebook
- `requirements.txt` / `pyproject.toml` → identify tech stack
- `.env.example` → identify required API keys / external services
- Existing README.md (if any) → preserve any custom sections
- Any `data/`, `assets/`, `models/` directories → note data artifacts

Build answers to these questions:
1. **What does this project do?** (1-2 sentence summary from code/notebooks)
2. **What type is it?** (RAG pipeline / Chatbot / Agent / Fine-tuning / API / Classifier / Image generation / etc.)
3. **What tech stack does it use?** (LLM provider, vector DB, framework, UI, deployment)
4. **What are the inputs and outputs?** (PDF, URL, CSV → answer, summary, image, JSON response)
5. **How do you run it?** (notebook / python script / streamlit / uvicorn / docker)
6. **What API keys are required?** (from .env.example)

### 2. Determine Project Type

Match detected imports/packages to project type:

| Detected Package | Project Type |
|---|---|
| `langchain` + `faiss`/`chroma` | RAG Pipeline |
| `langchain` + `streamlit` | LangChain Chatbot |
| `langgraph` | Agentic Workflow |
| `crewai` | Multi-Agent System |
| `lamini` / `peft` / `trl` | Fine-tuning |
| `langserve` / `fastapi` | LLM API Server |
| `boto3` + `bedrock` | AWS Bedrock Integration |
| `pinecone` | Hybrid Vector Search |
| `neo4j` | Graph RAG / Knowledge Graph |
| `slack_bolt` | Slack AI Bot |
| `transformers` + `datasets` | HuggingFace Training |
| `streamlit` | Streamlit App |

### 3. Generate README.md

Use this template, filling in all `<placeholders>` from the scan:

```markdown
# <Project Name>

> <One-line description: what it does and why it's useful>

## Overview

<2-3 paragraph description covering:
- What problem this solves
- How it works at a high level
- What makes it interesting or unique>

## Architecture

```
<ASCII diagram of the data/processing flow>
Example for RAG:
User Query
    ↓
Query Embedding
    ↓
Vector Store (ChromaDB/FAISS) → Top-K Chunks
    ↓
LLM + Prompt Template
    ↓
Answer
```

## Tech Stack

| Component | Technology |
|---|---|
| Framework | LangChain / LangGraph / CrewAI |
| LLM | OpenAI GPT-4o / Groq LLaMA / AWS Bedrock Claude |
| Embeddings | OpenAI text-embedding-3 / HuggingFace |
| Vector Store | FAISS / ChromaDB / Pinecone |
| UI | Streamlit / FastAPI / Jupyter |

## Project Structure

```
<project-name>/
├── <main files with one-line description each>
```

## Setup

### Prerequisites
- Python 3.10+
- API keys (see Environment Variables below)

### Installation

```bash
# 1. Clone the repository
git clone <repo-url>
cd <project-name>

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env and fill in your API keys
```

### Environment Variables

| Variable | Required | Description | Get it from |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | OpenAI API key | https://platform.openai.com/api-keys |
| `LANGCHAIN_API_KEY` | Optional | LangSmith tracing | https://smith.langchain.com/settings |

## Usage

<How to run the project — pick the appropriate one:>

### Run as Jupyter Notebook
```bash
jupyter notebook <notebook-name>.ipynb
```

### Run as Streamlit App
```bash
streamlit run app.py
```

### Run as API Server
```bash
uvicorn app:app --reload
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### Run as Script
```bash
python main.py
```

## Key Concepts

<3-6 bullet points explaining the core ML/LLM concepts demonstrated, with brief explanations>

- **<Concept>** — <explanation>

## Example

<A concrete input/output example showing the project in action>

**Input:** `"<example question or prompt>"`

**Output:**
```
<example response>
```

## Notes

- <Any important limitations, known issues, or caveats>
- <Data/model requirements>
- <Cost considerations for API calls>

## License

MIT
```

### 4. Special Sections by Project Type

Add these extra sections based on project type:

**For RAG Projects** — add "Retrieval Details":
```markdown
## Retrieval Details

| Parameter | Value |
|---|---|
| Chunk size | 1000 characters |
| Chunk overlap | 200 characters |
| Embedding model | text-embedding-3-small |
| Vector store | ChromaDB (local) |
| Top-K retrieval | 4 chunks |
| Search type | Similarity search |
```

**For Agents/LangGraph** — add "Agent Architecture":
```markdown
## Agent Architecture

```
[User Input]
     ↓
[StateGraph Entry]
     ↓
[Node: research_agent] → [Tool: web_search]
     ↓
[Node: writer_agent]   → [Tool: document_writer]
     ↓
[Conditional Edge] ──→ END (if done)
         └──────────→ [Node: reviewer] (if needs review)
```

**Nodes:** list them
**Tools:** list them
**State:** what's stored in TypedDict State
```

**For Fine-tuning Projects** — add "Training Details":
```markdown
## Training Details

| Parameter | Value |
|---|---|
| Base model | meta-llama/Meta-Llama-3-8B-Instruct |
| Method | LoRA / QLoRA (4-bit) |
| Learning rate | 1e-4 |
| Epochs | 3 |
| Dataset size | N examples |
```

**For API/LangServe Projects** — add "API Endpoints":
```markdown
## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/chain/invoke` | Single invocation |
| POST | `/chain/stream` | Streaming response |
| POST | `/chain/batch` | Batch processing |
| GET  | `/chain/playground` | Interactive UI |
```

**For Slack Bot Projects** — add "Slack App Setup":
```markdown
## Slack App Setup

1. Go to https://api.slack.com/apps → Create New App
2. OAuth & Permissions → Bot Token Scopes: `app_mentions:read`, `chat:write`
3. Event Subscriptions → Subscribe to: `app_mention`, `message.im`
4. Socket Mode → Enable → Create App-Level Token (scope: `connections:write`)
5. Install App to Workspace → copy Bot Token
```

### 5. ASCII Architecture Diagram Guidelines

Generate the right diagram per type:

**RAG:**
```
PDF/URL/CSV → Loader → Splitter → Embeddings → Vector Store
                                                     ↓
User Question → Query Embedding → Similarity Search → Top-K Chunks
                                                     ↓
                                    LLM + Prompt → Answer
```

**Agent:**
```
User Input → Agent (ReAct Loop) → Tool Selection → Tool Execution
                    ↑                                      ↓
                    └──────── Observation / Result ────────┘
                                      ↓ (done)
                               Final Answer
```

**Chatbot with Memory:**
```
User Message → Chat History (Buffer/Summary) → Prompt Template
                                                      ↓
                                               LLM (GPT-4o) → Response
```

**Fine-tuning:**
```
Dataset → Tokenizer → Base Model (frozen) → LoRA Adapter (trainable)
                                                    ↓
                                          Fine-tuned Model → Inference
```

### 6. Report

Show:
- Detected project type
- Tech stack identified
- Files analyzed
- README.md created/updated at: `<path>`
- Preview: first 30 lines of generated README
- Any sections that could not be filled (need manual editing)
