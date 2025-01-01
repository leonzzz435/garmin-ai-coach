"""Enhanced AI framework implementation using CrewAI."""

import logging
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
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
            
            # Store input report for context
            input_metadata = {
                "timestamp": datetime.now().isoformat(),
                "type": "workout_input",
                "agent": {"role": workout_agent.role, "goal": workout_agent.goal}
            }
            self._store_logs(report, "workout_input", input_metadata)
            
            logger.info("Starting workout generation")
            result = crew.kickoff()
            logger.info("Completed workout generation")
            
            # Store and validate workout generation results
            workout_logs = str(result)
            if not workout_logs:
                error_metadata = {
                    "timestamp": datetime.now().isoformat(),
                    "status": "failed",
                    "error": "No workout generation results received"
                }
                self._store_logs("No workout results received", "workout_error", error_metadata)
                raise ValueError("No workout generation results received")
            
            # Extract the actual workout plan
            workout_result = self._extract_agent_result(workout_logs, workout_agent.role)
            if not workout_result:
                error_metadata = {
                    "timestamp": datetime.now().isoformat(),
                    "status": "failed",
                    "error": "Failed to extract workout plan from results"
                }
                self._store_logs(workout_logs, "workout_error", error_metadata)
                raise ValueError("Failed to extract workout plan from results")
            
            # Store successful results with metadata
            success_metadata = {
                "timestamp": datetime.now().isoformat(),
                "agent": {"role": workout_agent.role, "goal": workout_agent.goal},
                "status": "completed"
            }
            self._store_logs(workout_logs, "workout_generation", success_metadata)
            
            return workout_result
            
        except Exception as e:
            logger.error("Error in workout generation: %s", str(e), exc_info=True)
            error_metadata = {
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "error": str(e)
            }
            self._store_logs(str(e), "workout_error", error_metadata)
            raise

    def analyze(self) -> Dict[str, Any]:
        """Run the enhanced analysis process."""
        logger.info("Starting enhanced analysis process")
        
        try:
            # Create analysis tasks
            metrics_context = self._get_metrics_context()
            metrics_task = Task(
                description=f"""Analyze ONLY the provided training metrics data and identify patterns that exist within this data.
                Do not fabricate or estimate any missing values. If certain metrics are missing, acknowledge this rather than making assumptions.
                
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
                description=f"""Analyze ONLY the provided recent activities data and identify patterns that exist within this data.
                Do not fabricate or estimate any missing values. If certain activities or metrics are missing, acknowledge this rather than making assumptions.
                
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
                description=f"""Analyze ONLY the provided physiological data and identify patterns that exist within this data.
                Do not fabricate or estimate any missing values. If certain physiological markers are missing, acknowledge this rather than making assumptions.
                
                Data Structure:
                {json.dumps({k: type(v).__name__ for k, v in physio_context.items()}, indent=2)}
                
                Data Content:
                {json.dumps(physio_context, indent=2)}
                """,
                agent=self.physio_agent,
                expected_output="Analysis of recovery patterns, physiological adaptations, and health markers"
            )

            # Run and validate each analysis task individually
            analysis_results = []
            
            # Run metrics analysis
            metrics_data = self._get_metrics_context()
            logger.info("Metrics data available: %s", {k: bool(v) for k, v in metrics_data.items()})
            if any(metrics_data.values()):
                metrics_crew = Crew(
                    agents=[self.metrics_agent],
                    tasks=[metrics_task],
                    process=Process.sequential,
                    verbose=True
                )
                logger.info("Starting metrics analysis")
                metrics_result = metrics_crew.kickoff()
                if metrics_result:
                    analysis_results.append(str(metrics_result))
                    logger.info("Completed metrics analysis")
                else:
                    logger.warning("No metrics analysis results")
            else:
                logger.warning("No metrics data available for analysis")
            
            # Run activity analysis
            activity_data = self._get_activity_context()
            logger.info("Activity data available: %s", {k: bool(v) for k, v in activity_data.items()})
            if activity_data.get('recent_activities'):
                activity_crew = Crew(
                    agents=[self.activity_agent],
                    tasks=[activity_task],
                    process=Process.sequential,
                    verbose=True
                )
                logger.info("Starting activity analysis with %d activities", len(activity_data['recent_activities']))
                activity_result = activity_crew.kickoff()
                if activity_result:
                    analysis_results.append(str(activity_result))
                    logger.info("Completed activity analysis")
                else:
                    logger.warning("No activity analysis results")
            else:
                logger.warning("No activity data available for analysis")
            
            # Run physiological analysis
            physio_data = self._get_physio_context()
            logger.info("Physiological data available: %s", {k: bool(v) for k, v in physio_data.items()})
            if any(physio_data.values()):
                physio_crew = Crew(
                    agents=[self.physio_agent],
                    tasks=[physio_task],
                    process=Process.sequential,
                    verbose=True
                )
                logger.info("Starting physiological analysis")
                physio_result = physio_crew.kickoff()
                if physio_result:
                    analysis_results.append(str(physio_result))
                    logger.info("Completed physiological analysis")
                else:
                    logger.warning("No physiological analysis results")
            else:
                logger.warning("No physiological data available for analysis")
            
            # Combine and store analysis results
            analysis_logs = "\n\n".join(analysis_results)
            analysis_metadata = {
                "timestamp": datetime.now().isoformat(),
                "agents": [
                    {"role": agent.role, "goal": agent.goal}
                    for agent in [self.metrics_agent, self.activity_agent, self.physio_agent]
                ],
                "process": "sequential",
                "status": "completed"
            }
            self._store_logs(analysis_logs, "analysis", analysis_metadata)
            
            # Validate analysis results
            if not analysis_logs:
                analysis_metadata["status"] = "failed"
                self._store_logs("No analysis results received", "analysis_error", analysis_metadata)
                raise ValueError("No analysis results received from crew execution")
                
            # Convert CrewOutput objects to strings for synthesis
            synthesis_context = {
                'metrics_analysis': str(metrics_result) if metrics_result else None,
                'activity_analysis': str(activity_result) if activity_result else None,
                'physiological_analysis': str(physio_result) if physio_result else None
            }
            
            # Log available analyses
            logger.info("Available analyses for synthesis: %s", 
                       {k: bool(v) for k, v in synthesis_context.items()})
            
            synthesis_task = Task(
                description=f"""You have received analyses from specialized agents. Your task is to synthesize these into a comprehensive report.

                Available Analyses:
                - Metrics Analysis: {"Available" if metrics_result else "Not Available"}
                - Activity Analysis: {"Available" if activity_result else "Not Available"}
                - Physiological Analysis: {"Available" if physio_result else "Not Available"}

                For each available analysis, incorporate its insights into your synthesis. For any missing analyses, acknowledge their absence without making assumptions.

                Analysis Content:
                
                === Metrics Analysis ===
                {synthesis_context['metrics_analysis'] if synthesis_context['metrics_analysis'] else "Not Available"}

                === Activity Analysis ===
                {synthesis_context['activity_analysis'] if synthesis_context['activity_analysis'] else "Not Available"}

                === Physiological Analysis ===
                {synthesis_context['physiological_analysis'] if synthesis_context['physiological_analysis'] else "Not Available"}

                Create a comprehensive synthesis that:
                1. Clearly indicates which analyses are available and incorporated
                2. Synthesizes patterns and relationships only from available data
                3. Maintains a professional dashboard format with clear sections
                4. Uses appropriate emojis and formatting for readability
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
            
            # Store synthesis logs with metadata and return result
            synthesis_logs = str(synthesis_result)
            synthesis_metadata = {
                "timestamp": datetime.now().isoformat(),
                "agent": {"role": self.synthesis_agent.role, "goal": self.synthesis_agent.goal},
                "input_analyses": [agent.role for agent in [self.metrics_agent, self.activity_agent, self.physio_agent] 
                                 if self._extract_agent_result(analysis_logs, agent.role)],
                "status": "completed"
            }
            self._store_logs(synthesis_logs, "synthesis", synthesis_metadata)
            return synthesis_logs

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
            'sleep': self.data.get('sleep', []),
            'training_readiness': self.data.get('training_readiness', []),
            'daily_stats': self.data.get('daily_stats', {}),
            'physiological_markers': self.data.get('physiological_markers', {})
        }

    def _store_logs(self, logs: str, log_type: str, metadata: Dict[str, Any] = None) -> None:
        """Store analysis or synthesis logs to file with metadata.
        
        Args:
            logs: The log content to store
            log_type: Type of log ('analysis' or 'synthesis')
            metadata: Optional metadata to store with logs
        """
        try:
            # Create logs directory if it doesn't exist
            log_dir = Path("logs/agent_debug")
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate timestamp and filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{log_type}_{timestamp}.log"
            
            # Prepare log content with metadata
            content = []
            if metadata:
                content.append("=== Metadata ===")
                content.append(json.dumps(metadata, indent=2))
                content.append("\n=== Logs ===")
            content.append(logs)
            
            # Write to file
            log_path = log_dir / filename
            log_path.write_text("\n".join(content))
            logger.debug("Stored %s logs to %s", log_type, log_path)
            
        except Exception as e:
            logger.error("Error storing %s logs: %s", log_type, str(e))

    def _extract_agent_result(self, logs: str, agent_role: str) -> Optional[str]:
        """Extract an individual agent's analysis result from the crew logs."""
        try:
            if not logs:
                logger.warning(f"No logs provided for agent {agent_role}")
                return None
                
            # Validate data availability based on agent role
            if agent_role == "Metrics Analysis Specialist":
                metrics_data = self._get_metrics_context()
                if not any(metrics_data.values()):
                    logger.warning("No metrics data available for analysis")
                    return None
                    
            elif agent_role == "Activity Analysis Specialist":
                activity_data = self._get_activity_context()
                if not activity_data.get('recent_activities'):
                    logger.warning("No activity data available for analysis")
                    return None
                    
            elif agent_role == "Physiological Analysis Specialist":
                physio_data = self._get_physio_context()
                if not any(physio_data.values()):
                    logger.warning("No physiological data available for analysis")
                    return None
                
            # Return the logs if data validation passes
            return logs.strip()
            
        except Exception as e:
            logger.error("Error extracting result for agent %s: %s", agent_role, str(e))
            return None
