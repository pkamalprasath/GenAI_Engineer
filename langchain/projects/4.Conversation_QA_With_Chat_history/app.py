"""
Conversational RAG with PDF Uploads + Chat History (Streamlit + LangChain + Chroma + Groq)

OVERVIEW
--------
This app implements a Conversational Retrieval-Augmented Generation (RAG) workflow:
1) User uploads one or more PDFs.
2) PDFs are loaded into LangChain Document objects (typically one per page).
3) Documents are split into overlapping text chunks for better retrieval quality.
4) Each chunk is embedded (vectorized) using a HuggingFace embedding model.
5) Chunks + embeddings are stored in a Chroma vector store.
6) When the user asks a question:
   a) A "history-aware" step rewrites the question into a standalone query using chat history.
   b) The standalone query retrieves relevant chunks from Chroma.
   c) The LLM answers using ONLY the retrieved chunks (context) while remaining conversational.
7) Chat history is stored per session_id in Streamlit session_state so follow-ups work.

KEY COMPONENTS
--------------
- Streamlit UI:
  - Text input for Groq API key
  - Session ID input to isolate conversations
  - PDF uploader (multiple files)
  - User question input + assistant response display

- PDF Ingestion:
  - Each uploaded PDF is written to a temporary file on disk.
  - PyPDFLoader reads the PDF and returns a list[Document].
  - All Documents across PDFs are appended into a single 'documents' list.

- Chunking:
  - RecursiveCharacterTextSplitter breaks documents into chunks with overlap.
  - Overlap preserves continuity across chunk boundaries (important for semantic retrieval).

- Embeddings + Vector Store:
  - HuggingFaceEmbeddings converts each chunk into a dense vector.
  - Chroma stores vectors + original chunk text for similarity search.

- Conversational Retrieval:
  - create_history_aware_retriever:
      Uses an LLM prompt that includes chat_history + current user input to rewrite
      follow-up questions (e.g., "What about that?") into standalone queries.
      This improves retrieval relevance dramatically.
  - create_retrieval_chain:
      Runs retrieval first, then sends retrieved context into the answering chain.

- Answering:
  - create_stuff_documents_chain:
      "Stuff" means all retrieved chunks are concatenated into a single {context}
      field in the prompt, then the LLM generates an answer.
  - The system prompt enforces concise responses (max 3 sentences) and "don't know"
    behavior when the answer isn't in the retrieved context.

- Chat History (Session Memory):
  - st.session_state.store is a dictionary keyed by session_id.
  - Each session_id maps to a ChatMessageHistory instance.
  - RunnableWithMessageHistory automatically:
      - injects chat_history into prompts via MessagesPlaceholder("chat_history")
      - appends the new user/assistant messages after each invocation

NOTES / COMMON PITFALLS
-----------------------
- Temporary file handling:
  - The code writes every uploaded file to './temp.pdf'.
  - With multiple PDFs or Streamlit reruns, this can overwrite files and cause flaky behavior.
  - Prefer unique temp paths (e.g., f"./temp_{uploaded_file.name}") or tempfile.NamedTemporaryFile.

- Empty/Scanned PDFs:
  - If the PDF has no extractable text (scanned images), chunking can produce empty splits.
  - This leads to embedding/upsert errors in Chroma. Add guards to stop early when no text exists.

- Rebuilding vector store:
  - Streamlit reruns the script often; rebuilding Chroma each time can be slow.
  - For production, cache/store the vectorstore in st.session_state and rebuild only on new upload.

DATA FLOW SUMMARY (MENTAL MODEL)
--------------------------------
Upload PDFs -> Load Documents -> Split into chunks -> Embed -> Store in Chroma
User question -> (Rewrite with history) -> Retrieve chunks -> Answer using {context} -> Save history

"""


import os
import streamlit as st  
from dotenv import load_dotenv
load_dotenv() 

from langchain_community.document_loaders import PyPDFLoader # For loading the PDF as import file 
from langchain_text_splitters import RecursiveCharacterTextSplitter # Text processing 

from langchain_groq import ChatGroq # For llm GROQ open source model importing 
from langchain_huggingface import HuggingFaceEmbeddings # Embedding creation 

