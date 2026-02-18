Scaffold a new LangChain Agent or LangGraph agentic workflow project with best-practice structure.

## Usage
`/agent-scaffold <project-name> [--type langchain|langgraph|crewai] [--ui streamlit|api|none]`

Defaults: `--type langgraph`, `--ui none`

## Steps to Perform

### 1. Determine Agent Type from $ARGUMENTS

Parse $ARGUMENTS for:
- `--type langchain` → Classic ReAct agent with tools (AgentExecutor)
- `--type langgraph` → LangGraph StateGraph (default — more control, production-ready)
- `--type crewai` → Multi-agent CrewAI system with sequential/hierarchical process
- `--ui streamlit` → Add Streamlit chat interface
- `--ui api` → Add FastAPI + LangServe endpoint

### 2. Create Project Structure

**For LangGraph (default):**
```
<project-name>/
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── main.py              # Entry point — runs the graph
├── graph/
│   ├── __init__.py
│   ├── state.py         # TypedDict State definition
│   ├── nodes.py         # All node functions
│   ├── edges.py         # Conditional edge logic
│   └── graph.py         # StateGraph assembly + compile()
├── tools/
│   ├── __init__.py
│   └── custom_tools.py  # @tool decorated functions
└── prompts/
    └── system.py        # Prompt templates
```

**For LangChain ReAct:**
```
<project-name>/
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── main.py
├── agent/
│   ├── __init__.py
│   ├── agent.py         # AgentExecutor setup
│   └── prompts.py
└── tools/
    ├── __init__.py
    └── custom_tools.py
```

**For CrewAI:**
```
<project-name>/
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── main.py
├── agents/
│   ├── __init__.py
│   └── crew_agents.py   # Agent definitions
├── tasks/
│   ├── __init__.py
│   └── crew_tasks.py    # Task definitions
└── tools/
    ├── __init__.py
    └── custom_tools.py
```

### 3. Generate requirements.txt

**LangGraph:**
```
langchain>=0.2.0
langchain-openai>=0.1.0
langchain-community>=0.2.0
langgraph>=0.1.0
python-dotenv>=1.0.0
openai>=1.30.0
```

**LangChain ReAct:**
```
langchain>=0.2.0
langchain-openai>=0.1.0
langchain-community>=0.2.0
python-dotenv>=1.0.0
openai>=1.30.0
```

**CrewAI:**
```
crewai>=0.30.0
langchain-openai>=0.1.0
python-dotenv>=1.0.0
openai>=1.30.0
```

Add if `--ui streamlit`:
```
streamlit>=1.35.0
```

Add if `--ui api`:
```
fastapi>=0.111.0
langserve>=0.2.0
uvicorn>=0.30.0
sse-starlette>=2.1.0
```

### 4. Generate .env.example

```bash
# ============================================================
# <Project Name> Agent — Environment Variables
# ============================================================

# --- OpenAI (required) ---
# Get from: https://platform.openai.com/api-keys
OPENAI_API_KEY="your-openai-api-key-here"

# --- LangChain / LangSmith (optional, for tracing) ---
# Get from: https://smith.langchain.com/settings
LANGCHAIN_API_KEY="your-langchain-api-key-here"
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT="<project-name>"
```

### 5. Generate graph/state.py (LangGraph only)

**CRITICAL RULES for LangGraph State:**
1. Always use `TypedDict` for the State class — not a dataclass or Pydantic model
2. Use `Annotated[list, add_messages]` for message lists — this enables automatic appending
3. The state dict is shared across all nodes — each node receives and returns it
4. Node functions MUST return a dict with only the keys they want to update

```python
from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """State shared across all graph nodes."""
    messages: Annotated[list, add_messages]   # Chat history — auto-appended
    next_step: str                             # Routing signal for conditional edges
    context: str                               # Accumulated context/research
    iteration: int                             # Loop counter for safety limits
```

### 6. Generate graph/nodes.py (LangGraph only)

```python
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from .state import AgentState
from prompts.system import SYSTEM_PROMPT

load_dotenv()

llm = ChatOpenAI(model="gpt-4o", temperature=0)

def agent_node(state: AgentState) -> dict:
    """Main reasoning node — calls LLM with current state."""
    messages = state["messages"]
    response = llm.invoke([SystemMessage(content=SYSTEM_PROMPT)] + messages)
    return {"messages": [response]}

def tool_node(state: AgentState) -> dict:
    """Execute tools based on last LLM message."""
    # Parse tool calls from last message and execute
    last_message = state["messages"][-1]
    # Add tool execution logic here
    return {"messages": [], "context": "tool result here"}

def final_node(state: AgentState) -> dict:
    """Format and return the final answer."""
    return {"next_step": "END"}
```

