"""Enhanced AI framework implementation using CrewAI."""

import logging
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import asdict
from crewai import Agent, Task, Crew, LLM
from crewai.tools import BaseTool
from core.config import get_config
from core.security.competitions import SecureCompetitionManager

from services.garmin import GarminData
from .prompts import (
    metrics_agent_prompt,
    activity_agent_prompt,
    physiological_agent_prompt,
    synthesis_agent_prompt,
    workout_agent_prompt,
)

logger = logging.getLogger(__name__)

import agentops
agentops.init("31106bb1-bcb6-42cf-8123-328cfd226526")

class GetReportTool(BaseTool):
    """Tool for providing the analysis report."""
    name: str = "get_report"
    description: str = "Retrieve the generated analysis report for further processing"
    report: str  # The report data

    def _run(self) -> Dict[str, Any]:
        return {"report": self.report}

class GetCurrentDateTool(BaseTool):
    """Tool for providing the current date."""
    name: str = "get_current_date"
    description: str = "Get the current date and time"

    def _run(self) -> Dict[str, Any]:
        current_date = datetime.now()
        return {
            'current_date': current_date.isoformat(),
            'date_formatted': current_date.strftime('%Y-%m-%d')
        }

class GetCompetitionsTool(BaseTool):
    """Tool for providing competition/race data."""
    name: str = "get_competitions"
    description: str = "Get upcoming competitions and race events for workout planning"
    user_id: str  # User ID for accessing user-specific competition data

    def _run(self) -> Dict[str, Any]:
        try:
            competition_manager = SecureCompetitionManager(self.user_id)
            competitions = competition_manager.get_upcoming_competitions()
            return {
                'upcoming_competitions': [
                    {
                        'name': comp.name,
                        'date': comp.date.isoformat(),
                        'race_type': comp.race_type,
                        'priority': comp.priority.value,
                        'target_time': comp.target_time,
                        'location': comp.location,
                        'notes': comp.notes
                    }
                    for comp in competitions
                ]
            }
        except Exception as e:
            logger.error("Error getting competition data: %s", str(e))
            return {'upcoming_competitions': []}

class GetMetricsTool(BaseTool):
    """Tool for retrieving training metrics data."""
    name: str = "get_metrics"
    description: str = "Get training metrics data including load history, VO2 max, endurance scores, and race predictions"
    data: Dict[str, Any]  # Declare data as a field

    def _run(self) -> Dict[str, Any]:
        return {
            'training_load_history': self.data.get('training_load_history', []),
            'vo2_max_history': self.data.get('vo2_max_history', []),
            'endurance_score_history': self.data.get('endurance_score_history', []),
            'hill_score': self.data.get('hill_score', []),
            'race_predictions': self.data.get('race_predictions', [])
        }

class GetActivitiesTool(BaseTool):
    """Tool for retrieving activity data."""
    name: str = "get_activities"
    description: str = "Get recent activities and training status data for analysis"
    data: Dict[str, Any]  # Declare data as a field

    def _run(self) -> Dict[str, Any]:
        return {
            'recent_activities': self.data.get('recent_activities', []),
            'training_status': self.data.get('training_status', {})
        }

class GetPhysioTool(BaseTool):
    """Tool for retrieving physiological data."""
    name: str = "get_physio"
    description: str = "Get physiological data including sleep, readiness, and daily stats"
    data: Dict[str, Any]  # Declare data as a field

    def _run(self) -> Dict[str, Any]:
        return {
            'sleep': self.data.get('sleep', []),
            'training_readiness': self.data.get('training_readiness', []),
            'daily_stats': self.data.get('daily_stats', {}),
            'physiological_markers': self.data.get('physiological_markers', {})
        }

