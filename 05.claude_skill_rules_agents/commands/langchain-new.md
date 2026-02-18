Scaffold a new LangChain project with proper structure, security, and GitHub-ready setup.

## Usage
/langchain-new <project-name> [type]

Types: `chatbot` | `rag` | `agent` | `api` | `summarizer` (default: `chatbot`)

## What to Create

### 1. Determine project type from $ARGUMENTS
Parse the project name and optional type from $ARGUMENTS.

### 2. Create folder structure

For ALL types:
```
<project-name>/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
└── app.py
```

For `rag`:
```
<project-name>/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── app.py
└── data/              # place your PDFs/docs here
```

For `agent`:
```
<project-name>/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── app.py
└── tools/
    └── __init__.py
```

For `api` (LangServe):
```
<project-name>/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
└── server.py
```

### 3. File contents

**.gitignore** — include: `venv/`, `.venv/`, `.env`, `__pycache__/`, `*.pyc`, `.ipynb_checkpoints/`, `chroma_db/`, `faiss.index/`, `*.db`, `output/`, `.claude/`

**.env.example**:
```
# Copy to .env and fill in your actual keys
OPENAI_API_KEY="your-openai-key-here"
LANGCHAIN_API_KEY="your-langchain-key-here"
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT="<project-name>"
```
Add additional keys based on type (GROQ_API_KEY for groq, HF_TOKEN for huggingface, etc.)

**requirements.txt** — grouped by category, based on type:
- chatbot: `langchain`, `langchain-openai`, `streamlit`, `python-dotenv`
- rag: add `langchain-community`, `pypdf`, `faiss-cpu`, `langchain-text-splitters`
- agent: add `ddgs`, `wikipedia`, `arxiv`
- api: add `fastapi`, `uvicorn`, `langserve`, `sse_starlette`

**app.py** — create a working starter template with:
- `load_dotenv()` at top
- All API keys via `os.getenv()`
- Proper imports
- Basic working example for the chosen type
- Comments explaining each section

**README.md** — include:
- Project title
- What it does
- Setup instructions (venv, pip, .env)
- How to run
- Required API keys table

### 4. Confirm

After creating all files, display:
- The full folder tree created
- The command to run it: `streamlit run app.py` or `python server.py`
- Reminder: "Copy `.env.example` to `.env` and fill in your API keys before running"
