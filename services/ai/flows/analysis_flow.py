"""Analysis Flow implementation using CrewAI."""

import logging
from pathlib import Path
from typing import Dict, Any
from pydantic import BaseModel
from crewai import Agent, Task, Crew
from crewai.flow.flow import Flow, start, listen
from dataclasses import asdict

from ..prompts import (
    metrics_agent_prompt,
    activity_agent_prompt,
    physiological_agent_prompt,
    synthesis_agent_prompt
)
from ..model_config import ModelSelector
from ..config.ai_settings import AgentRole
from services.garmin import GarminData
from ..enhanced_framework import (
    GetMetricsTool, GetActivitiesTool, GetPhysioTool,
    GetCompetitionsTool, GetCurrentDateTool
)

logger = logging.getLogger(__name__)

class AnalysisState(BaseModel):
    """State management for analysis flow."""
    metrics_result: str = ""
    activities_result: str = ""
    physiology_result: str = ""
    synthesis_result: str = ""

class AnalysisFlow(Flow[AnalysisState]):
    """Analysis implementation using CrewAI."""

    def __init__(self, garmin_data: GarminData, user_id: str, athlete_name: str):
        """
        Initialize the analysis flow.

        Args:
            garmin_data: Athlete's Garmin data
            user_id: User identifier
            athlete_name: Name of the athlete for personalizing agent roles
        """
        super().__init__()
        self.data = asdict(garmin_data)
        self.user_id = user_id
        self.athlete_name = athlete_name
        
        # Initialize tools
        self.metrics_tool = GetMetricsTool(data=self.data)
        self.activities_tool = GetActivitiesTool(data=self.data)
        self.physio_tool = GetPhysioTool(data=self.data)
        self.competitions_tool = GetCompetitionsTool(user_id=self.user_id)
        self.current_date_tool = GetCurrentDateTool()
        
        # Ensure output directory exists
        Path("analysis").mkdir(exist_ok=True)
        
        # Initialize agents
        self.metrics_agent = self._create_metrics_agent()
        self.activity_agent = self._create_activity_agent()
        self.physio_agent = self._create_physiology_agent()
        self.synthesis_agent = self._create_synthesis_agent()
        
        # Initialize tasks
        self.metrics_task = Task(
            name="metrics_analysis",
            description="Analyze training metrics and identify patterns in relation to competition goals",
            agent=self.metrics_agent,
            expected_output="Competition-aware metrics analysis with patterns and trends",
            output_file="analysis/metrics.md"
        )
        
        self.activities_task = Task(
            name="activity_analysis",
            description="Analyze workout execution and identify patterns considering race preparation",
            agent=self.activity_agent,
            expected_output="Race-specific activity patterns and execution analysis",
            output_file="analysis/activities.md"
        )
        
        self.physiology_task = Task(
            name="physio_analysis",
            description="Analyze physiological responses and adaptations in context of competition schedule",
            agent=self.physio_agent,
            expected_output="Competition-aware recovery and adaptation analysis",
            output_file="analysis/physiology.md"
        )
        
        self.synthesis_task = Task(
            name="synthesis",
            description="Synthesize analysis results into comprehensive report with competition context",
            agent=self.synthesis_agent,
            context=[self.metrics_task, self.activities_task, self.physiology_task],
            expected_output="Competition-aware comprehensive synthesis with insights",
            output_file="analysis/synthesis.md"
        )
        
        logger.info("Initialized AnalysisFlow with data keys: %s", list(self.data.keys()))

    def _create_metrics_agent(self) -> Agent:
        """Create metrics analysis agent."""
        return Agent(
            role="Metrics Analysis Specialist",
            goal="Analyze training metrics and competition data",
            backstory=metrics_agent_prompt,
            verbose=True,
            llm=ModelSelector.get_llm(AgentRole.METRICS),
            tools=[self.metrics_tool, self.competitions_tool, self.current_date_tool]
        )

    def _create_activity_agent(self) -> Agent:
        """Create activity analysis agent."""
        return Agent(
            role="Activity Analysis Specialist",
            goal="Analyze training activities and patterns",
            backstory=activity_agent_prompt,
            verbose=True,
            llm=ModelSelector.get_llm(AgentRole.ACTIVITY),
            tools=[self.activities_tool, self.competitions_tool, self.current_date_tool]
        )

    def _create_physiology_agent(self) -> Agent:
        """Create physiological analysis agent."""
        return Agent(
            role="Physiological Analysis Specialist",
            goal="Analyze physiological data and recovery patterns",
            backstory=physiological_agent_prompt,
            verbose=True,
            llm=ModelSelector.get_llm(AgentRole.PHYSIO),
            tools=[self.physio_tool, self.competitions_tool, self.current_date_tool]
        )

    def _create_synthesis_agent(self) -> Agent:
        """Create synthesis agent."""
        return Agent(
            role="Data Synthesis Specialist",
            goal="Synthesize analyses into comprehensive reports",
            backstory=synthesis_agent_prompt,
            verbose=True,
            llm=ModelSelector.get_llm(AgentRole.SYNTHESIS),
            tools=[self.competitions_tool, self.current_date_tool]
        )

    @start()
    def analyze_metrics(self):
        """Perform metrics analysis."""
        crew = Crew(tasks=[self.metrics_task], agents=[self.metrics_agent], verbose=True)
        result = crew.kickoff()
        self.state.metrics_result = result
        logger.info("Metrics Analysis completed")
        return result

    @listen(analyze_metrics)
    def analyze_activities(self, metrics_result):
        """Perform activities analysis."""
        crew = Crew(tasks=[self.activities_task], agents=[self.activity_agent], verbose=True)
        result = crew.kickoff()
        self.state.activities_result = result
        logger.info("Activities Analysis completed")
        return result

    @listen(analyze_activities)
    def analyze_physiology(self, activities_result):
        """Perform physiology analysis."""
        crew = Crew(tasks=[self.physiology_task], agents=[self.physio_agent], verbose=True)
        result = crew.kickoff()
        self.state.physiology_result = result
        logger.info("Physiology Analysis completed")
        return result

    @listen(analyze_physiology)
    def synthesize_results(self, physiology_result):
        """Combine analysis results into a synthesis report."""
        crew = Crew(tasks=[self.synthesis_task], agents=[self.synthesis_agent], verbose=True)
        result = crew.kickoff()
        self.state.synthesis_result = result
        logger.info("Synthesis completed")
        return result
