"""Enhanced AI framework implementation using CrewAI."""

import logging
from typing import Dict, Any
from dataclasses import asdict
from crewai import Agent, Task, Crew, Process

from services.garmin import GarminData
from .prompts import (
    enhanced_system,
    metrics_agent_prompt,
    activity_agent_prompt,
    physiological_agent_prompt,
    synthesis_agent_prompt
)

logger = logging.getLogger(__name__)

class EnhancedAnalyzer:
    """Enhanced analysis system using specialized AI agents."""
    
    def __init__(self, garmin_data: GarminData):
        """Initialize the enhanced analyzer with athlete data."""
        self.data = asdict(garmin_data)
        logger.info("Initializing EnhancedAnalyzer with data keys: %s", list(self.data.keys()))
        
        # Initialize specialized agents
        self.metrics_agent = Agent(
            role="Metrics Analysis Specialist",
            goal="Analyze training metrics and patterns",
            backstory=metrics_agent_prompt,
            verbose=True
        )
        
        self.activity_agent = Agent(
            role="Activity Analysis Specialist",
            goal="Analyze workout execution and patterns",
            backstory=activity_agent_prompt,
            verbose=True
        )
        
        self.physio_agent = Agent(
            role="Physiological Analysis Specialist",
            goal="Analyze physiological responses and adaptations",
            backstory=physiological_agent_prompt,
            verbose=True
        )
        
        self.synthesis_agent = Agent(
            role="Training Synthesis Specialist",
            goal="Synthesize analyses into actionable insights",
            backstory=synthesis_agent_prompt,
            verbose=True
        )

    def analyze(self) -> Dict[str, Any]:
        """Run the enhanced analysis process."""
        logger.info("Starting enhanced analysis process")
        
        try:
            # Create analysis tasks
            metrics_task = Task(
                description="Analyze training metrics and identify key patterns",
                agent=self.metrics_agent,
                context=self._get_metrics_context()
            )

            activity_task = Task(
                description="Analyze recent activities and execution patterns",
                agent=self.activity_agent,
                context=self._get_activity_context()
            )

            physio_task = Task(
                description="Analyze physiological responses and patterns",
                agent=self.physio_agent,
                context=self._get_physio_context()
            )

            # Create synthesis task that builds on analysis results
            synthesis_task = Task(
                description="Synthesize analyses into comprehensive insights",
                agent=self.synthesis_agent,
                context=[metrics_task, activity_task, physio_task]
            )

            # Create and run the analysis crew
            crew = Crew(
                agents=[
                    self.metrics_agent,
                    self.activity_agent,
                    self.physio_agent,
                    self.synthesis_agent
                ],
                tasks=[
                    metrics_task,
                    activity_task,
                    physio_task,
                    synthesis_task
                ],
                process=Process.sequential,
                verbose=True
            )

            logger.info("Starting crew analysis")
            result = crew.kickoff()
            logger.info("Completed crew analysis")
            
            return result

        except Exception as e:
            logger.error("Error in enhanced analysis: %s", str(e), exc_info=True)
            raise

    def _get_metrics_context(self) -> Dict[str, Any]:
        """Get relevant metrics data for analysis."""
        return {
            'training_load_history': self.data.get('training_load_history', []),
            'vo2_max_history': self.data.get('vo2_max_history', []),
            'endurance_score_history': self.data.get('endurance_score_history', []),
            'hill_score': self.data.get('hill_score', []),
            'race_predictions': self.data.get('race_predictions', [])
        }

    def _get_activity_context(self) -> Dict[str, Any]:
        """Get relevant activity data for analysis."""
        return {
            'recent_activities': self.data.get('recent_activities', []),
            'training_status': self.data.get('training_status', {})
        }

    def _get_physio_context(self) -> Dict[str, Any]:
        """Get relevant physiological data for analysis."""
        return {
            'physiological_markers': self.data.get('physiological_markers', {}),
            'recovery_indicators': self.data.get('recovery_indicators', []),
            'training_readiness': self.data.get('training_readiness', []),
            'daily_stats': self.data.get('daily_stats', {})
        }
