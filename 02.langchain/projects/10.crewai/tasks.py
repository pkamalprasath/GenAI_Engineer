from crewai import Task
from tools import yt_tool 
from agents import blog_researcher, blog_writer


research_task = Task(
    description=(
        "Search the YouTube channel using the tool you already have access to.\n"
        "Use the topic '{topic}' as the search_query.\n"
        "Do NOT ask for a channel or video URL.\n"
        "Return key insights explaining the topic clearly."
    ),
    expected_output=(
        "Bullet-point explanation of the topic based on the most relevant videos."
    ),
    agent=blog_researcher,
)

writer_task = Task(
    description=(
        "Write a detailed blog post on '{topic}' using the research provided.\n"
        "Explain concepts clearly with examples."
    ),
    expected_output="Well-structured markdown blog post.",
    agent=blog_writer,
    output_file="blog.md",
)