class EnhancedAnalyzer:
    """Enhanced analysis system using specialized AI agents."""
    
    def __init__(self, garmin_data: GarminData, user_id: str):
        """Initialize the enhanced analyzer with athlete data and user ID."""
        self.data = asdict(garmin_data)
        self.user_id = user_id
        logger.info("Initializing EnhancedAnalyzer with data keys: %s", list(self.data.keys()))
        
        # Configure Claude LLM
        # self.llm = LLM(
        #     model="claude-3-5-sonnet-20241022",
        #     base_url="https://api.anthropic.com",
        #     max_tokens=8000,
        #     api_key=get_config().anthropic_api_key
        # )
        
        self.llm = LLM(
            model="gpt-4o",
            base_url="https://api.openai.com/v1",
            max_tokens=8000,
            api_key=get_config().openai_api_key
        )
        
        # Initialize specialized agents
        # Configure agents with rate limiting
        self.metrics_agent = Agent(
            role="Metrics Analysis Specialist",
            goal="Analyze training metrics and patterns",
            backstory=metrics_agent_prompt,
            verbose=True,
            llm=self.llm
        )
        
        self.activity_agent = Agent(
            role="Activity Analysis Specialist",
            goal="Analyze workout execution and patterns",
            backstory=activity_agent_prompt,
            verbose=True,
            llm=self.llm
        )
        
        self.physio_agent = Agent(
            role="Physiological Analysis Specialist",
            goal="Analyze physiological responses and adaptations",
            backstory=physiological_agent_prompt,
            verbose=True,
            llm=self.llm
        )
        
        self.synthesis_agent = Agent(
            role="Training Synthesis Specialist",
            goal="Synthesize analyses into actionable insights",
            backstory=synthesis_agent_prompt,
            verbose=True,
            llm=self.llm
        )

    def create_workout_agent(self) -> Agent:
        """Create a workout-specific agent."""
        return Agent(
            role="Workout Generation Specialist",
            goal="Generate personalized workout plans",
            backstory=workout_agent_prompt,
            verbose=True,
            llm=self.llm
        )

    def generate_workouts(self, report: str) -> str:
        """Generate workout plans based on analysis report and competition data."""
        try:
            # Ensure output directory exists
            Path("workouts").mkdir(exist_ok=True)
            
            # Create a workout agent
            workout_agent = self.create_workout_agent()
            
            # Create tools with report, competition data, and current date
            report_tool = GetReportTool(report=report)
            competitions_tool = GetCompetitionsTool(user_id=self.user_id)
            current_date_tool = GetCurrentDateTool()
            
            # Create workout generation task
            workout_task = Task(
                name="workout_generation",
                description="Generate personalized workout plans considering upcoming competitions and current training phase.",
                agent=workout_agent,
                tools=[report_tool, competitions_tool, current_date_tool],
                expected_output="Detailed workout plans for each discipline",
                output_file="workouts/generated.md"
            )
            
            # Run workout generation
            crew = Crew(
                agents=[workout_agent],
                tasks=[workout_task],
                verbose=True
            )
            
            result = crew.kickoff()
            return str(result)
            
        except Exception as e:
            logger.error("Error in workout generation: %s", str(e), exc_info=True)
            raise

    def analyze(self) -> str:
        """Run the enhanced analysis process."""
        try:
            # Ensure output directory exists
            Path("analysis").mkdir(exist_ok=True)
            
            # Create analysis tasks
            tasks = []
            
            # Create competition tool
            competitions_tool = GetCompetitionsTool(user_id=self.user_id)
            current_date_tool = GetCurrentDateTool()

            # Add tasks with their respective tools
            tasks.append(Task(
                name="metrics_analysis",
                description="Analyze training metrics and identify patterns in relation to competition goals",
                agent=self.metrics_agent,
                tools=[GetMetricsTool(data=self.data), competitions_tool, current_date_tool],
                expected_output="Competition-aware metrics analysis with patterns and trends",
                output_file="analysis/metrics.md"
            ))

            tasks.append(Task(
                name="activity_analysis",
                description="Analyze workout execution and identify patterns considering race preparation",
                agent=self.activity_agent,
                tools=[GetActivitiesTool(data=self.data), competitions_tool, current_date_tool],
                expected_output="Race-specific activity patterns and execution analysis",
                output_file="analysis/activities.md"
            ))

            tasks.append(Task(
                name="physio_analysis",
                description="Analyze physiological responses and adaptations in context of competition schedule",
                agent=self.physio_agent,
                tools=[GetPhysioTool(data=self.data), competitions_tool, current_date_tool],
                expected_output="Competition-aware recovery and adaptation analysis",
                output_file="analysis/physiology.md"
            ))

            # Run analysis if we have tasks
            if tasks:
                # Run analysis
                crew = Crew(
                    agents=[self.metrics_agent, self.activity_agent, self.physio_agent],
                    tasks=tasks,
                    verbose=True
                )
                crew.kickoff()

                # Create synthesis task using analysis tasks as context
                synthesis_task = Task(
                    name="synthesis",
                    description="Synthesize analysis results into comprehensive report with competition context",
                    agent=self.synthesis_agent,
                    context=tasks,
                    tools=[competitions_tool, current_date_tool],
                    expected_output="Competition-aware comprehensive synthesis with insights",
                    output_file="analysis/synthesis.md",
                    async_execution=True
                )

                # Run synthesis
                synthesis_crew = Crew(
                    agents=[self.synthesis_agent],
                    tasks=[synthesis_task],
                    verbose=True
                )
                
                result = synthesis_crew.kickoff()
                return str(result)

            return "No data available for analysis"
            
        except Exception as e:
            logger.error("Error in enhanced analysis: %s", str(e), exc_info=True)
            raise
