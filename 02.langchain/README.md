# LangChain Mastery

A comprehensive learning repository covering LangChain, LLM integrations, vector databases, agents, and production-ready GenAI application development.

## Topics Covered

| # | Notebook | Concept |
|---|----------|---------|
| 01 | `notebooks/01_data_ingestion.ipynb` | Document loaders, web scraping, PDF ingestion |
| 02 | `notebooks/02_text_splitter.ipynb` | Recursive, character, token-based text splitting |
| 03 | `notebooks/03_embeddings.ipynb` | OpenAI & HuggingFace embeddings |
| 04 | `notebooks/04_chatbot.ipynb` | Basic chatbot with memory |
| 05 | `notebooks/05_chat_prompts.ipynb` | ChatPromptTemplate, SystemMessage, HumanMessage |
| 06 | `notebooks/06_chroma_db.ipynb` | ChromaDB vector store — store, retrieve, similarity search |
| 07 | `notebooks/07_faiss.ipynb` | FAISS vector store — local, fast similarity search |
| 08 | `notebooks/08_lcel.ipynb` | LangChain Expression Language (LCEL) chains |
| 09 | `notebooks/09_conversational_qa.ipynb` | Conversational retrieval with chat history |
| 10 | `notebooks/10_summarization.ipynb` | Stuff, Map-Reduce, Refine summarization |
| 11 | `notebooks/11_tool_agents.ipynb` | Agents with tools (Wikipedia, Arxiv, DuckDuckGo) |
| 12 | `notebooks/12_genai_project_1.ipynb` | End-to-end GenAI project notebook |

## Projects

| # | Project | Stack |
|---|---------|-------|
| 01 | [QA Chatbot — OpenAI](projects/1.QA_ChatBot_WithOpenAI/) | Streamlit + OpenAI + LangChain |
| 02 | [QA Chatbot — Ollama](projects/2.QA_ChatBot_WithOllama/) | Streamlit + Ollama (local LLMs) |
| 03 | [QA Chatbot — Groq](projects/3.QA_ChatBot_WithGroq/) | Streamlit + Groq + PDF RAG |
| 04 | [Conversational QA with History](projects/4.Conversation_QA_With_Chat_history/) | Multi-turn QA + session memory |
| 05 | [Tool-based QA Agent](projects/5.QA_ChatBot_Tool_based/) | ReAct agent with search tools |
| 06 | [SQL Database QA](projects/6.QA_Chat_With_Sqldb/) | Natural language to SQL |
| 07 | [Text Summarization](projects/7.Text_Summarization/) | Stuff / Map-Reduce / Refine chains |
| 08 | [MathGPT](projects/8.MathGPT/) | Math reasoning with LLM + tools |
| 09 | [HuggingFace Integration](projects/9.WithHuggingface/) | Open-source LLMs via HuggingFace Hub |
| 10 | [CrewAI Multi-Agent](projects/10.crewai/) | Multi-agent workflow with CrewAI |
| 11 | [Hybrid Search — PineconeDB](projects/11.hybridSearch_with_PineConeDB/) | BM25 + dense vector hybrid retrieval |
| 12 | [Graph DB QA](projects/12.QA_with_GraphDB/) | Neo4j + LangChain GraphCypherQAChain |
| 13 | [Fine-Tuning (LoRA / QLoRA / Lamini)](projects/13.FineTunning_Techniques/) | PEFT fine-tuning techniques |
| 14 | [LangGraph Chatbot](projects/14.QA_chatbot_WithLangraph/) | Stateful agents with LangGraph |
| 15 | [AWS Bedrock](projects/15.AWS_BEDROCK/) | Claude / Titan via Amazon Bedrock |
| 16 | [PDF Query](projects/PDFQuery_LangChain/) | RAG over PDF documents |

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/langchain-mastery.git
cd langchain-mastery
```

### 2. Create a virtual environment

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
# Edit .env and fill in your API keys
```

### 5. Launch Jupyter

```bash
jupyter notebook
```

## API Keys Required

| Provider | Purpose | Get Key |
|----------|---------|---------|
| OpenAI | GPT models | [platform.openai.com](https://platform.openai.com/api-keys) |
| LangSmith | Tracing & monitoring | [smith.langchain.com](https://smith.langchain.com) |
| HuggingFace | Open-source models | [huggingface.co](https://huggingface.co/settings/tokens) |
| Groq | Fast inference | [console.groq.com](https://console.groq.com/keys) |
| Neo4j | Graph database | [console.neo4j.io](https://console.neo4j.io) |
| Pinecone | Vector database | [app.pinecone.io](https://app.pinecone.io) |
| AWS | Bedrock LLMs | [aws.amazon.com](https://aws.amazon.com) |

## Tech Stack

- **LangChain** — Core orchestration framework
- **LangGraph** — Stateful multi-step agent flows
- **CrewAI** — Multi-agent collaboration
- **Streamlit** — Web UI for chatbots
- **FastAPI + LangServe** — LLM API serving (`server.py`)
- **ChromaDB / FAISS / Pinecone** — Vector stores
- **Neo4j** — Graph database
- **HuggingFace** — Open-source model hub

## Repository Structure

```
langchain-mastery/
├── notebooks/          # Concept notebooks (tutorials)
├── projects/           # Full mini-applications
├── data/               # Sample PDFs and text files
├── assets/             # Images used in README/docs
├── server.py           # LangServe API server
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
└── .gitignore          # Git exclusion rules
```
