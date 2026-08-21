import os
from typing import List
from crewai import Agent, Crew, Process, Task, LLM
from crewai.agents.agent_builder.base_agent import BaseAgent
from crewai.project import CrewBase, agent, crew, task

@CrewBase
class TestCrew:
    """Test Crew"""
    agents: List[BaseAgent]
    tasks: List[Task]

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def text_writer(self) -> Agent:
        return Agent(
            config=self.agents_config["text_writer"],  # type: ignore[index]
            llm=LLM(
                model=os.getenv("OPENAI_MODEL", ""),
                api_key=os.getenv("OPENAI_API_KEY", "")
            )
        )

    @task
    def write_text(self) -> Task:
        return Task(
            config=self.tasks_config["write_text"],  # type: ignore[index],
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Research Crew"""

        return Crew(
            agents=self.agents,  # Automatically created by the @agent decorator
            tasks=self.tasks,  # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
        )
