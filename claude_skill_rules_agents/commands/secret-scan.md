Scan the current project for hardcoded secrets, API keys, tokens, and sensitive credentials.

## What to Scan

Search all files EXCEPT: `venv/`, `.venv/`, `node_modules/`, `.git/`, `*.example`

### Patterns to Search For

| Type | Pattern | Providers |
|---|---|---|
| OpenAI key | `sk-proj-[a-zA-Z0-9]`, `sk-[a-zA-Z0-9]{48}` | OpenAI |
| LangSmith | `lsv2_pt_[a-zA-Z0-9]` | LangChain |
| HuggingFace | `hf_[a-zA-Z0-9]{30,}` | HuggingFace |
| Groq | `gsk_[a-zA-Z0-9]{50,}` | Groq |
| Pinecone | `pcsk_[a-zA-Z0-9]` | Pinecone |
| AstraDB | `AstraCS:` | DataStax |
| AWS | `AKIA[A-Z0-9]{16}` | AWS |
| Slack Bot | `xoxb-[0-9]` | Slack |
| Slack App | `xoxp-`, `xapp-` | Slack |
| Anthropic | `sk-ant-[a-zA-Z0-9]` | Anthropic |
| Generic assignment | `api_key\s*=\s*["'][^"']{20,}["']` | Generic |
| Generic token | `token\s*=\s*["'][^"']{20,}["']` | Generic |
| Generic password | `password\s*=\s*["'][^"']{8,}["']` | Generic |

### Special: Jupyter Notebooks (.ipynb)
These are JSON files — scan BOTH:
1. `source` arrays in cells (the code)
2. `outputs` arrays (printed results — secrets can appear in output!)

## For Each Finding Report

- **File**: relative path
- **Line**: line number
- **Type**: what kind of secret
- **Severity**: CRITICAL / HIGH / MEDIUM
- **Fix**: replace with `os.getenv("KEY_NAME")`

## Auto-Fix Option

If `$ARGUMENTS` is `--fix`, automatically replace any found hardcoded secrets with `os.getenv()` calls and report what was changed. Also add the variable name to `.env.example` if it's not already there.

## Summary

End with:
- Total secrets found
- Files affected
- Whether git history needs cleaning (if `.git` exists and secrets were in previous commits)
- Recommended next steps

If no secrets found: confirm "CLEAN — no secrets detected in tracked files."
