import streamlit as st
from langchain_community.llms import Ollama
from langchain_classic.prompts import ChatPromptTemplate

import os 
from dotenv import load_dotenv

load_dotenv()

#Langsmith tracking 
os.environ['LANGCHAIN_API_KEY']=os.getenv("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_TRACING_V2"]="true"
os.environ["LANGCHAIN_PROJECT"]="2.QA CHATBOT WITH OLLAMA"

# Prompt Template
prompt=ChatPromptTemplate.from_messages(
          [
              ("system","You are a helpful assitant.Please response to the user queries"),
              ("user","Question:{question}")
          ]
)

# Function to generate response based on the various parameters 
def generate_response(question,engine,temperature):
    llm=Ollama(model=engine,temperature=temperature)
    chain=prompt|llm
    answer=chain.invoke({'question':question})
    return answer

# streamlit Section 
## Title of the app
st.title("Q&A Chatbot with OLLAMA")

# List the Open source model in Ollama platform 
engine= st.sidebar.selectbox("Select an OPEN Source Model", ["qwen3:0.6b"])

# Adjust the parameter 
temperature=st.sidebar.slider("Temperature",min_value=0.0,max_value=1.0,value=0.7)

# Main interface for user input 
st.write("Go ahead and ask any question")
user_input=st.text_input("You:")

# If the user enter the question pass the input parameters to the "generate_response function"
if user_input:
    response=generate_response(user_input,engine,temperature)
    st.write(response)
else: 
    st.write("Please provide the query")