### 7. Generate graph/edges.py (LangGraph only)

```python
from .state import AgentState

MAX_ITERATIONS = 5

def should_continue(state: AgentState) -> str:
    """
    Conditional edge: decide what to do next.
    Returns the name of the next node, or END.
    """
    # Safety limit — prevent infinite loops
    if state.get("iteration", 0) >= MAX_ITERATIONS:
        return "final"

    last_message = state["messages"][-1]

    # If the last AI message has tool calls → go to tool node
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    # Otherwise → done
    return "final"
```

### 8. Generate graph/graph.py (LangGraph only)

```python
from langgraph.graph import StateGraph, START, END
from .state import AgentState
from .nodes import agent_node, tool_node, final_node
from .edges import should_continue

def build_graph():
    """Assemble and compile the LangGraph StateGraph."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("final", final_node)

    # Entry point
    graph.add_edge(START, "agent")

    # Conditional routing from agent node
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "final": "final",
        }
    )

    # After tools → back to agent
    graph.add_edge("tools", "agent")

    # Final → END
    graph.add_edge("final", END)

    return graph.compile()

# Compiled graph instance — import this in main.py
app = build_graph()
```

### 9. Generate tools/custom_tools.py

```python
from langchain_core.tools import tool

@tool
def search_web(query: str) -> str:
    """Search the web for information about the given query.

    Args:
        query: The search query string

    Returns:
        Search results as a formatted string
    """
    # Implement with DuckDuckGo, Tavily, SerpAPI, etc.
    return f"Search results for: {query}"

@tool
def calculate(expression: str) -> str:
    """Evaluate a mathematical expression.

    Args:
        expression: A valid Python math expression (e.g. '2 + 2 * 10')

    Returns:
        The result as a string
    """
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as e:
        return f"Error: {e}"
```

### 10. Generate main.py

**For LangGraph:**
```python
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from graph.graph import app

load_dotenv()

def run_agent(user_input: str) -> str:
    """Run the agent graph with a user message."""
    initial_state = {
        "messages": [HumanMessage(content=user_input)],
        "next_step": "",
        "context": "",
        "iteration": 0,
    }

    result = app.invoke(initial_state)
    return result["messages"][-1].content

if __name__ == "__main__":
    print("Agent ready. Type 'quit' to exit.\n")
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit", "q"):
            break
        if not user_input:
            continue
        response = run_agent(user_input)
        print(f"Agent: {response}\n")
```

**For CrewAI:**
```python
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI

load_dotenv()

llm = ChatOpenAI(model="gpt-4o", temperature=0)

# Define agents
researcher = Agent(
    role="Research Specialist",
    goal="Find accurate and comprehensive information",
    backstory="Expert researcher with deep web search skills",
    llm=llm,
    verbose=True,
)

writer = Agent(
    role="Content Writer",
    goal="Write clear, well-structured content based on research",
    backstory="Professional writer who turns research into readable content",
    llm=llm,
    verbose=True,
)

# Define tasks
research_task = Task(
    description="Research the topic: {topic}",
    agent=researcher,
    expected_output="A comprehensive research summary with key facts",
)

write_task = Task(
    description="Write a detailed report based on the research",
    agent=writer,
    expected_output="A well-structured, readable report",
)

# Assemble crew
crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, write_task],
    process=Process.sequential,
    verbose=True,
)

if __name__ == "__main__":
    result = crew.kickoff(inputs={"topic": "LangGraph vs LangChain Agents"})
    print(result)
```

### 11. Generate app.py (Streamlit UI — if `--ui streamlit`)

```python
import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from graph.graph import app as agent_graph

load_dotenv()

st.set_page_config(page_title="<Project Name> Agent", page_icon="🤖")
st.title("<Project Name> Agent")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Handle user input
if prompt := st.chat_input("Ask the agent..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Agent thinking..."):
            state = {"messages": [HumanMessage(content=prompt)], "next_step": "", "context": "", "iteration": 0}
            result = agent_graph.invoke(state)
            response = result["messages"][-1].content
        st.markdown(response)

    st.session_state.messages.append({"role": "assistant", "content": response})
```

### 12. Generate .gitignore

```
__pycache__/
*.py[cod]
venv/
.venv/
.env
.env.*
!.env.example
*.log
.idea/
.vscode/
.claude/
chroma_db/
*.faiss
*.pkl
```

### 13. Report

Show:
- Agent type selected: LangGraph / LangChain / CrewAI
- UI type: Streamlit / FastAPI / None
- All files created with paths
- How to run:
  - Script: `python main.py`
  - Streamlit: `streamlit run app.py`
  - API: `uvicorn app:app --reload`
- LangGraph architecture diagram (nodes → edges → compile flow)
- Next steps (implement tool logic, adjust prompts, add memory)
