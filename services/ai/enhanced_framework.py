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

from services.garmin import GarminData
from .prompts import (
    enhanced_system,
    metrics_agent_prompt,
    activity_agent_prompt,
    physiological_agent_prompt,
    synthesis_agent_prompt,
    workout_system,
    workout_generation_prompt
)

logger = logging.getLogger(__name__)

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
    
    def __init__(self, garmin_data: GarminData):
        """Initialize the enhanced analyzer with athlete data."""
        self.data = asdict(garmin_data)
        logger.info("Initializing EnhancedAnalyzer with data keys: %s", list(self.data.keys()))
        
        # Configure Claude LLM
        self.llm = LLM(
            model="claude-3-5-sonnet-20241022",
            base_url="https://api.anthropic.com",
            max_tokens=8000,
            api_key=get_config().anthropic_api_key
        )
        
        # Initialize specialized agents
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
            backstory=workout_system,
            verbose=True,
            llm=self.llm
        )

    def generate_workouts(self, report: str) -> str:
        """Generate workout plans based on analysis report."""
        try:
            # Ensure output directory exists
            Path("workouts").mkdir(exist_ok=True)
            
            # Create workout generation task
            workout_task = Task(
                name="workout_generation",
                description=workout_generation_prompt % report,
                agent=self.create_workout_agent(),
                expected_output="Detailed workout plans for each discipline",
                output_file="workouts/generated.md"
            )
            
            # Run workout generation
            crew = Crew(
                agents=[workout_task.agent],
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
            
            # Add tasks with their respective tools
            tasks.append(Task(
                name="metrics_analysis",
                description="Analyze training metrics and identify patterns",
                agent=self.metrics_agent,
                tools=[GetMetricsTool(data=self.data)],
                expected_output="Metrics analysis with patterns and trends",
                output_file="analysis/metrics.md"
            ))

            tasks.append(Task(
                name="activity_analysis",
                description="Analyze workout execution and identify patterns",
                agent=self.activity_agent,
                tools=[GetActivitiesTool(data=self.data)],
                expected_output="Activity patterns and execution analysis",
                output_file="analysis/activities.md"
            ))

            tasks.append(Task(
                name="physio_analysis",
                description="Analyze physiological responses and adaptations",
                agent=self.physio_agent,
                tools=[GetPhysioTool(data=self.data)],
                expected_output="Recovery and adaptation analysis",
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
                    description="Synthesize analysis results into comprehensive report",
                    agent=self.synthesis_agent,
                    context=tasks,
                    expected_output="Comprehensive synthesis with insights",
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
