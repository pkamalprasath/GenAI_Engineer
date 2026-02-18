from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from src.tools import zapproxy



@CrewBase
class PennTestAgentCrew():
    """PennTest Crew class"""
    agents_config = "config/penn_test_agents.yaml"
    tasks_config = "config/penn_test_tasks.yaml"

    @agent
    def penn_test_planner(self) -> Agent:
        return Agent(
            config=self.agents_config['penn_tester_planner'],
            tools=[
                zapproxy.zap_general_use
            ],
            verbose=True,
            allow_delegation=False,
        )

    @agent
    def writer_agent_planner(self) -> Agent:
        return Agent(
            config=self.agents_config['writer_agent_planner'],
            verbose=True,
            allow_delegation=False,
        )

    @agent
    def markdown_agent_planner(self) -> Agent:
        return Agent(
            config=self.agents_config['markdown_agent_planner'],
            verbose=True,
            allow_delegation=False,
        )

    @task
    def cybersecurity_research_task(self) -> Task:
        return Task(
            config=self.tasks_config['web_security_vulnerability_scan'],
            agent=self.penn_test_planner()
        )

    @task
    def build_cybersecurity_report_task(self) -> Task:
        return Task(
            config=self.tasks_config['web_security_report_task'],
            agent=self.writer_agent_planner()
        )

    @task
    def convert_report_to_markdown_task(self) -> Task:
        return Task(
            config=self.tasks_config['convert_report_to_markdown_task'],
            agent=self.markdown_agent_planner()
        )
    @crew
    def crew(self) -> Crew:
        """Creates the CyberSecurity crew"""
        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            memory=True,
        )