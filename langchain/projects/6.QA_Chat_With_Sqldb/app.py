import streamlit as st
from pathlib import Path
from langchain.agents import create_agent
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine
from langchain_community.callbacks import StreamlitCallbackHandler
from langchain_groq import ChatGroq
import sqlite3 

st.set_page_config(page_title="LangChain: Chat with SQL DB", page_icon="🦜")
st.title("🦜 LangChain: Chat with SQL DB")

LOCALDB="USE_LOCALDB"
MYSQL="USE_MYSQL"
radio_opt=["Use SQLLite 3 Database- Student.db","Connect to you MySQL Database"]
selected_opt=st.sidebar.radio(label="Chose the DB which you want to chat",options=radio_opt)

if radio_opt.index(selected_opt)==1: 
    db_uri=MYSQL
    mysql_host=st.sidebar.text_input("Provide MySQL Host")
    mysql_user=st.sidebar.text_input("MYSQL User")
    mysql_password=st.sidebar.text_input("MYSQL password",type="password")
    mysql_db=st.sidebar.text_input("MySQL database")
else:
    db_uri=LOCALDB

api_key = st.sidebar.text_input("Groq API Key", type="password")

if api_key and db_uri:
    llm = ChatGroq(groq_api_key=api_key, model_name="llama-3.1-8b-instant", streaming=False)
else:
    st.info("Please enter DB details and Groq API key.")
    st.stop()  

@st.cache_resource(ttl="2h") 
def configure_db(db_uri,mysql_host=None,mysql_user=None,mysql_password=None,mysql_db=None): 
    if db_uri==LOCALDB: 
        dbfilepath=(Path(__file__).parent/"student.db").absolute()
        print(dbfilepath)
        creator=lambda: sqlite3.connect(f"file:{dbfilepath}?mode=ro",uri=True)
        return SQLDatabase(create_engine("sqlite:///", creator=creator)) 
    elif db_uri==MYSQL:
        if not (mysql_host and mysql_user and mysql_password and mysql_db): 
            st.error("Please provide all Mysql connection details")
            st.stop()
        return SQLDatabase(create_engine(f"mysql+mysqlconnector://{mysql_user}:{mysql_password}@{mysql_host}/{mysql_db}"))   

try:
    if db_uri == MYSQL:
        db = configure_db(db_uri, mysql_host, mysql_user, mysql_password, mysql_db)
    else:
        db = configure_db(db_uri)
except Exception as e:
    st.error(f"Database connection failed: {e}")
    st.stop()


# Tool kit 
toolkit=SQLDatabaseToolkit(db=db,llm=llm)
tools=toolkit.get_tools()

agent=create_agent(llm,tools)

if "messages" not in st.session_state or st.sidebar.button("Clear message history"):
    st.session_state["messages"] = [{"role": "assistant", "content": "How can I help you?"}]

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

user_query=st.chat_input(placeholder="Ask anything from the database")

if user_query:
    st.session_state.messages.append({"role": "user", "content": user_query})
    st.chat_message("user").write(user_query)

    with st.chat_message("assistant"):
        st_cb=StreamlitCallbackHandler(st.container(),expand_new_thoughts=False)
        result = agent.invoke(
            {"messages": st.session_state.messages},
            config={"callbacks": [st_cb]} 
        )

        # Extract final assistant message text
        final_answer = result["messages"][-1].content

        # Save only clean text to history (not the whole dict)
        st.session_state.messages.append({"role": "assistant", "content": final_answer})

        # Show nicely
        st.markdown(final_answer)