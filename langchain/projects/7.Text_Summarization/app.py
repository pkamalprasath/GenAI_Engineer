import validators
import streamlit as st
from langchain_classic.chains.summarize import load_summarize_chain
from langchain_core.prompts import ChatPromptTemplate  
from langchain_groq import ChatGroq 
from langchain_community.document_loaders.youtube import YoutubeLoader 
from langchain_community.document_loaders import UnstructuredURLLoader 

 
## 

st.set_page_config(page_title="Text Summarization App",page_icon=": robot :") 
st.title("Summarize text from youtube or Website:robot:") 
st.subheader("Using Groq LLM and Langchain") 

## 

with st.sidebar:    
    groq_api_key=st.text_input("Enter Groq API Key:",value="",type="password") 

generic_url=st.text_input("URL",label_visibility="collapsed",placeholder="Enter Youtube or Website URL") 

template=""" Write a concise summary of the following text IN 300 Words: {text} """ 
prompt = ChatPromptTemplate.from_template(template) 

if st.button("Summarize"): 
    if not groq_api_key.strip() or not generic_url.strip(): 
        st.error("Please enter the webiste or youtube URL ") 
    elif not validators.url(generic_url): 
        st.error("Please enter valid URL")  
    else: 

        try: 
            with st.spinner("Waiting.."):
                llm=ChatGroq(model="llama-3.1-8b-instant", groq_api_key=groq_api_key) 
                if "youtube" in generic_url:
                    loader=YoutubeLoader.from_youtube_url(generic_url,add_video_info=True)
                else :
                    loader=UnstructuredURLLoader(urls=[generic_url],ssl_verify=False,
                                                 headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"})
                doc=loader.load()        
                chain=load_summarize_chain(llm,chain_type="stuff",prompt=prompt)
                output=chain.invoke({"input_documents":doc})
                st.success(output["output_text"])
        except Exception as e: 
            st.error(f"Error: {e}")


               
       