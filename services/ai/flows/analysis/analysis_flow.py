"""Analysis Flow implementation using CrewAI."""

import logging
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel
from crewai import Agent, Task, Crew, Process
from crewai.flow.flow import Flow, start, listen
from crewai.project import CrewBase, agent, task, crew
from dataclasses import asdict

from core.security.competitions import SecureCompetitionManager
from core.security.users import UserTracker

from ...model_config import ModelSelector
from ...ai_settings import AgentRole
from services.garmin import GarminData

logger = logging.getLogger(__name__)

class AnalysisState(BaseModel):
    """State management for analysis flow."""
    metrics_result: str = ""
    activities_result: str = ""
    physiology_result: str = ""
    synthesis_result: str = ""
    html_result: str = ""

@CrewBase
class AnalysisCrew:
    """Analysis crew implementation."""

    def __init__(self, garmin_data: GarminData, user_id: str, athlete_name: str):
        """Initialize the analysis crew."""
        self.data = asdict(garmin_data)
        self.user_id = user_id
        self.athlete_name = athlete_name
        
        # Get user meta information
        user_tracker = UserTracker()
        self.meta = user_tracker.get_meta(user_id)
        
        # Get competition data and current date
        competition_manager = SecureCompetitionManager(self.user_id)
        self.competitions = [
            {
                'name': comp.name,
                'date': comp.date.isoformat(),
                'race_type': comp.race_type,
                'priority': comp.priority.value,
                'target_time': comp.target_time,
                'location': comp.location,
                'notes': comp.notes
            }
            for comp in competition_manager.get_upcoming_competitions()
        ]
        current_date = datetime.now()
        self.current_date = {
            'current_date': current_date.isoformat(),
            'date_formatted': current_date.strftime('%Y-%m-%d')
        }
        
        # Load style guide for user-facing outputs
        try:
            with open('agent_docs/styleGuide.md', 'r') as f:
                self.style_guide = f.read()
        except Exception as e:
            logger.error(f"Failed to load style guide: {e}")
            self.style_guide = ""
        
        # Ensure output directory exists
        Path("stuff/analysis").mkdir(parents=True, exist_ok=True)
        logger.info("Initialized AnalysisCrew with data keys: %s", list(self.data.keys()))

    @agent
    def metrics_agent(self) -> Agent:
        """Create metrics analysis agent."""
        return Agent(
            config=self.agents_config['metrics_agent'],
            llm=ModelSelector.get_llm(AgentRole.METRICS)
        )

    @agent
    def activity_agent(self) -> Agent:
        """Create activity analysis agent."""
        return Agent(
            config=self.agents_config['activity_agent'],
            llm=ModelSelector.get_llm(AgentRole.ACTIVITY)
        )

    @agent
    def physiology_agent(self) -> Agent:
        """Create physiological analysis agent."""
        return Agent(
            config=self.agents_config['physiology_agent'],
            llm=ModelSelector.get_llm(AgentRole.PHYSIO)
        )

    @agent
    def synthesis_agent(self) -> Agent:
        """Create synthesis agent."""
        return Agent(
            config=self.agents_config['synthesis_agent'],
            llm=ModelSelector.get_llm(AgentRole.SYNTHESIS)
        )
        
    @agent
    def formatter_agent(self) -> Agent:
        """Create formatter agent."""
        return Agent(
            config=self.agents_config['formatter_agent'],
            llm=ModelSelector.get_llm(AgentRole.FORMATTER)
        )

    @task
    def metrics_task(self) -> Task:
        """Create metrics analysis task."""
        return Task(
            config=self.tasks_config['metrics_task']
        )

    @task
    def activities_task(self) -> Task:
        """Create activities analysis task."""
        return Task(
            config=self.tasks_config['activities_task']
        )

    @task
    def physiology_task(self) -> Task:
        """Create physiology analysis task."""
        return Task(
            config=self.tasks_config['physiology_task']
        )

    @task
    def synthesis_task(self) -> Task:
        """Create synthesis task."""
        task_config = self.tasks_config['synthesis_task']
        task_config['context'] = [
            self.metrics_task(),
            self.activities_task(),
            self.physiology_task()
        ]
        return Task(config=task_config)
        
    @task
    def formatter_task(self) -> Task:
        """Create formatter task."""
        task_config = self.tasks_config['formatter_task']
        task_config['context'] = [self.synthesis_task()]
        return Task(config=task_config)

    @crew
    def metrics_crew(self) -> Crew:
        """Create metrics analysis crew."""
        return Crew(
            agents=[self.metrics_agent()],
            tasks=[self.metrics_task()],
            process=Process.sequential,
            #verbose=True,
        )

    @crew
    def activities_crew(self) -> Crew:
        """Create activities analysis crew."""
        return Crew(
            agents=[self.activity_agent()],
            tasks=[self.activities_task()],
            process=Process.sequential,
            #verbose=True,
        )

    @crew
    def physiology_crew(self) -> Crew:
        """Create physiology analysis crew."""
        return Crew(
            agents=[self.physiology_agent()],
            tasks=[self.physiology_task()],
            process=Process.sequential,
            #verbose=True,
        )

    @crew
    def synthesis_crew(self) -> Crew:
        """Create synthesis crew."""
        return Crew(
            agents=[self.synthesis_agent()],
            tasks=[self.synthesis_task()],
            process=Process.sequential,
            #verbose=True,
        )
        
    @crew
    def formatter_crew(self) -> Crew:
        """Create formatter crew."""
        return Crew(
            agents=[self.formatter_agent()],
            tasks=[self.formatter_task()],
            process=Process.sequential
        )

