from crewai import Crew,Process
from agents import blog_researcher, blog_writer
from tasks import research_task, writer_task

crewai = Crew(
    agents=[blog_researcher, blog_writer],
    tasks=[research_task, writer_task],
    process=Process.sequential,
    memory=True,
    verbose=False,
    cache=True,
    max_rpm=100,
    share_crew=True
)
response = crewai.kickoff(inputs={'topic' : 'AI vs ML VS DL VS Data science'})
print(response)