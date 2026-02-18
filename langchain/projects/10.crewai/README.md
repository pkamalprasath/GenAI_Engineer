# Multi-Agent Blog Writer with CrewAI

A multi-agent system using CrewAI where a **Researcher** agent gathers information and a **Writer** agent produces a blog post — collaborating autonomously on any given topic.

## Overview

Demonstrates the CrewAI framework for orchestrating multiple AI agents that work together sequentially. Each agent has a defined role, goal, and set of tools.

## Agents

| Agent | Role | Tools |
|---|---|---|
| `blog_researcher` | Find relevant, up-to-date information on the topic | Web search tools |
| `blog_writer` | Write a well-structured blog post from the research | LLM generation |

## Tech Stack

| Component | Technology |
|---|---|
| Multi-Agent Framework | CrewAI |
| LLM Backend | Configurable (OpenAI / Groq / etc.) |
| Process | Sequential (`Process.sequential`) |
| Memory | Enabled |
| Caching | Enabled |

## Project Structure

```
10.crewai/
├── app.py       # Entry point — creates crew and kicks off
├── agents.py    # Agent definitions (researcher, writer)
├── tasks.py     # Task definitions for each agent
├── tools.py     # Custom tools available to agents
└── README.md
```

## Setup

```bash
# Install dependencies (from repo root)
pip install -r requirements.txt

# Run the crew
python app.py
```

The crew will run on the topic `'AI vs ML VS DL VS Data science'` by default. Change the `topic` in `app.py` to research any subject.

## How It Works

```
Topic input
    ↓
blog_researcher agent → uses tools to gather information
    ↓
research_task result passed to next agent
    ↓
blog_writer agent → writes structured blog post
    ↓
Final blog post printed / saved
```

## Key Concepts

- **Agents** have a role, goal, and backstory that shape their behavior
- **Tasks** define what each agent must produce and in what format
- **Sequential process** means each task completes before the next starts
- **Memory** allows agents to recall previous interactions within a crew run
- **`max_rpm`** limits API calls per minute to avoid rate limiting

## Output

The generated blog post is printed to stdout. To save it, redirect output:

```bash
python app.py > output/blog.md
```
