Text Summarization App (YouTube & Website)

A Streamlit-based web application that summarizes content from YouTube videos or web pages using Groq-hosted LLMs and LangChain.

🚀 Project Overview

In today’s world, valuable information is often locked inside long videos or lengthy web articles. Reading or watching entire content is time-consuming and inefficient.

This project solves that problem by allowing users to:

Paste a YouTube video URL or a website URL

Instantly receive a concise, meaningful summary

Save time while still capturing the core ideas

🎯 Use Case / Problem Statement
Problem

Long YouTube videos and articles are hard to consume quickly

Users want fast insights, not full transcripts

Manual summarization is time-consuming and inconsistent

Solution

Automatically extract content from URLs

Use an LLM to generate a clear, structured summary

Provide a simple UI for non-technical users

🧩 Components Involved
1️⃣ User Interface (UI)

Built with Streamlit

Accepts:

Groq API Key

YouTube or Website URL

Displays summarized output in real time

2️⃣ Content Loaders

YouTubeLoader

Extracts video transcripts and metadata

UnstructuredURLLoader

Extracts clean text from web pages

3️⃣ Prompt & Chain Logic

Custom summarization prompt

Uses LangChain’s load_summarize_chain

stuff chain type for concise summaries

4️⃣ Large Language Model (LLM)

Powered by Groq

Model used: llama-3.1-8b-instant

Fast inference with high-quality summaries

🛠️ Tech Stack
Category	Technology
Frontend	Streamlit
LLM Provider	Groq
LLM Model	LLaMA 3.1 (8B Instant)
Framework	LangChain
Loaders	YouTubeLoader, UnstructuredURLLoader
Validation	validators
Language	Python

User URL
   ↓
Content Loader (YouTube / Web)
   ↓
Text Extraction
   ↓
LangChain Summarization Chain
   ↓
Groq LLM
   ↓
Final Summary (Streamlit UI)


nstallation & Setup
1️⃣ Clone the repository
git clone https://github.com/your-username/text-summarization-app.git
cd text-summarization-app

2️⃣ Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # macOS/Linux

3️⃣ Install dependencies
pip install -r requirements.txt

4️⃣ Run the app
python -m streamlit run app.py

🔑 API Key Requirement

You need a Groq API Key to use this app.

Enter the key in the Streamlit sidebar

The key is used only at runtime (not stored)

✅ Features

Summarize YouTube videos

Summarize web articles

Clean UI

Fast inference

URL validation

Error handling

⚠️ Current Limitations

Very long videos/pages may hit token limits

stuff chain is best for short-to-medium content

No persistent storage (stateless app)

🔮 Future Enhancements

Map-Reduce summarization for long content

Adjustable summary length

Multi-language summaries

Download summary as PDF / TXT

Deployment on Streamlit Cloud

User authentication

📌 Ideal For

Students & researchers

Content creators

Developers building RAG pipelines

Anyone needing fast content insights

👨‍💻 Author

Kamal Prasath Perumalsamy
AI / ML Enthusiast | LangChain & LLM Applications