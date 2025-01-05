"""Workout Flow implementation using CrewAI."""

import logging
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel
from crewai import Agent, Task, Crew, Process
from crewai.project import CrewBase, agent, task, crew
from crewai.flow.flow import Flow, start
from ...model_config import ModelSelector
from ...ai_settings import AgentRole
from dataclasses import asdict
from services.garmin import GarminData
from core.security.competitions import SecureCompetitionManager

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
        
        # Store analysis report
        self.analysis_report = analysis_report
        
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
        Path("stuff/workouts").mkdir(parents=True, exist_ok=True)
        logger.info("Initialized WorkoutCrew")
        
    @agent
    def competition_planner_agent(self) -> Agent:
        """Create competition planning agent."""
        return Agent(
            config=self.agents_config['competition_planner_agent'],
            llm=ModelSelector.get_llm(AgentRole.COMPETITION_PLANNER),
        )

    @agent
    def workout_agent(self) -> Agent:
        """Create workout generation agent."""
        return Agent(
            config=self.agents_config['workout_agent'],
            llm=ModelSelector.get_llm(AgentRole.WORKOUT),
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
        # Prepare data for workout generation
        metrics_data = {
            'training_load_history': self.crew_instance.data.get('training_load_history', []),
        }
        activities_data = {
            'recent_activities': self.crew_instance.data.get('recent_activities', []),
            'training_status': self.crew_instance.data.get('training_status', {})
        }
        
        import json
        
        # Properly serialize JSON data
        inputs = {
            'athlete_name': str(self.athlete_name),
            'analysis_report': str(self.crew_instance.analysis_report),
            'metrics_data': json.dumps(metrics_data, indent=2),
            'activities_data': json.dumps(activities_data, indent=2),
            'competitions': json.dumps(self.crew_instance.competitions, indent=2),
            'current_date': json.dumps(self.crew_instance.current_date, indent=2)
        }
        
        # Remove any empty strings from inputs
        inputs = {k: v for k, v in inputs.items() if v and v.strip()}
        
        result = await self.crew_instance.crew().kickoff_async(inputs=inputs)
        self.state.workout_result = result
        logger.info("Workout generation completed")
        return result
