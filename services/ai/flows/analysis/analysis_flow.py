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

@CrewBase
class AnalysisCrew:
    """Analysis crew implementation."""

    def __init__(self, garmin_data: GarminData, user_id: str, athlete_name: str):
        """Initialize the analysis crew."""
        self.data = asdict(garmin_data)
        self.user_id = user_id
        self.athlete_name = athlete_name
        
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
        
        # Ensure output directory exists
        Path("analysis").mkdir(exist_ok=True)
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

    @crew
    def metrics_crew(self) -> Crew:
        """Create metrics analysis crew."""
        return Crew(
            agents=[self.metrics_agent()],
            tasks=[self.metrics_task()],
            process=Process.sequential
        )

    @crew
    def activities_crew(self) -> Crew:
        """Create activities analysis crew."""
        return Crew(
            agents=[self.activity_agent()],
            tasks=[self.activities_task()],
            process=Process.sequential
        )

    @crew
    def physiology_crew(self) -> Crew:
        """Create physiology analysis crew."""
        return Crew(
            agents=[self.physiology_agent()],
            tasks=[self.physiology_task()],
            process=Process.sequential
        )

    @crew
    def synthesis_crew(self) -> Crew:
        """Create synthesis crew."""
        return Crew(
            agents=[self.synthesis_agent()],
            tasks=[self.synthesis_task()],
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
        metrics_data = {
            'training_load_history': self.analysis_crew.data.get('training_load_history', []),
            'vo2_max_history': self.analysis_crew.data.get('vo2_max_history', []),
            'endurance_score_history': self.analysis_crew.data.get('endurance_score_history', []),
            'hill_score': self.analysis_crew.data.get('hill_score', []),
            'race_predictions': self.analysis_crew.data.get('race_predictions', [])
        }
        result = await self.analysis_crew.metrics_crew().kickoff_async(
            inputs={
                'data': metrics_data,
                'competitions': self.analysis_crew.competitions,
                'current_date': self.analysis_crew.current_date
            }
        )
        self.state.metrics_result = result
        logger.info("Metrics Analysis completed")
        return result

    @listen(analyze_metrics)
    async def analyze_activities(self):
        """Perform activities analysis."""
        activities_data = {
            'recent_activities': self.analysis_crew.data.get('recent_activities', []),
            'training_status': self.analysis_crew.data.get('training_status', {})
        }
        result = await self.analysis_crew.activities_crew().kickoff_async(
            inputs={
                'data': activities_data,
                'competitions': self.analysis_crew.competitions,
                'current_date': self.analysis_crew.current_date
            }
        )
        self.state.activities_result = result
        logger.info("Activities Analysis completed")
        return result

    @listen(analyze_activities)
    async def analyze_physiology(self):
        """Perform physiology analysis."""
        physio_data = {
            'sleep': self.analysis_crew.data.get('sleep', []),
            'training_readiness': self.analysis_crew.data.get('training_readiness', []),
            'daily_stats': self.analysis_crew.data.get('daily_stats', {}),
            'physiological_markers': self.analysis_crew.data.get('physiological_markers', {})
        }
        result = await self.analysis_crew.physiology_crew().kickoff_async(
            inputs={
                'data': physio_data,
                'competitions': self.analysis_crew.competitions,
                'current_date': self.analysis_crew.current_date
            }
        )
        self.state.physiology_result = result
        logger.info("Physiology Analysis completed")
        return result

    @listen(analyze_physiology)
    async def synthesize_results(self):
        """Combine analysis results into a synthesis report."""
        result = await self.analysis_crew.synthesis_crew().kickoff_async(
            inputs={
                'athlete_name': self.athlete_name,
                'competitions': self.analysis_crew.competitions,
                'current_date': self.analysis_crew.current_date
            }
        )
        self.state.synthesis_result = result
        logger.info("Synthesis completed")
        return result
