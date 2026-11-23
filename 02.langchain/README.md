# 02. LangChain: LLM application labs

Course notebooks and small projects on building LLM applications with LangChain: loaders, splitters, embeddings, vector stores, LCEL, conversational RAG, summarisation, tool-using agents, LangGraph, and a few related tools (CrewAI, PEFT, Amazon Bedrock).

**Source:** Built while following the Udemy course *Complete Generative AI Course With LangChain and Hugging Face* (completed 20 Jan 2026). These are course labs; notebook outputs have been cleared.

## Concept notebooks

| # | Notebook | Topic |
|---|---|---|
| 01 | `01_data_ingestion.ipynb` | Document loaders (text, PDF, web) |
| 02 | `02_text_splitter.ipynb` | Character, recursive, HTML-header and JSON splitters |
| 03 | `03_embeddings.ipynb` | OpenAI, Ollama and Hugging Face embeddings |
| 04 | `04_chatbot.ipynb` | Chatbot with message history (Groq) |
| 05 | `05_chat_prompts.ipynb` | Prompt templates and output parsers |
| 06 | `06_chroma_db.ipynb` | Chroma vector store |
| 07 | `07_conversational_qa.ipynb` | Conversational RAG with a history-aware retriever |
| 08 | `08_faiss.ipynb` | FAISS vector store |
| 09 | `09_lcel.ipynb` | LangChain Expression Language |
| 10 | `10_summarization.ipynb` | Stuff, map-reduce and refine summarisation |
| 11 | `11_tool_agents.ipynb` | Agents with Arxiv, Wikipedia and retriever tools |
| 12 | `12_genai_project_1.ipynb`, `12_genai_project_2.py` | Small end-to-end RAG project and an Ollama Streamlit app |

Details: [notebooks/README.md](./notebooks/README.md). `01.server.py` serves a Groq chain with LangServe and FastAPI.

## Projects

| # | Project | Stack (from the code) | What it does |
|---|---|---|---|
| 01 | [QA chatbot (OpenAI)](./projects/01.QA_ChatBot_WithOpenAI/) | `ChatOpenAI` · Streamlit | Chatbot with model selection; no document retrieval |
| 02 | [QA chatbot (Ollama)](./projects/02.QA_ChatBot_WithOllama/) | Ollama · Streamlit | Local-model chatbot, no API key needed |
| 03 | [Research-paper RAG (Groq)](./projects/03.QA_ChatBot_WithGroq/) | Groq · OpenAI embeddings · FAISS · Streamlit | Q&A over a folder of PDFs |
| 04 | [Conversational RAG](./projects/04.Conversation_QA_With_Chat_history/) | Groq · Hugging Face embeddings · Chroma · Streamlit | PDF Q&A with chat history |
| 05 | [Tool-using chatbot](./projects/05.QA_ChatBot_Tool_based/) | Groq · Arxiv, Wikipedia, DuckDuckGo tools · Streamlit | Agent that picks a search tool |
| 06 | [SQL chatbot](./projects/06.QA_Chat_With_Sqldb/) | Groq · `SQLDatabase` (SQLite or MySQL) · Streamlit | Natural-language questions over a database |
| 07 | [Text summarisation](./projects/07.Text_Summarization/) | Groq · YouTube and URL loaders · Streamlit | Summarises a YouTube video or web page |
| 08 | [MathGPT](./projects/08.MathGPT/) | Groq · LangGraph ReAct agent · calculator and Wikipedia tools · Streamlit | Maths word-problem solver |
| 09 | [Hugging Face models](./projects/09.WithHuggingface/) | `HuggingFaceEndpoint` | Open models through the Hugging Face Hub |
| 10 | [CrewAI blog writer](./projects/10.crewai/) | CrewAI · OpenAI · YouTube channel search | Two agents: researcher and writer |
| 11 | [Hybrid search (Pinecone)](./projects/11.hybridSearch_with_PineConeDB/) | Pinecone · BM25 · Hugging Face embeddings | Sparse + dense retrieval |
| 12 | [Graph DB QA](./projects/12.QA_with_GraphDB/) | Neo4j · `GraphCypherQAChain` · Groq | Questions answered with generated Cypher |
| 13 | [Fine-tuning with PEFT](./projects/13.finetuning_peft/) | Hugging Face `peft` · `bitsandbytes` · Lamini | LoRA and QLoRA on `distilgpt2`; Lamini API tuning |
| 14 | [LangGraph chatbot](./projects/14.langgraph_chatbot/) | LangGraph · Groq · Arxiv and Wikipedia tools | Graph-based chatbot with a tool-calling loop |
| 15 | [Amazon Bedrock (Nova)](./projects/15.aws_bedrock_nova/) | `boto3` · Amazon Nova 2 Lite · Nova Canvas | Text and image generation on Bedrock |
| 16 | [PDF query (Cassandra)](./projects/16.pdf_query_cassandra/) | `cassio` · Astra DB (Cassandra) · OpenAI · PyPDF2 | PDF Q&A in a notebook |

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # fill in the keys each notebook or project needs
```
