import streamlit as st
from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain_classic.prompts import ChatPromptTemplate

import os 
from dotenv import load_dotenv

load_dotenv()

#Langsmith tracking 
os.environ['LANGCHAIN_API_KEY']=os.getenv("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_TRACING_V2"]="true"
os.environ["LANGCHAIN_PROJECT"]="1.QA CHATBOT WITH OPENAI"

# Prompt Template
prompt=ChatPromptTemplate.from_messages(
          [
              ("system","You are a helpful assitant.Please response to the user queries"),
              ("user","Question:{question}")
          ]
)
# Function to generate response based on the various parameters 
def generate_response(question,api_key,llm,temperature,max_tokens):
    llm=ChatOpenAI(api_key=api_key,model=llm,temperature=temperature,max_tokens=max_tokens)
    chain=prompt|llm
    answer=chain.invoke({'question':question})
    return answer.content

# streamlit Section 
## Title of the app
st.title("Q&A Chatbot with OPENAI")

## Sidebar settings
st.sidebar.title("Settings")

# Get the api key from the user and validate that 
api_key =st.sidebar.text_input("Enter your OPENAI API KEY:",type="password")

# After the validation list all the Open AI model that with "gpy-" ; User can select from the listed models
if api_key:
    client = OpenAI(api_key=api_key)
    # Fetch models in real time
    models = client.models.list()
    model_ids = sorted([m.id for m in models.data if m.id.startswith("gpt-")])
    llm = st.sidebar.selectbox("Select an OPEN AI Model", model_ids)
    st.write("Selected model:", llm)
else:
    st.info("Please enter your OpenAI API key")

# Slide bar is introduced to select temperature and max tokens
temperature=st.sidebar.slider("Temperature",min_value=0.0,max_value=1.0,value=0.7)
max_tokens=st.sidebar.slider("Max Tokens",min_value=50,max_value=300,value=150)

# Main interface for user input 
st.write("Go ahead and ask any question")
user_input=st.text_input("You:")

# If the user enter the question pass the input parameters to the "generate_response function"
if user_input:
    response=generate_response(user_input,api_key,llm,temperature,max_tokens)
    st.write(response)
else: 
    st.write("Please provide the query")