class AnalysisFlow(Flow[AnalysisState]):
    """Analysis flow implementation."""
    
    def __init__(self, garmin_data: GarminData, user_id: str, athlete_name: str):
        """Initialize the analysis flow."""
        super().__init__()
        self.analysis_crew = AnalysisCrew(garmin_data, user_id, athlete_name)
        self.athlete_name = athlete_name
    
    @start()
    async def analyze_metrics(self):
        """Perform metrics analysis."""
        try:
            metrics_data = {
                'training_load_history': self.analysis_crew.data.get('training_load_history', []),
                'vo2_max_history': self.analysis_crew.data.get('vo2_max_history', []),
                'training_status': self.analysis_crew.data.get('training_status', {}),
                #'body_metrics': self.analysis_crew.data.get('body_metrics', {})
            }
            logger.info("Starting metrics analysis")
            result = await self.analysis_crew.metrics_crew().kickoff_async(
                inputs={
                    'data': metrics_data,
                    'competitions': self.analysis_crew.competitions,
                    'current_date': self.analysis_crew.current_date
                }
            )
            self.state.metrics_result = result
            logger.info("Metrics Analysis completed successfully")
            return result
        except Exception as e:
            logger.error(f"Metrics Analysis failed: {str(e)}")
            self.state.metrics_result = f"Error during metrics analysis: {str(e)}"
            raise

    @listen(analyze_metrics)
    async def analyze_activities(self):
        """Perform activities analysis."""
        try:
            activities_data = {
                'recent_activities': self.analysis_crew.data.get('recent_activities', []),  # Includes laps and weather
                'training_status': self.analysis_crew.data.get('training_status', {})
            }
            logger.info("Starting activities analysis")
            result = await self.analysis_crew.activities_crew().kickoff_async(
                inputs={
                    'data': activities_data,
                    'competitions': self.analysis_crew.competitions,
                    'current_date': self.analysis_crew.current_date
                }
            )
            self.state.activities_result = result
            logger.info("Activities Analysis completed successfully")
            return result
        except Exception as e:
            logger.error(f"Activities Analysis failed: {str(e)}")
            self.state.activities_result = f"Error during activities analysis: {str(e)}"
            raise

    @listen(analyze_activities)
    async def analyze_physiology(self):
        """Perform physiology analysis."""
        try:
            physio_data = {
                'recovery_indicators': self.analysis_crew.data.get('recovery_indicators', []),  # Includes sleep and stress data
                'daily_stats': self.analysis_crew.data.get('daily_stats', {}),
                'physiological_markers': self.analysis_crew.data.get('physiological_markers', {})
            }
            logger.info("Starting physiology analysis")
            result = await self.analysis_crew.physiology_crew().kickoff_async(
                inputs={
                    'data': physio_data,
                    'competitions': self.analysis_crew.competitions,
                    'current_date': self.analysis_crew.current_date
                }
            )
            self.state.physiology_result = result
            logger.info("Physiology Analysis completed successfully")
            return result
        except Exception as e:
            logger.error(f"Physiology Analysis failed: {str(e)}")
            self.state.physiology_result = f"Error during physiology analysis: {str(e)}"
            raise

    @listen(analyze_physiology)
    async def synthesize_results(self):
        """Combine analysis results into a synthesis report."""
        try:
            logger.info("Starting synthesis")
            result = await self.analysis_crew.synthesis_crew().kickoff_async(
                inputs={
                    'athlete_name': self.athlete_name,
                    'competitions': self.analysis_crew.competitions,
                    'current_date': self.analysis_crew.current_date,
                    'style_guide': self.analysis_crew.style_guide,
                    'meta': self.analysis_crew.meta
                }
            )
            self.state.synthesis_result = result
            logger.info("Synthesis completed successfully")
            return result
        except Exception as e:
            logger.error(f"Synthesis failed: {str(e)}")
            self.state.synthesis_result = f"Error during synthesis: {str(e)}"
            raise
            
    @listen(synthesize_results)
    async def format_to_html(self):
        """Convert synthesis markdown to HTML."""
        try:
            logger.info("Starting HTML formatting")
            result = await self.analysis_crew.formatter_crew().kickoff_async()
            self.state.html_result = result
            logger.info("HTML formatting completed successfully")
            return result
        except Exception as e:
            logger.error(f"HTML formatting failed: {str(e)}")
            self.state.html_result = f"Error during HTML formatting: {str(e)}"
            raise
