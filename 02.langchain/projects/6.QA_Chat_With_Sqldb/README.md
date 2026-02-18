# Chat with SQL Database (LangChain + Groq + Streamlit)

A natural language interface for querying SQL databases — type a question in plain English and get SQL-powered answers.

## Overview

Uses a LangChain SQL agent backed by a Groq LLM to convert natural language questions into SQL queries and return results. Supports both SQLite (local) and MySQL (remote) databases.

## Tech Stack

| Component | Technology |
|---|---|
| UI | Streamlit |
| LLM | Groq (`llama-3.1-8b-instant`) |
| Framework | LangChain |
| Database (local) | SQLite (`student.db`) |
| Database (remote) | MySQL |
| Agent | `SQLDatabaseToolkit` + LangChain agent |

## Project Structure

```
6.QA_Chat_With_Sqldb/
├── app.py          # Main Streamlit app
├── Sqlite.py       # Script to create the student.db SQLite database
└── README.md
```

## Setup

```bash
# 1. Generate the sample SQLite database
python Sqlite.py

# 2. Install dependencies (from repo root)
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py
```

Enter your Groq API key in the sidebar, then choose either the local SQLite database or connect to MySQL.

## How It Works

```
User natural language question
    ↓
Groq LLM + SQLDatabaseToolkit
    ↓
LLM generates SQL query
    ↓
Query executed against SQLite / MySQL
    ↓
Results formatted into natural language answer
    ↓
Displayed in Streamlit chat UI
```

## Database Options

| Option | Details |
|---|---|
| SQLite (local) | Uses `student.db` — created by running `Sqlite.py` |
| MySQL (remote) | Provide host, user, password, database name in sidebar |

## Key Learnings

- `SQLDatabaseToolkit` gives the LLM schema awareness and query execution
- SQLite runs in read-only mode (`mode=ro`) for safety
- The agent handles multi-step reasoning: inspect schema → generate SQL → execute → format answer
- `@st.cache_resource` caches the database connection to avoid reconnecting on every rerun
