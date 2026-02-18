"""
This Streamlit application implements a simple Retrieval-Augmented Generation (RAG) pipeline
for querying PDF research papers using a Large Language Model (LLM).

High-level flow:
1. Load environment variables and initialize API keys.
2. Load PDF documents from a local directory.
3. Split large documents into smaller overlapping chunks.
4. Convert document chunks into vector embeddings.
5. Store embeddings in a FAISS vector database for similarity search.
6. Accept a user query through the Streamlit UI.
7. Retrieve the most relevant document chunks based on semantic similarity.
8. Pass the retrieved context to an LLM (Groq – LLaMA 3.1) using a prompt template.
9. Generate an answer strictly based on the retrieved context.
10. Display the answer and optionally show the matched document chunks.

Key components used:
- Streamlit: UI for interaction and session state management
- PyPDFDirectoryLoader: Loads PDFs from a folder
- RecursiveCharacterTextSplitter: Splits documents into manageable chunks
- OpenAIEmbeddings: Converts text into numerical vectors
- FAISS: Stores and searches vectors efficiently
- ChatGroq: LLM used for generating answers
- Retrieval + Stuff Documents Chain: Combines retrieval and LLM reasoning

Important notes:
- The vector database is built only once per session and stored in Streamlit session_state.
- The LLM is instructed to answer only using the retrieved context to avoid hallucinations.
- Document similarity results are shown using a Streamlit expander for transparency.

Overall, this code demonstrates a basic but complete RAG-based document Q&A system
built with LangChain, FAISS, Groq LLMs, and Streamlit.

""" 

import os
import streamlit as st  
from dotenv import load_dotenv
load_dotenv() 

from langchain_community.document_loaders import PyPDFDirectoryLoader # For loading the PDF as import file 
from langchain_text_splitters import RecursiveCharacterTextSplitter # Text processing 
from langchain_openai import OpenAIEmbeddings # Embedding creation 
from langchain_community.vectorstores import FAISS # to store the embedding for similarity search 
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq # For llm GROQ open source model importing 
from langchain_classic.chains import create_retrieval_chain 

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")
groq_api_key=os.getenv("GROQ_API_KEY")
model=ChatGroq(groq_api_key=groq_api_key,model='llama-3.1-8b-instant')


prompt=ChatPromptTemplate.from_template(
    """ 
    Answer the questions based on the provided context only.
    please provide the most accurate response based on the question
    <context>
    {context}
    </context>
    Question:{input}
     
        
    """
)

def create_vector_embedding(): 
    if "vectors" not in st.session_state:
        st.session_state.embeddings=OpenAIEmbeddings()
        st.session_state.loader=PyPDFDirectoryLoader("research_papers") # Data ingestion 
        st.session_state.docs=st.session_state.loader.load() # Load the all the documents 
        st.session_state.text_splitter=RecursiveCharacterTextSplitter(chunk_size=1000,chunk_overlap=100) 
        st.session_state.final_documents=st.session_state.text_splitter.split_documents(st.session_state.docs[:50])
        st.session_state.vectors=FAISS.from_documents(st.session_state.final_documents,st.session_state.embeddings)

user_prompt=st.text_input("Enter your query from the research paper")
if st.button("Document Embedding"): 
    create_vector_embedding()
    st.write("Vector database is ready")

import time
if user_prompt : 
    st.error("Click 'Document Embedding' first to build the vector database.")
    st.stop()
    document_chain=create_stuff_documents_chain(model,prompt)
    retriever=st.session_state.vectors.as_retriever()
    retriver_chain=create_retrieval_chain(retriever,document_chain)

    start=time.process_time()
    response=retriver_chain.invoke({'input':user_prompt})
    print(f"Response time :{time.process_time()- start}")
    st.write(response['answer'])    

## With a streamlit expander 

    with st.expander("Document similarity search"):
        for i,doc in enumerate(response['context']):
            st.write(doc.page_content)
            st.write('----------------------------') 