Scan the current project's Python files and notebooks, detect all environment variables used, and create a proper .env.example and .gitignore.

## Steps to Perform

### 1. Scan for environment variable usage
Search all `.py` and `.ipynb` files for:
- `os.getenv("KEY")` or `os.getenv('KEY')`
- `os.environ["KEY"]` or `os.environ['KEY']`
- `os.environ.get("KEY")`
- `load_dotenv()` presence
- Any hardcoded secrets (flag as CRITICAL — replace before creating .env.example)

Build a list of all unique environment variable names found.

### 2. Categorize variables
Group discovered variables by provider:
- OpenAI: `OPENAI_API_KEY`
- LangChain: `LANGCHAIN_API_KEY`, `LANGCHAIN_TRACING_V2`, `LANGCHAIN_PROJECT`
- HuggingFace: `HF_TOKEN`
- Groq: `GROQ_API_KEY`
- Anthropic: `ANTHROPIC_API_KEY`
- Slack: `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_SIGNING_SECRET`
- AWS: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`
- Neo4j: `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`
- Pinecone: `PINECONE_API_KEY`, `PINECONE_ENV`
- Other/custom: everything else

### 3. Create .env.example
Generate `.env.example` with:
```
# ============================================================
# <Project Name> — Environment Variables
# ============================================================
# SETUP:
#   1. cp .env.example .env
#   2. Fill in your actual values
#   3. NEVER commit .env to git
# ============================================================

# --- Provider Group ---
KEY_NAME="your-placeholder-here"   # link to where to get it
```

Include comments with the URL where each key can be obtained.

### 4. Create/Update .gitignore
Ensure `.gitignore` contains at minimum:
```
# Python
__pycache__/
*.py[cod]
*.pyo

# Virtual environments
venv/
.venv/
env/

# Secrets
.env
.env.*
!.env.example

# Jupyter
.ipynb_checkpoints/

# Generated vector stores
chroma_db/
faiss.index/
*.faiss
*.pkl

# Databases
*.db
*.sqlite
*.sqlite3

# IDE
.vscode/
.idea/
.claude/

# Logs
*.log
```

### 5. Report
Show:
- All environment variables found and which files use them
- Whether .env.example was created or updated
- Whether .gitignore was created or updated
- Any hardcoded secrets detected (and auto-fixed if `--fix` in $ARGUMENTS)

If $ARGUMENTS contains a specific provider name (e.g., `slack`, `openai`, `groq`), add that provider's typical variables even if not yet in the code.
