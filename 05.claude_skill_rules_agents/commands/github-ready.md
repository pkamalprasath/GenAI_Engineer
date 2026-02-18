Perform a comprehensive GitHub-readiness audit on the current project. Work through every check below in order and produce a clear report.

## Checks to Perform

### 1. Secret Scan (CRITICAL — check first)
Search ALL non-venv files for these patterns:
- OpenAI: `sk-proj-`, `sk-[a-zA-Z0-9]{20,}`
- LangSmith: `lsv2_`
- HuggingFace: `hf_[a-zA-Z]`
- Groq: `gsk_`
- Pinecone: `pcsk_`
- AstraDB: `AstraCS:`
- AWS: `AKIA[A-Z0-9]{16}`
- Slack: `xoxb-`, `xoxp-`, `xapp-`
- Neo4j passwords (long random strings in .env-like assignments)
- Generic: any line matching `api_key\s*=\s*"[^"]{20,}"` or `password\s*=\s*"[^"]{8,}"`

For each secret found: report file, line number, type. If found in Jupyter notebooks (.ipynb), check both source cells AND outputs.

### 2. .gitignore
Check if `.gitignore` exists. Verify it covers:
- `venv/`, `.venv/`, `env/`
- `.env` (but NOT `.env.example`)
- `__pycache__/`, `*.pyc`
- `.ipynb_checkpoints/`
- `*.db`, `*.sqlite`, `*.sqlite3`
- `chroma_db/`, `faiss.index/`
- `output/`
- `.claude/` (local IDE settings)

Report any missing entries.

### 3. .env.example
Check if `.env.example` exists. Verify:
- All environment variables used in the code (`os.getenv(...)`) have a corresponding placeholder entry
- No real values — only placeholders like `"your-key-here"`
- Instructions at top on how to copy it

### 4. README.md
Check if `README.md` exists at root. Verify it contains:
- Project title and description
- Setup instructions (venv, pip install, .env setup)
- How to run the project
- List of required API keys/services

### 5. Project Structure
- Is `venv/` or `.venv/` present and committed? (bad — should be gitignored)
- Are any `.env` files with real values present?
- Are generated files committed (chroma_db, faiss.index, *.db, __pycache__)?
- Is `requirements.txt` present?

### 6. Git History Check
If this is a git repo, check recent commits for any accidental secret exposure:
`git log --oneline -10`

## Output Format

Produce a table:

| Check | Status | Action Required |
|---|---|---|
| Secret Scan | PASS/FAIL | details |
| .gitignore | PASS/WARN/FAIL | missing entries |
| .env.example | PASS/WARN/FAIL | details |
| README.md | PASS/WARN/FAIL | what's missing |
| Project Structure | PASS/WARN/FAIL | details |
| Git History | PASS/WARN | details |

Then list all **ACTION ITEMS** in priority order (CRITICAL first).

If $ARGUMENTS is provided, treat it as a specific subdirectory or file to focus on.
