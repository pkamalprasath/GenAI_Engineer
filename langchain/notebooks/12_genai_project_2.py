
import os
from dotenv import load_dotenv
load_dotenv() 

from langchain_community.llms import Ollama 
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser 
import streamlit as st 

os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT")

# Prompt template 
prompt=ChatPromptTemplate(
    [

        ("system","you are a helpful assistant.Please respond to the question asked"),
        ("user","Question:{question}")

    ] 
)

## Stream lit framework 
st.title("Langchain Demo with Gemma model")
input_text=st.text_input("what question you have in mind?")

## LLM definition 
llm=Ollama(model="qwen3:0.6b")
output_parser=StrOutputParser()
chain=prompt|llm|output_parser

try:
    response = chain.invoke({"question": input_text})
    st.write(response)
except Exception as e:
    st.error(str(e))