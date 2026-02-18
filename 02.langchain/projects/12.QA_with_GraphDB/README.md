# Q&A with Graph Database (LangChain + Neo4j)

Experiments demonstrating how to query a Neo4j graph database using natural language, with LangChain converting questions into Cypher queries automatically.

## Overview

Graph databases model relationships between entities more naturally than relational databases. This project uses `GraphCypherQAChain` to let an LLM generate Cypher queries from plain English and retrieve graph-structured answers.

## Architecture

```
Natural language question
    ↓
LLM generates Cypher query (via GraphCypherQAChain)
    ↓
Cypher executed against Neo4j
    ↓
Graph results returned
    ↓
LLM formats into natural language answer
```

## Tech Stack

| Component | Technology |
|---|---|
| Graph Database | Neo4j (cloud — Neo4j Aura) |
| Query Language | Cypher |
| Framework | LangChain |
| LLM | OpenAI |
| Integration | `GraphCypherQAChain` |
| Notebook | Jupyter |

## Project Structure

```
12.QA_with_GraphDB/
├── experiments.ipynb
├── .env.example
└── README.md
```

## Setup

```bash
# 1. Copy and fill in your Neo4j and OpenAI credentials
cp .env.example .env

# 2. Install dependencies (from repo root)
pip install -r requirements.txt

# 3. Launch Jupyter
jupyter notebook experiments.ipynb
```

## Environment Variables

See [.env.example](.env.example).

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | LLM for Cypher generation |
| `NEO4J_URI` | Neo4j connection URI |
| `NEO4J_USERNAME` | Neo4j username |
| `NEO4J_PASSWORD` | Neo4j password |

## Key Concepts

- **`GraphCypherQAChain`** — automatically generates and executes Cypher from natural language
- **Schema-aware** — LangChain reads your graph schema to generate valid queries
- **Neo4j Aura** — managed cloud Neo4j (free tier available at [console.neo4j.io](https://console.neo4j.io))
- Graph DBs excel at relationship queries: "Who knows who?", "What is connected to X?"
