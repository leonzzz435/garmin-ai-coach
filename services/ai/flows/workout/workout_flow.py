"""Workout Flow implementation using CrewAI."""

import logging
from pathlib import Path
from pydantic import BaseModel
from crewai import Agent, Task, Crew, Process
from crewai.project import CrewBase, agent, task, crew
from crewai.flow.flow import Flow, start
from ...model_config import ModelSelector
from ...ai_settings import AgentRole
from ..tools.tools import (
    GetReportTool, GetCompetitionsTool, GetCurrentDateTool
)

logger = logging.getLogger(__name__)

class WorkoutState(BaseModel):
    """State management for workout flow."""
    analysis_report: str = ""
    workout_result: str = ""

@CrewBase
class WorkoutCrew:
    """Workout crew implementation."""

    def __init__(self, user_id: str, athlete_name: str, analysis_report: str):
        """Initialize the workout crew."""
        self.user_id = user_id
        self.athlete_name = athlete_name
        
        # Initialize tools
        self.report_tool = GetReportTool(report=analysis_report)
        self.competitions_tool = GetCompetitionsTool(user_id=user_id)
        self.current_date_tool = GetCurrentDateTool()
        
        # Ensure output directory exists
        Path("workouts").mkdir(exist_ok=True)
        logger.info("Initialized WorkoutCrew")
        
    @agent
    def workout_agent(self) -> Agent:
        """Create workout generation agent."""
        return Agent(
            config=self.agents_config['workout_agent'],
            llm=ModelSelector.get_llm(AgentRole.WORKOUT),
            tools=[
                self.report_tool,
                self.competitions_tool,
                self.current_date_tool
            ]
        )
        
    @task
    def workout_task(self) -> Task:
        """Create workout generation task."""
        return Task(
            config=self.tasks_config['workout_task']
        )

    @crew
    def crew(self) -> Crew:
        """Create workout generation crew."""
        return Crew(
            agents=[self.workout_agent()],
            tasks=[self.workout_task()],
            process=Process.sequential
        )

class WorkoutFlow(Flow[WorkoutState]):
    """Workout flow implementation."""
    
    workout_crew = WorkoutCrew

    def __init__(self, user_id: str, athlete_name: str, analysis_report: str):
        """Initialize the workout flow."""
        super().__init__()
        self.crew_instance = self.workout_crew(user_id, athlete_name, analysis_report)
        self.athlete_name = athlete_name
        self.state.analysis_report = analysis_report

    @start()
    async def generate_workouts(self):
        """Generate personalized workout plans."""
        result = await self.crew_instance.crew().kickoff_async(
            inputs={'athlete_name': self.athlete_name}
        )
        self.state.workout_result = result
        logger.info("Workout generation completed")
        return result
