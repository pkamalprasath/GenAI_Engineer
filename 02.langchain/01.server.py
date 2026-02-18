import os
from fastapi import FastAPI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langserve import add_routes
from dotenv import load_dotenv

# Load environment variables from .env file
# (Example: GROQ_API_KEY=xxxx)
load_dotenv()

from langchain_groq import ChatGroq

# Read Groq API key securely from environment variables
groq_api_key = os.getenv("GROQ_API_KEY")

# Create the LLM object (this is the "brain")
# model="llama-3.1-8b-instant" is the Groq-hosted Llama model name
model = ChatGroq(model="llama-3.1-8b-instant", groq_api_key=groq_api_key)

# Output parser: converts model output into a plain string
parser = StrOutputParser()

# Prompt instruction (system message)
# {Language} is a variable that will be filled at runtime
generic_template = "Translate the following into {Language}:"

# Create a chat prompt template with:
# 1) system message = instruction
# 2) user message = actual text to translate
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", generic_template),
        ("user", "{text}")  # {text} will be filled at runtime
    ]
)

# Create the LangChain runnable pipeline:
# input -> prompt -> model -> output parser
chain = prompt | model | parser

# Create FastAPI app (the web server)
app = FastAPI(
    title="LangChain Server",
    version="1.0",
    description="A simple API server using LangChain runnable interfaces"
)

# LangServe automatically creates API endpoints for the chain under /chain
# You will get endpoints like:
# POST /chain/invoke  (normal request/response)
# POST /chain/stream  (streaming)
# POST /chain/batch   (batch inputs)
add_routes(app, chain, path="/chain")

# Run the server locally only when you run this file directly
if __name__ == "__main__":
    import uvicorn
    # Starts server at http://localhost:8000
    uvicorn.run(app, host="localhost", port=8000)