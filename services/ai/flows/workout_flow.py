"""Workout Flow implementation using CrewAI."""

import logging
from pathlib import Path
from typing import Dict, Any
from pydantic import BaseModel
from crewai import Agent, Task, Crew
from ..prompts import workout_agent_prompt
from crewai.flow.flow import Flow, start
from ..model_config import ModelSelector
from ..config.ai_settings import AgentRole
from ..enhanced_framework import (
    GetReportTool, GetCompetitionsTool, GetCurrentDateTool
)

logger = logging.getLogger(__name__)

class WorkoutState(BaseModel):
    """State management for workout flow."""
    analysis_report: str = ""
    workout_result: str = ""

class WorkoutFlow(Flow[WorkoutState]):
    """Workout generation implementation using CrewAI."""

    def __init__(self, user_id: str, athlete_name: str, analysis_report: str):
        """
        Initialize the workout flow.

        Args:
            user_id: User identifier
            athlete_name: Name of the athlete for personalizing agent roles
            analysis_report: Analysis report from AnalysisFlow
        """
        super().__init__()
        self.user_id = user_id
        self.athlete_name = athlete_name
        self.state.analysis_report = analysis_report
        
        # Initialize tools
        self.report_tool = GetReportTool(report=analysis_report)
        self.competitions_tool = GetCompetitionsTool(user_id=user_id)
        self.current_date_tool = GetCurrentDateTool()
        
        # Ensure output directory exists
        Path("workouts").mkdir(exist_ok=True)
        
        # Initialize agent
        self.workout_agent = self._create_workout_agent()
        
        # Initialize task
        self.workout_task = Task(
            name="workout_generation",
            description="Generate personalized workout plans considering upcoming competitions and current training phase",
            agent=self.workout_agent,
            expected_output="Detailed workout plans for each discipline",
            output_file="workouts/generated.md"
        )
        
        logger.info("Initialized WorkoutFlow")

    def _create_workout_agent(self) -> Agent:
        """Create workout generation agent."""
        return Agent(
            role="Workout Generation Specialist",
            goal="Generate personalized workout plans",
            backstory=workout_agent_prompt,
            verbose=True,
            llm=ModelSelector.get_llm(AgentRole.WORKOUT),
            tools=[
                self.report_tool,
                self.competitions_tool,
                self.current_date_tool
            ]
        )

    @start()
    def generate_workouts(self):
        """Generate personalized workout plans."""
        crew = Crew(tasks=[self.workout_task], agents=[self.workout_agent], verbose=True)
        result = crew.kickoff()
        self.state.workout_result = result
        logger.info("Workout generation completed")
        return result
