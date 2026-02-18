# Claude Code — Skills, Rules, Agents & Commands

Reusable Claude Code slash commands, architectural patterns, and development rules
built from real GenAI projects (LangChain, Slack Bot, AI Guardrails).

Plug these into any project's `.claude/` folder or the global `~/.claude/` folder.

## What's Inside

```
claude_skill_rules_agents/
├── CLAUDE.md                        # Global rules & context (auto-loaded every session)
├── commands/                        # Slash commands — invoke with /command-name
│   ├── langchain-new.md             # Scaffold new LangChain project
│   ├── rag-scaffold.md              # Build complete RAG pipeline
│   ├── agent-scaffold.md            # Scaffold LangGraph / CrewAI agent
│   ├── slack-bot-new.md             # Scaffold Slack Bolt bot
│   ├── genai-readme.md              # Auto-generate README for any GenAI project
│   ├── github-ready.md              # Full GitHub audit (secrets, gitignore, README)
│   ├── github-push.md               # Push project into subfolder of any GitHub repo
│   ├── secret-scan.md               # Deep scan for hardcoded secrets
│   ├── env-setup.md                 # Scan code and create .env.example + .gitignore
│   ├── add-agent-tool.md            # Add tool to agent ToolRegistry
│   ├── add-scheduler-job.md         # Add APScheduler periodic background job
│   ├── debug-agent-tools.md         # 7-step debug process for broken agent tools
│   ├── bug-hunter.md                # Systematically find and document all bugs
│   └── integration-tester.md        # Create async integration test suite
├── patterns/                        # Architectural pattern guides
│   ├── error-handling-strategy.md   # Layered error handling: tools→services→listeners→jobs
│   ├── shared-state-management.md   # Dependency injection for stateful components
│   └── testing-async-services.md    # 10 patterns for testing async Python + AI
└── rules/                           # Critical rules learned from production
    ├── slack-bot-development.md      # 10 rules for Slack + Agent bots
    └── fastmcp-integration.md        # Why @mcp.tool() breaks imports and the fix
```

## How to Use

### Option 1: Global (applies to ALL projects)
```bash
# Copy to global .claude folder
cp -r commands/ ~/.claude/commands/
cp -r patterns/ ~/.claude/patterns/
cp -r rules/ ~/.claude/rules/
cp CLAUDE.md ~/.claude/CLAUDE.md
```

### Option 2: Per-project
```bash
# Copy into a specific project
cp -r commands/ my-project/.claude/commands/
cp CLAUDE.md my-project/.claude/CLAUDE.md
```

### Option 3: Windows (PowerShell)
```powershell
Copy-Item -Recurse commands/ $env:USERPROFILE\.claude\commands\
Copy-Item -Recurse patterns/ $env:USERPROFILE\.claude\patterns\
Copy-Item -Recurse rules/ $env:USERPROFILE\.claude\rules\
Copy-Item CLAUDE.md $env:USERPROFILE\.claude\CLAUDE.md
```

## Slash Commands Reference

| Command | Usage | What it does |
|---|---|---|
| `/langchain-new` | `/langchain-new <name> [type]` | Scaffold chatbot/rag/agent/api project |
| `/rag-scaffold` | `/rag-scaffold [vector-store] [llm]` | Full RAG pipeline with chosen stack |
| `/agent-scaffold` | `/agent-scaffold <name> [--type langgraph]` | LangGraph / LangChain / CrewAI agent |
| `/slack-bot-new` | `/slack-bot-new <name> [--socket]` | Slack Bolt bot with handlers + checklist |
| `/genai-readme` | `/genai-readme [--overwrite]` | Auto-detect project type, generate README |
| `/github-ready` | `/github-ready` | Audit: secrets, gitignore, README, history |
| `/github-push` | `/github-push <url> <subfolder>` | Push project into a GitHub repo subfolder |
| `/secret-scan` | `/secret-scan` | Find hardcoded API keys in all files |
| `/env-setup` | `/env-setup [provider]` | Scan code for env vars, create .env.example |
| `/add-agent-tool` | `/add-agent-tool` | Step-by-step: add tool to ToolRegistry |
| `/add-scheduler-job` | `/add-scheduler-job` | Add APScheduler job with correct patterns |
| `/debug-agent-tools` | `/debug-agent-tools` | 7-step checklist for broken agent tools |
| `/bug-hunter` | `/bug-hunter` | Full codebase bug hunt → PROBLEMS.md |
| `/integration-tester` | `/integration-tester` | Generate async integration test suite |

## Key Rules (CLAUDE.md highlights)

- **Never hardcode secrets** — always `os.getenv()` + `load_dotenv()`
- **On Windows**: bash is unreliable → use Python subprocess for git/file ops
- **LangChain**: use LCEL `prompt | llm | parser`, not legacy `LLMChain`
- **LangGraph**: always `Annotated[list, add_messages]` for message state
- **Slack**: `app_mention` not `message`, always include `next` in middleware
- **MCP**: never import `@mcp.tool()` decorated functions directly — use SDK
- **Shared state**: inject stateful components (MemoryManager, DB) via constructor
- **Agent tools**: return `{"success": False, "error": "..."}`, never raise exceptions

## Projects That Generated These Skills

| Project | Skills Generated |
|---|---|
| LangChain Mastery (12 notebooks + 16 projects) | `/langchain-new`, `/rag-scaffold`, `/agent-scaffold`, `/env-setup`, CLAUDE.md LangChain + LangGraph patterns |
| open_claw_slack_bot (Slack AI Agent) | `/slack-bot-new`, `/add-agent-tool`, `/add-scheduler-job`, `/debug-agent-tools`, `/bug-hunter`, `/integration-tester`, patterns/, rules/ |
| AI Guardrails (8 modules) | `/github-ready`, `/secret-scan`, `/github-push`, `/genai-readme` |
