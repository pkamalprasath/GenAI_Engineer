# Global Claude Code Rules & Context
# Kamal Prasath — GenAI Engineer

These rules apply to ALL projects. Project-level CLAUDE.md adds to these.

---

## Identity & Stack

- **Platform**: Windows 10, bash shell via VS Code terminal
- **Python**: always use `venv` (not conda) unless explicitly told otherwise
- **venv path**: `.venv\Scripts\python.exe` on Windows, `.venv/bin/python` on Linux/macOS
- **Shell**: Use `powershell -Command "..."` when bash commands fail on Windows

---

## Security Rules (NON-NEGOTIABLE)

1. **NEVER hardcode API keys, tokens, passwords, or secrets** in any file
2. Always use `os.getenv("KEY_NAME")` with `python-dotenv` and `load_dotenv()`
3. Every project needs `.env` in `.gitignore` and `.env.example` with placeholder values
4. Before any `git push`, run a secret scan — search for: `sk-`, `sk-proj-`, `lsv2_`, `hf_`, `gsk_`, `pcsk_`, `AstraCS:`, `AKIA`, `xoxb-`, `xoxp-`
5. If secrets found in git history, rewrite history with orphan branch before pushing
6. Jupyter notebooks are HIGH RISK — cell outputs can expose secrets; scan `.ipynb` JSON too

---

## Python Project Rules

### Environment
```bash
# Always set up like this
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux/macOS
pip install -r requirements.txt
```

### Project Structure (GenAI projects)
```
project-name/
├── README.md          # Required — overview, setup, API keys table
├── requirements.txt   # Pinned or grouped with comments
├── .env.example       # Placeholder values — SAFE to commit
├── .gitignore         # Must include: venv/, .env, __pycache__, *.db, *.faiss
├── src/ or app.py     # Main code
├── notebooks/         # Jupyter experiments (scan for secrets before commit)
└── data/              # Sample data (no sensitive data)
```

### requirements.txt format
```
# --- Core ---
langchain
# --- LLMs ---
langchain-openai
# --- Vector Stores ---
chromadb
```
Group by category. Remove duplicates. Add comments.

---

## LangChain Patterns

### Always use LCEL (LangChain Expression Language)
```python
chain = prompt | llm | output_parser   # preferred
chain = LLMChain(llm=llm, prompt=prompt)  # legacy, avoid
```

### RAG Pipeline Pattern
```python
# Load → Split → Embed → Store → Retrieve → Generate
loader = PyPDFLoader("doc.pdf")
splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
embeddings = OpenAIEmbeddings()
vectorstore = FAISS.from_documents(splits, embeddings)
retriever = vectorstore.as_retriever()
chain = create_retrieval_chain(retriever, document_chain)
```

### Environment Loading (always at top of file)
```python
import os
from dotenv import load_dotenv
load_dotenv()

openai_key = os.getenv("OPENAI_API_KEY")
```

### Streamlit Apps
- Use `st.session_state` for all state that must survive reruns
- Never put API keys in source code — use `st.sidebar.text_input(..., type="password")`
- Cache heavy resources with `@st.cache_resource`

### Agents / Tools
```python
@tool
def my_tool(query: str) -> str:
    """Clear docstring — the LLM reads this to decide when to call the tool."""
    ...
```

---

## LangGraph Patterns

```python
from langgraph.graph import StateGraph, START, END
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

class State(TypedDict):
    messages: Annotated[list, add_messages]  # always use add_messages, not plain list

graph = StateGraph(State)
graph.add_node("node_name", function)
graph.add_edge(START, "node_name")
graph.add_edge("node_name", END)
app = graph.compile()
```

---

## Slack Bot Rules (from open_claw project)

- **Middleware MUST use `next` as the parameter name** — not `next_fn`, not `nxt`
- `reactions_add` throws `already_reacted` — always wrap in `try/except SlackApiError`
- `reactions_remove` throws `no_reaction` — same, always catch
- For `@mentions`: listen in `app_mention` handler ONLY, not `message` (both fire — causes double responses)
- Bot token format: `xoxb-...` (never commit), App token: `xapp-...`
- Use Socket Mode for development, HTTP for production
- Slack channel IDs: `^[CDGW][A-Z0-9]{8,12}$` — C=public, D=DM, G=group, W=workspace

