# Notebooks — LangChain Concepts

Step-by-step tutorial notebooks covering core LangChain concepts. Work through them in order for a structured learning path.

## Learning Path

| # | Notebook | Concept | Key Classes |
|---|---|---|---|
| 01 | [01_data_ingestion.ipynb](01_data_ingestion.ipynb) | Document loaders | `WebBaseLoader`, `PyPDFLoader`, `WikipediaLoader` |
| 02 | [02_text_splitter.ipynb](02_text_splitter.ipynb) | Chunking strategies | `RecursiveCharacterTextSplitter`, `CharacterTextSplitter` |
| 03 | [03_embeddings.ipynb](03_embeddings.ipynb) | Vector embeddings | `OpenAIEmbeddings`, `HuggingFaceEmbeddings` |
| 04 | [04_chatbot.ipynb](04_chatbot.ipynb) | Basic chatbot with memory | `ChatGroq`, `ChatMessageHistory` |
| 05 | [05_chat_prompts.ipynb](05_chat_prompts.ipynb) | Prompt engineering | `ChatPromptTemplate`, `SystemMessage`, `HumanMessage` |
| 06 | [06_chroma_db.ipynb](06_chroma_db.ipynb) | ChromaDB vector store | `Chroma`, similarity search, persistence |
| 07 | [07_faiss.ipynb](07_faiss.ipynb) | FAISS vector store | `FAISS`, `save_local`, `load_local` |
| 08 | [08_lcel.ipynb](08_lcel.ipynb) | LangChain Expression Language | `\|` operator, `RunnablePassthrough`, `RunnableLambda` |
| 09 | [09_conversational_qa.ipynb](09_conversational_qa.ipynb) | Conversational RAG | `create_history_aware_retriever`, `RunnableWithMessageHistory` |
| 10 | [10_summarization.ipynb](10_summarization.ipynb) | Summarization chains | `load_summarize_chain`, stuff / map-reduce / refine |
| 11 | [11_tool_agents.ipynb](11_tool_agents.ipynb) | Agents with tools | `create_react_agent`, `AgentExecutor`, tool decorators |
| 12 | [12_genai_project_1.ipynb](12_genai_project_1.ipynb) | End-to-end project | Full pipeline combining multiple concepts |

## Setup

From the repo root:

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your API keys
jupyter notebook
```

## Concept Dependency Map

```
01 Data Ingestion
    ↓
02 Text Splitting
    ↓
03 Embeddings
    ↓
06 ChromaDB / 07 FAISS (vector stores)
    ↓
09 Conversational QA (RAG + memory)

05 Prompts → 04 Chatbot → 08 LCEL → 11 Agents
                                          ↓
                                    10 Summarization
```
