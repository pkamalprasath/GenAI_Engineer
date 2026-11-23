# Multi-Agent Blog Writer with CrewAI

A multi-agent system using CrewAI where a **Researcher** agent gathers information and a **Writer** agent produces a blog post — collaborating autonomously on any given topic.

## Overview

Demonstrates the CrewAI framework for orchestrating multiple AI agents that work together sequentially. Each agent has a defined role, goal, and set of tools.

## Agents

| Agent | Role | Tools |
|---|---|---|
| `blog_researcher` | Find videos on the topic in one YouTube channel | `YoutubeChannelSearchTool` |
| `blog_writer` | Write a well-structured blog post from the research | LLM generation |

## Tech Stack

| Component | Technology |
|---|---|
| Multi-Agent Framework | CrewAI |
| LLM Backend | OpenAI (`gpt-4.1-mini` via `ChatOpenAI`) |
| Process | Sequential (`Process.sequential`) |
| Memory | Enabled |
| Caching | Enabled |

## Project Structure

```
10.crewai/
├── app.py       # Entry point — creates crew and kicks off
├── agents.py    # Agent definitions (researcher, writer)
├── tasks.py     # Task definitions for each agent
├── tools.py     # YouTube channel search tool
└── README.md
```

## Setup

```bash
# Install dependencies (from repo root)
pip install -r requirements.txt

# Set the YouTube channel the researcher searches, then run the crew
export YOUTUBE_CHANNEL_URL="https://www.youtube.com/@channel-handle"
python app.py
```

The crew will run on the topic `'AI vs ML VS DL VS Data science'` by default. Change the `topic` in `app.py` to research any subject.

## How It Works

```
Topic input
    ↓
blog_researcher agent → searches the YouTube channel for the topic
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

**Source:** course labs from the Udemy course *Complete Generative AI Course With LangChain and Hugging Face* (completed 20 Jan 2026). The channel URL is read from the `YOUTUBE_CHANNEL_URL` environment variable.
