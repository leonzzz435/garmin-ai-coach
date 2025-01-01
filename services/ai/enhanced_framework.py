"""Enhanced AI framework implementation using CrewAI."""

import logging
import json
from typing import Dict, Any, List
from dataclasses import asdict
from crewai import Agent, Task, Crew, Process, LLM
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
        logger.info("Starting workout generation")
        
        try:
            workout_agent = self.create_workout_agent()
            
            workout_task = Task(
                description=workout_generation_prompt % report,
                agent=workout_agent,
                expected_output="Detailed workout plans for each discipline"
            )
            
            crew = Crew(
                agents=[workout_agent],
                tasks=[workout_task],
                process=Process.sequential,
                verbose=True
            )
            
            logger.info("Starting workout generation")
            result = crew.kickoff()
            logger.info("Completed workout generation")
            
            return str(result)
            
        except Exception as e:
            logger.error("Error in workout generation: %s", str(e), exc_info=True)
            raise

    def analyze(self) -> Dict[str, Any]:
        """Run the enhanced analysis process."""
        logger.info("Starting enhanced analysis process")
        
        try:
            # Create analysis tasks
            metrics_context = self._get_metrics_context()
            metrics_task = Task(
                description=f"""Analyze training metrics and identify key patterns.
                
                Data Structure:
                {json.dumps({k: type(v).__name__ for k, v in metrics_context.items()}, indent=2)}
                
                Data Content:
                {json.dumps(metrics_context, indent=2)}
                """,
                agent=self.metrics_agent,
                expected_output="Detailed analysis of training metrics including load patterns, performance trends, and key indicators"
            )

            activity_context = self._get_activity_context()
            activity_task = Task(
                description=f"""Analyze recent activities and execution patterns.
                
                Data Structure:
                {json.dumps({k: type(v).__name__ for k, v in activity_context.items()}, indent=2)}
                
                Data Content:
                {json.dumps(activity_context, indent=2)}
                """,
                agent=self.activity_agent,
                expected_output="Analysis of workout execution, patterns, and technical aspects across different activities"
            )

            physio_context = self._get_physio_context()
            physio_task = Task(
                description=f"""Analyze physiological responses and patterns.
                
                Data Structure:
                {json.dumps({k: type(v).__name__ for k, v in physio_context.items()}, indent=2)}
                
                Data Content:
                {json.dumps(physio_context, indent=2)}
                """,
                agent=self.physio_agent,
                expected_output="Analysis of recovery patterns, physiological adaptations, and health markers"
            )

            # Run individual analysis tasks first
            crew_analysis = Crew(
                agents=[self.metrics_agent, self.activity_agent, self.physio_agent],
                tasks=[metrics_task, activity_task, physio_task],
                process=Process.sequential,
                verbose=True
            )
            
            logger.info("Starting analysis tasks")
            analysis_results = crew_analysis.kickoff()
            logger.info("Completed analysis tasks")
            
            # Convert CrewOutput to string representation for synthesis
            analysis_results_str = str(analysis_results)
            
            # Create synthesis task with analysis results
            synthesis_context = {
                'previous_analyses': analysis_results_str
            }
            
            synthesis_task = Task(
                description=f"""Synthesize analyses into comprehensive insights.
                
                Data Structure:
                {json.dumps({k: type(v).__name__ for k, v in synthesis_context.items()}, indent=2)}
                
                Data Content:
                {json.dumps(synthesis_context, indent=2)}
                """,
                agent=self.synthesis_agent,
                expected_output="Comprehensive synthesis of all analyses with actionable recommendations"
            )
            
            # Run synthesis
            crew_synthesis = Crew(
                agents=[self.synthesis_agent],
                tasks=[synthesis_task],
                process=Process.sequential,
                verbose=True
            )
            
            logger.info("Starting synthesis")
            synthesis_result = crew_synthesis.kickoff()
            logger.info("Completed synthesis")
            
            # Return the synthesis result directly
            return str(synthesis_result)

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
