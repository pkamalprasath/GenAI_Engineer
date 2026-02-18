import streamlit as st
from langchain_groq import ChatGroq
from langchain_community.utilities import ArxivAPIWrapper,WikipediaAPIWrapper
from langchain_community.tools import ArxivQueryRun,WikipediaQueryRun,DuckDuckGoSearchRun
from langchain_community.callbacks import StreamlitCallbackHandler
from langchain.agents import create_agent
import os
from dotenv import load_dotenv

arxiv_wraper=ArxivAPIWrapper(top_k_results=1,doc_content_chars_max=250)
arxiv=ArxivQueryRun(api_wrapper=arxiv_wraper)

wiki_wraper=WikipediaAPIWrapper(top_k_results=1,doc_content_chars_max=250)
wiki=WikipediaQueryRun(api_wrapper=wiki_wraper)

search=DuckDuckGoSearchRun(name="Search")



st.title("🔎 LangChain - Chat with search")

## Sidebar for settings
st.sidebar.title("Settings")
api_key=st.sidebar.text_input("Enter your Groq API Key:",type="password")

#  1. Initialize (first visit only)
if "messages" not in st.session_state: 
    st.session_state.messages=[
        {"role":"assistant","content":"Hi,I'm a chatbot who can search the web. How can I help you?"}
    ]

# 2. Show history
for msg in st.session_state.messages: 
    st.chat_message(msg["role"]).write(msg['content']) 

# 3. New input
if prompt:= st.chat_input(placeholder="What is machine learning?"):
    st.session_state.messages.append({"role":"user","content":prompt})
    st.chat_message("user").write(prompt) 
    llm=ChatGroq(groq_api_key=api_key,model_name="llama-3.1-8b-instant",streaming=True) 
    tools=[search,arxiv,wiki]
    search_agent=create_agent(llm,tools)
    with st.chat_message("assistant"):
        # Create callback - passes container for live visualization [→ Shows live: [🧠 Thinking...] [🔧 Tool call] 
        st_cb=StreamlitCallbackHandler(st.container(),expand_new_thoughts=False)
       
        result = search_agent.invoke(
            {"messages": st.session_state.messages},
            config={"callbacks": [st_cb]} 
        )

        # Extract final assistant message text
        final_answer = result["messages"][-1].content

        # Save only clean text to history (not the whole dict)
        st.session_state.messages.append({"role": "assistant", "content": final_answer})

        # Show nicely
        st.markdown(final_answer)
       