from crewai import Agent
from tools import yt_tool
import os 
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
load_dotenv()

os.environ["OPENAI_API_KEY"]= os.getenv('OPENAI_API_KEY')

llm = ChatOpenAI(
    model="gpt-4.1-mini",
    temperature=0.2
)

blog_researcher = Agent(
    role="YouTube Research Analyst",
    goal="Find and summarize the most relevant content about {topic}.",
    backstory=(
        "You are an expert researcher. "
        "You already have access to the correct YouTube channel via your tools. "
        "Never ask for channel URLs or video URLs. "
        "Always use the provided tool to search the channel."
    ),
    tools=[yt_tool],
    llm=llm,
    verbose=False,
    memory=True,
)

blog_writer = Agent(
    role='Blog Writer',
    goal='write a detailed blog post on the topic {topic} using the research content provided by the Blog Researcher agent',
    verbose=False,
    memory=True,
    backstory='You are an experienced blog writer known for crafting engaging and informative articles. Your task is to create a comprehensive blog post on the specified topic using the research content provided by the Blog Researcher agent.',
    tools=[yt_tool],
    llm=llm,
    allow_delegation=False
)

