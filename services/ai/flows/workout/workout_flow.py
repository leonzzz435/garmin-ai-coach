"""Workout Flow implementation using CrewAI."""

import logging
from pathlib import Path
from pydantic import BaseModel
from crewai import Agent, Task, Crew, Process
from crewai.project import CrewBase, agent, task, crew
from crewai.flow.flow import Flow, start
from ...model_config import ModelSelector
from ...ai_settings import AgentRole
from dataclasses import asdict
from services.garmin import GarminData
from ..tools.tools import (
    GetReportTool, GetCompetitionsTool, GetCurrentDateTool,
    GetMetricsTool, GetActivitiesTool, GetPhysioTool
)

logger = logging.getLogger(__name__)

class WorkoutState(BaseModel):
    """State management for workout flow."""
    analysis_report: str = ""
    competition_plan: str = ""
    workout_result: str = ""

@CrewBase
class WorkoutCrew:
    """Workout crew implementation."""

    def __init__(self, user_id: str, athlete_name: str, analysis_report: str, garmin_data: GarminData):
        """Initialize the workout crew."""
        self.user_id = user_id
        self.athlete_name = athlete_name
        
        # Convert GarminData to dict
        self.data = asdict(garmin_data)
        
        # Initialize tools
        self.report_tool = GetReportTool(report=analysis_report)
        self.competitions_tool = GetCompetitionsTool(user_id=user_id)
        self.current_date_tool = GetCurrentDateTool()
        self.metrics_tool = GetMetricsTool(data=self.data)
        self.activities_tool = GetActivitiesTool(data=self.data)
        self.physio_tool = GetPhysioTool(data=self.data)
        
        # Ensure output directory exists
        Path("workouts").mkdir(exist_ok=True)
        logger.info("Initialized WorkoutCrew")
        
    @agent
    def competition_planner_agent(self) -> Agent:
        """Create competition planning agent."""
        return Agent(
            config=self.agents_config['competition_planner_agent'],
            llm=ModelSelector.get_llm(AgentRole.COMPETITION_PLANNER),
            tools=[
                self.competitions_tool,
                self.current_date_tool
            ]
        )

    @agent
    def workout_agent(self) -> Agent:
        """Create workout generation agent."""
        return Agent(
            config=self.agents_config['workout_agent'],
            llm=ModelSelector.get_llm(AgentRole.WORKOUT),
            tools=[
                self.report_tool,
                self.activities_tool,
                self.metrics_tool,
                self.physio_tool
            ]
        )
        
    @task
    def competition_planning_task(self) -> Task:
        """Create competition planning task."""
        return Task(
            config=self.tasks_config['competition_planning_task']
        )

    @task
    def workout_task(self) -> Task:
        """Create workout generation task."""
        return Task(
            config=self.tasks_config['workout_task'],
            context=[self.competition_planning_task()]
        )

    @crew
    def crew(self) -> Crew:
        """Create workout generation crew."""
        return Crew(
            agents=[
                self.competition_planner_agent(),
                self.workout_agent()
            ],
            tasks=[
                self.competition_planning_task(),
                self.workout_task()
            ],
            process=Process.sequential,
            verbose=True
        )

class WorkoutFlow(Flow[WorkoutState]):
    """Workout flow implementation."""
    
    workout_crew = WorkoutCrew

    def __init__(self, user_id: str, athlete_name: str, analysis_report: str, garmin_data: GarminData):
        """Initialize the workout flow."""
        super().__init__()
        self.crew_instance = self.workout_crew(user_id, athlete_name, analysis_report, garmin_data)
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
