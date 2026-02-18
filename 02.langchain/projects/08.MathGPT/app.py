
import streamlit as st
import os 
import numexpr as ne 
from langchain_groq import ChatGroq
from langchain_core.tools import tool
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_core.prompts import ChatPromptTemplate 

from langgraph.prebuilt import create_react_agent

# ---------------- UI ----------------
st.set_page_config(page_title="MathGPT", page_icon="🧮")
st.title("MathGPT 🧮")
st.subheader("Solve Math Problems + Wikipedia using Groq + LangChain v1")

# Groq API
groq_api_key = st.sidebar.text_input("Groq API Key:", type="password")
if not groq_api_key:
    st.info("👈 Enter Groq API Key")
    st.stop()
os.environ["GROQ_API_KEY"] = groq_api_key

# ---------------- LLM ----------------
llm = ChatGroq(model_name="llama-3.1-8b-instant")

# ---------------- Tools ----------------
@tool  
def wikipedia_search(query: str) -> str:
    """Search Wikipedia for factual information."""
    wrapper = WikipediaAPIWrapper(top_k_results=3, doc_content_chars_max=1500)
    return wrapper.run(query)

@tool  
def calculator(expression: str) -> str:
    """Solve math problems. Input: math expression or word problem."""
    try:
        result = ne.evaluate(expression)
        return f"Result: {result}"
    except Exception as e:
        return f"Error: {e}. Use valid Python math expression."

@tool  
def reasoning(question: str) -> str:
    """Provide step-by-step reasoning for complex questions."""
    prompt = ChatPromptTemplate.from_template(
        "Explain step-by-step: {question}\n\nAnswer:"
    )
    chain = prompt | llm
    return chain.invoke({"question": question}).content

tools = [wikipedia_search, calculator, reasoning]

# ---------------- Agent ----------------
agent = create_react_agent(
    llm,
    tools,
    prompt="""You are MathGPT 🧮.

IMPORTANT RULES:
- Always provide a FINAL ANSWER to the user.
- After using any tool, summarize the result in clear natural language.
- Never reply with tool status messages.
- If the question is definitional, explain in simple terms.

You may use tools, but the final response must be human-readable."""
)


# ---------------- Chat ----------------
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hi! Ask math or Wikipedia questions!"}]

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).markdown(msg["content"])

# User input
if prompt := st.chat_input("Ask a math problem or question..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("🧮 Thinking..."):
            
            result = agent.invoke({
                "messages": [{"role": "user", "content": prompt}]
            })
            answer = result["messages"][-1].content

        st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})