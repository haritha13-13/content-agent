import os
from typing import List

from crewai import Agent, Crew, LLM, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent

from content_agent.tools.seo_checker import SEOCheckerTool
from content_agent.tools.content_validator import ContentValidatorTool
from content_agent.tools.file_writer import FileWriterTool
from content_agent.tools.file_reader import FileReaderTool
from content_agent.tools.web_researcher import WebResearchTool
from content_agent.tools.image_generator import ImageGenerationTool


def default_llm() -> LLM:
    """Create the default LLM.

    Priority:
      1. If MODE=cloud (or OLLAMA_API_KEY + API_BASE are set) -> use the remote Ollama endpoint.
      2. Else if OPENAI_API_KEY / ANTHROPIC_API_KEY set -> cloud provider via MODEL.
      3. Else -> local Ollama at localhost:11434.
    """
    model = os.getenv("MODEL", "ollama/llama3.1")

    # Remote / cloud Ollama (e.g. gemma3:31b-cloud)
    api_base = os.getenv("API_BASE")
    ollama_key = os.getenv("OLLAMA_API_KEY")
    if os.getenv("MODE", "").lower() == "cloud" or (api_base and ollama_key):
        return LLM(
            model=model,
            api_key=ollama_key,
            base_url=api_base,
            temperature=0.7,
        )

    # Standard cloud providers
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        return LLM(model=model, temperature=0.7)

    # Local Ollama - no API key needed
    return LLM(
        model=model,
        api_key="ollama",
        base_url="http://localhost:11434",
        temperature=0.7,
    )


@CrewBase
class ContentGenerationCrew:
    """Content Generation crew that follows the Speedbots content strategy."""

    agents: List[BaseAgent]
    tasks: List[Task]

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def strategy_planner(self) -> Agent:
        return Agent(
            config=self.agents_config["strategy_planner"],  # type: ignore[index]
            llm=default_llm(),
            verbose=True,
            max_iter=3,
        )

    @agent
    def research_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config["research_analyst"],  # type: ignore[index]
            llm=default_llm(),
            tools=[WebResearchTool()],
            verbose=True,
            max_iter=3,
        )

    @agent
    def content_writer(self) -> Agent:
        return Agent(
            config=self.agents_config["content_writer"],  # type: ignore[index]
            llm=default_llm(),
            tools=[FileWriterTool()],
            verbose=True,
            max_iter=3,
        )

    @agent
    def seo_optimizer(self) -> Agent:
        return Agent(
            config=self.agents_config["seo_optimizer"],  # type: ignore[index]
            llm=default_llm(),
            tools=[SEOCheckerTool(), FileReaderTool()],
            verbose=True,
            max_iter=3,
        )

    @agent
    def quality_reviewer(self) -> Agent:
        return Agent(
            config=self.agents_config["quality_reviewer"],  # type: ignore[index]
            llm=default_llm(),
            tools=[ContentValidatorTool(), FileWriterTool()],
            verbose=True,
            max_iter=3,
        )

    @agent
    def image_artist(self) -> Agent:
        return Agent(
            config=self.agents_config["image_artist"],  # type: ignore[index]
            llm=default_llm(),
            tools=[ImageGenerationTool()],
            verbose=True,
            max_iter=2,
        )

    @task
    def strategy_task(self) -> Task:
        return Task(
            config=self.tasks_config["strategy_task"],  # type: ignore[index]
        )

    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config["research_task"],  # type: ignore[index]
            context=[self.strategy_task()],
        )

    @task
    def image_task(self) -> Task:
        return Task(
            config=self.tasks_config["image_task"],  # type: ignore[index]
            context=[self.strategy_task(), self.research_task()],
            async_execution=True,
        )

    @task
    def writing_task(self) -> Task:
        return Task(
            config=self.tasks_config["writing_task"],  # type: ignore[index]
            context=[self.strategy_task(), self.research_task()],
        )

    @task
    def seo_task(self) -> Task:
        return Task(
            config=self.tasks_config["seo_task"],  # type: ignore[index]
            context=[self.writing_task()],
        )

    @task
    def review_task(self) -> Task:
        return Task(
            config=self.tasks_config["review_task"],  # type: ignore[index]
            context=[
                self.strategy_task(),
                self.writing_task(),
                self.seo_task(),
            ],
        )

    @crew
    def crew(self) -> Crew:
        """Creates the ContentGeneration crew."""
        import time

        def _log_task(result):
            name = getattr(result, "name", None) or "task"
            with open("/tmp/crew_timing.log", "a") as f:
                f.write(f"{name} | wallclock {time.time():.1f}\n")

        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
            task_callback=_log_task,
        )
