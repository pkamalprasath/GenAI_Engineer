# 02. LangChain — LLM Application Development

End-to-end LangChain learning path covering everything from basic chains to production-grade agentic pipelines.

## Notebooks (Learning Path)

| # | Notebook | Topic |
|---|---|---|
| 01 | `01_data_ingestion.ipynb` | Document loaders, PDF/text ingestion |
| 02 | `02_text_splitter.ipynb` | Chunking strategies — recursive, semantic |
| 03 | `03_embeddings.ipynb` | OpenAI + HuggingFace embeddings |
| 04 | `04_chatbot.ipynb` | Basic LLM chain with memory |
| 05 | `05_chat_prompts.ipynb` | PromptTemplates, system/human messages |
| 06 | `06_chroma_db.ipynb` | ChromaDB vector store — store and retrieve |
| 07 | `07_conversational_qa.ipynb` | RAG with conversation history |
| 08 | `08_faiss.ipynb` | FAISS in-memory vector search |
| 09 | `09_lcel.ipynb` | LangChain Expression Language (pipe syntax) |
| 10 | `10_summarization.ipynb` | Map-reduce and stuff summarization chains |
| 11 | `11_tool_agents.ipynb` | ReAct agents with custom tools |
| 12 | `12_genai_project.ipynb` | End-to-end project combining all concepts |

[View Notebooks →](./notebooks/)

## Projects

| # | Project | Stack | Description |
|---|---|---|---|
| 01 | [QA ChatBot (OpenAI)](./projects/01.QA_ChatBot_WithOpenAI/) | OpenAI · ChromaDB · Streamlit | PDF Q&A chatbot |
| 02 | [QA ChatBot (Ollama)](./projects/02.QA_ChatBot_WithOllama/) | Ollama · FAISS · Streamlit | Local LLM chatbot — no API key needed |
| 03 | [QA ChatBot (Groq)](./projects/03.QA_ChatBot_WithGroq/) | Groq · FAISS | Ultra-fast inference with Groq API |
| 04 | [Conversational QA](./projects/04.Conversation_QA_With_Chat_history/) | OpenAI · ChromaDB | Multi-turn QA with full chat history |
| 05 | [Tool-Based Agent](./projects/05.QA_ChatBot_Tool_based/) | OpenAI · LangChain Tools | Agent that selects tools to answer queries |
| 06 | [SQL Chatbot](./projects/06.QA_Chat_With_Sqldb/) | SQLite · LangChain | Natural language to SQL queries |
| 07 | [Text Summarization](./projects/07.Text_Summarization/) | OpenAI · LangChain | Map-reduce summarization pipeline |
| 08 | [MathGPT](./projects/08.MathGPT/) | OpenAI · Wolfram · LangChain | Math problem solver with tool use |
| 09 | [HuggingFace Integration](./projects/09.WithHuggingface/) | HuggingFace · LangChain | Open-source models via HuggingFace Hub |
| 10 | [CrewAI Multi-Agent](./projects/10.crewai/) | CrewAI · OpenAI | Role-based multi-agent orchestration |
| 11 | [Hybrid Search (Pinecone)](./projects/11.hybridSearch_with_PineConeDB/) | Pinecone · BM25 | Sparse + dense hybrid retrieval |
| 12 | [GraphDB QA](./projects/12.QA_with_GraphDB/) | Neo4j · LangChain | Knowledge graph question answering |
| 13 | [Fine-Tuning Techniques](./projects/13.FineTunning_Techniques/) | HuggingFace PEFT · LoRA | Parameter-efficient fine-tuning |
| 14 | [LangGraph Agent](./projects/14.QA_chatbot_WithLangraph/) | LangGraph · OpenAI | Stateful agent with graph-based flow |
| 15 | [AWS Bedrock](./projects/15.AWS_BEDROCK/) | AWS Bedrock · Claude · Titan | Enterprise LLM deployment on AWS |
| 16 | [PDF Query](./projects/16.PDFQuery_LangChain/) | LangChain · FAISS · Streamlit | Production PDF Q&A app |

## Key Patterns Used

- **LCEL** — `prompt | llm | parser` pipe syntax throughout
- **RAG** — Load → Split → Embed → Store → Retrieve → Generate
- **Agents** — ReAct loop with custom tool definitions
- **Memory** — `ConversationBufferMemory` and `RunnableWithMessageHistory`

## Setup

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
# Fill in OPENAI_API_KEY and other keys
```
