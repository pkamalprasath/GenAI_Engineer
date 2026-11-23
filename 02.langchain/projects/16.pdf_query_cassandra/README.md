# PDF query with LangChain and Cassandra (Astra DB)

A course notebook that answers questions about a PDF using a vector store on Apache Cassandra (DataStax Astra DB, via `cassio`).

## Pipeline

```
budget_speech.pdf
    ↓  PyPDF2 PdfReader (text extraction)
    ↓  CharacterTextSplitter (chunking)
    ↓  OpenAIEmbeddings
    ↓  Cassandra vector store (Astra DB, via cassio)
    ↓  retriever
    ↓  RetrievalQA with the OpenAI LLM
answer, plus the top 4 chunks with similarity scores
```

The last cell is an interactive question loop in the notebook (not a web app).

## Files

```
16.pdf_query_cassandra/
├── 01.PDFQuery_LangChain.ipynb
├── budget_speech.pdf      sample document
└── README.md
```

## Setup

Set these in `.env` (see `../../.env.example`):

| Variable | Purpose |
|---|---|
| `ASTRA_DB_APPLICATION_TOKEN` | Astra DB token |
| `ASTRA_DB_ID` | Astra DB database ID |
| `OPENAI_API_KEY` | LLM and embeddings |

```bash
pip install -r ../../requirements.txt
jupyter notebook 01.PDFQuery_LangChain.ipynb
```

**Source:** course labs from the Udemy course *Complete Generative AI Course With LangChain and Hugging Face* (completed 20 Jan 2026).