---

## Git & GitHub Rules

### Pushing to GitHub (pkamalprasath/GenAI_Engineer pattern)
Use `/github-push <url> <subfolder>` — it writes and runs a Python script that:
1. Clones the target repo to `C:\Temp\<repo>_push`
2. Copies all project files (skipping venv, __pycache__, .git, reports, .env)
3. Commits and pushes to origin main/master
4. Cleans up the temp directory

**Always use Python subprocess for git operations on Windows** — bash is unreliable,
PowerShell `$variable` syntax gets mangled by the shell layer.

### Before every push
1. Run `/secret-scan` on all tracked files
2. Check `.gitignore` covers: `venv/`, `.env`, `__pycache__/`, `*.db`, `*.sqlite`, generated outputs
3. Verify `README.md` exists and is complete
4. Verify `.env.example` exists and has all required keys as placeholders

### Commit message format
```
type: short description

- bullet detail 1
- bullet detail 2
```
Types: `feat`, `fix`, `docs`, `refactor`, `security`, `chore`

### Never commit
- `venv/` or `.venv/`
- `.env` (any file with real credentials)
- `__pycache__/`, `*.pyc`
- Generated vector stores: `chroma_db/`, `faiss.index/`
- Jupyter checkpoint folders: `.ipynb_checkpoints/`
- Database files: `*.db`, `*.sqlite`, `*.sqlite3`
- AI-generated output images/files unless specifically needed

---

## Code Quality Rules

1. **No over-engineering** — build the minimum that solves the problem
2. **No premature abstraction** — three similar lines beats a helper function for one-time use
3. **No backwards-compat shims** — if something is removed, delete it completely
4. **Validate at boundaries** — user input, external APIs; trust internal code
5. **Use `os.getenv()` at startup** — not scattered through the code

---

## Common Mistakes to Avoid

| Mistake | Correct |
|---|---|
| `max_token` | `max_tokens` (LangChain param) |
| `StructuredOutputParser` for normal chat | Just use `response.content` |
| Hardcoding `gpt-4` | Fetch models dynamically or make configurable |
| `OpenAI.api_key = key` | Pass `api_key=` into `ChatOpenAI(...)` |
| `num_predict` vs `max_tokens` | Ollama uses `num_predict`, OpenAI uses `max_tokens` |
| Chat models returning strings | `ChatOpenAI` returns message objects — use `.content` |
| `message` + `app_mention` both firing | Only handle in `app_mention` |
| Importing at function level | Always import at top of file |
| `MemoryError` as custom exception name | Shadows Python built-in — use `BotMemoryError` etc. |
| Importing `@mcp.tool()` functions directly | Use underlying SDK — decorated funcs are `FunctionTool` objects, not callable |
| Multiple instances of MemoryManager | Share single instance via dependency injection |
| Forgetting `scheduler.start()` | Periodic jobs never run without it |
| Tools raising exceptions | Agent ReAct loop crashes — return `{"success": False, "error": "..."}` instead |

---

## Reference Library (from open_claw_slack_bot project)

Detailed patterns, rules, and skills stored in global `.claude` folder:

### Slash Commands (`commands/`)
- `/add-agent-tool` — Add a new tool to an agent's ToolRegistry
- `/add-scheduler-job` — Add periodic APScheduler background job
- `/debug-agent-tools` — 7-step debug process for broken agent tools
- `/bug-hunter` — Systematically find and document bugs (creates PROBLEMS.md)
- `/integration-tester` — Create comprehensive async integration test suite
- `/github-push <url> <subfolder>` — Push current project into a subfolder of any GitHub repo (Python-based, works without bash/gh)

### Patterns (`patterns/`)
- `error-handling-strategy.md` — Layered error handling: tools → services → listeners → jobs
- `shared-state-management.md` — Dependency injection for stateful components
- `testing-async-services.md` — 10 patterns for testing async Python + AI services

### Rules (`rules/`)
- `slack-bot-development.md` — 10 critical rules for Slack + Agent bots
- `fastmcp-integration.md` — Why `@mcp.tool()` breaks direct imports and the fix