from langchain_community.vectorstores import Chroma # to store the embedding for similarity search 
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_classic.chains import create_retrieval_chain,create_history_aware_retriever 
from langchain_core.runnables.history import RunnableWithMessageHistory


os.environ["HF_TOKEN"]=os.getenv("HF_TOKEN")
embeddings=HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2") 

st.title("Conversational RAG with PDF uploads and chat history")
st.write("upload the pdf's and chat with their content")

api_key=st.text_input("Enter the GROQ API key:",type="password")

if api_key:
    llm=ChatGroq(groq_api_key=api_key,model='llama-3.1-8b-instant')
    ## chat interface

    session_id=st.text_input("Session ID",value="default_session")
    ## statefully manage chat history
    if 'store' not in st.session_state:
        st.session_state.store={}

    uploaded_files=st.file_uploader("Choose A PDf file",type="pdf",accept_multiple_files=True)

    # Streamlit gives you a PDF in memory → you save it temporarily → LangChain reads it like a normal file.
    if uploaded_files:
        documents=[]
        for uploaded_file in uploaded_files: 
            temppdf=f"./temp.pdf"    
            with open(temppdf,"wb") as file: 
                file.write(uploaded_file.getvalue())
                file_name=uploaded_file.name
            
            loader=PyPDFLoader(temppdf)
            docs=loader.load()
            documents.extend(docs)
            
    # Split and create embeddings for the documents
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=5000, chunk_overlap=500)
        splits = text_splitter.split_documents(documents)
        vectorstore = Chroma.from_documents(documents=splits, embedding=embeddings)
        retriever = vectorstore.as_retriever()  

        contextualize_q_system_prompt=(
            "Given a chat history and the latest user question"
            "which might reference context in the chat history, "
            "formulate a standalone question which can be understood "
            "without the chat history. Do NOT answer the question, "
            "just reformulate it if needed and otherwise return it as is."
        )

        contextualize_q_prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", contextualize_q_system_prompt),
                    MessagesPlaceholder("chat_history"),
                    ("human", "{input}"),
                ]
            )
        
            # Step A — Rewrite
            # It calls the LLM with contextualize_q_prompt to output a standalone query.
            # Step B — Retrieve
            # It sends that rewritten query into your retriever (Chroma similarity search) 
            # to fetch relevant chunks.
            # user question + chat history → LLM rewrites → retriever 
        history_aware_retriever=create_history_aware_retriever(llm,retriever,contextualize_q_prompt)

        # Answer question
        system_prompt = (
                "You are an assistant for question-answering tasks. "
                "Use the following pieces of retrieved context to answer "
                "the question. If you don't know the answer, say that you "
                "don't know. Use three sentences maximum and keep the "
                "answer concise."
                "\n\n"
                "{context}"
            )
        qa_prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", system_prompt),
                    MessagesPlaceholder("chat_history"),
                    ("human", "{input}"),
                ]
            )
        # All retrieved chunks are stuffed directly into {context}
        question_answer_chain=create_stuff_documents_chain(llm,qa_prompt) 
        rag_chain=create_retrieval_chain(history_aware_retriever,question_answer_chain)
        #This block defines the answering rules and structure, telling the LLM 
        # to answer concisely using only retrieved PDF context while staying conversational via chat history.

        def get_session_history(session:str)->BaseChatMessageHistory:
            if session_id not in st.session_state.store:
                st.session_state.store[session_id]=ChatMessageHistory()
            return st.session_state.store[session_id] 
        
        conversational_rag_chain=RunnableWithMessageHistory(
            rag_chain,get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
            output_messages_key="answer"
        )
        user_input = st.text_input("Your question:")
        if user_input:
            session_history=get_session_history(session_id)
            response = conversational_rag_chain.invoke(
                {"input": user_input},
                config={
                    "configurable": {"session_id":session_id}
                },  # constructs a key "abc123" in `store`.
            )
            st.write(st.session_state.store)
            st.write("Assistant:", response['answer'])
            st.write("Chat History:", session_history.messages)
else:
    st.warning("Please enter the GRoq API Key")