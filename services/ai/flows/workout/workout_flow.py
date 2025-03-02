"""Workout Flow implementation using CrewAI."""

import json
import logging
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel
from crewai import Agent, Task, Crew, Process
from crewai.project import CrewBase, agent, task, crew
from crewai.flow.flow import Flow, start, listen
from ...model_config import ModelSelector
from ...ai_settings import AgentRole
from dataclasses import asdict
from services.garmin import GarminData
from core.security.competitions import SecureCompetitionManager
from core.security.cache import SecureMetricsCache, SecureActivityCache, SecurePhysiologyCache
from core.security.users import UserTracker

logger = logging.getLogger(__name__)

class WorkoutState(BaseModel):
    """State management for workout flow."""
    activity_context: str = ""
    competition_plan: str = ""
    workout_result: str = ""
    html_result: str = ""

@CrewBase
class WorkoutCrew:
    """Workout crew implementation."""

    def __init__(self, user_id: str, athlete_name: str, garmin_data: GarminData):
        """Initialize the workout crew."""
        self.user_id = user_id
        self.athlete_name = athlete_name
        
        # Convert GarminData to dict
        self.data = asdict(garmin_data)
        
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
        Path("stuff/workouts").mkdir(parents=True, exist_ok=True)
        logger.info("Initialized WorkoutCrew")
        
    @agent
    def activity_context_agent(self) -> Agent:
        """Create activity context analysis agent."""
        return Agent(
            config=self.agents_config['activity_context_agent'],
            llm=ModelSelector.get_llm(AgentRole.ACTIVITY)
        )

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
        
    @agent
    def formatter_agent(self) -> Agent:
        """Create formatter agent."""
        return Agent(
            config=self.agents_config['formatter_agent'],
            llm=ModelSelector.get_llm(AgentRole.FORMATTER)
        )
        
    @task
    def activity_context_task(self) -> Task:
        """Create activity context analysis task."""
        return Task(
            config=self.tasks_config['activity_context_task']
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
            context=[self.activity_context_task(), self.competition_planning_task()]
        )
        
    @task
    def formatter_task(self) -> Task:
        """Create formatter task."""
        task_config = self.tasks_config['formatter_task']
        task_config['context'] = [self.workout_task()]
        return Task(config=task_config)

    @crew
    def activity_context_crew(self) -> Crew:
        """Create activity context analysis crew."""
        return Crew(
            agents=[self.activity_context_agent()],
            tasks=[self.activity_context_task()],
            process=Process.sequential
        )

    @crew
    def competition_planning_crew(self) -> Crew:
        """Create competition planning crew."""
        return Crew(
            agents=[self.competition_planner_agent()],
            tasks=[self.competition_planning_task()],
            process=Process.sequential
        )

    @crew
    def workout_crew(self) -> Crew:
        """Create workout generation crew."""
        return Crew(
            agents=[self.workout_agent()],
            tasks=[self.workout_task()],
            process=Process.sequential
        )
        
    @crew
    def formatter_crew(self) -> Crew:
        """Create formatter crew."""
        return Crew(
            agents=[self.formatter_agent()],
            tasks=[self.formatter_task()],
            process=Process.sequential
        )

class WorkoutFlow(Flow[WorkoutState]):
    """Workout flow implementation."""
    
    def __init__(self, user_id: str, athlete_name: str, garmin_data: GarminData, athlete_context: str = ""):
        """Initialize the workout flow."""
        super().__init__()
        self.crew_instance = WorkoutCrew(user_id, athlete_name, garmin_data)
        self.athlete_name = athlete_name
        self.athlete_context = athlete_context

    @start()
    async def analyze_activity_context(self):
        """Analyze recent activity context."""
        activities_data = self.crew_instance.data.get('recent_activities', [])
        user_profile = self.crew_instance.data.get('user_profile', {})
        
        result = await self.crew_instance.activity_context_crew().kickoff_async(
            inputs={
                'athlete_name': self.athlete_name,
                'user_profile': json.dumps(user_profile, indent=2),
                'activities_data': json.dumps(activities_data, indent=2),
                'current_date': json.dumps(self.crew_instance.current_date, indent=2)
            }
        )
        self.state.activity_context = result
        logger.info("Activity Context Analysis completed")
        return result

    @listen(analyze_activity_context)
    async def plan_competition(self):
        """Create competition-based training plan."""
        result = await self.crew_instance.competition_planning_crew().kickoff_async(
            inputs={
                'athlete_name': self.athlete_name,
                'user_profile': json.dumps(self.crew_instance.data.get('user_profile', {}), indent=2),
                'competitions': json.dumps(self.crew_instance.competitions, indent=2),
                'current_date': json.dumps(self.crew_instance.current_date, indent=2)
            }
        )
        self.state.competition_plan = result
        logger.info("Competition Planning completed")
        return result

    @listen(plan_competition)
    async def generate_workout(self):
        """Generate personalized workout options."""
        # Load cached analysis results (stored as strings)
        metrics_cache = SecureMetricsCache(self.crew_instance.user_id)
        physiology_cache = SecurePhysiologyCache(self.crew_instance.user_id)
        
        # Get cached results (already in string format)
        metrics_analysis = metrics_cache.get()
        physiology_analysis = physiology_cache.get()
        
        result = await self.crew_instance.workout_crew().kickoff_async(
            inputs={
                'athlete_name': self.athlete_name,
                'athlete_context': self.athlete_context,
                'metrics_analysis': metrics_analysis if metrics_analysis else "",
                'physiology_analysis': physiology_analysis if physiology_analysis else "",
                'current_date': json.dumps(self.crew_instance.current_date, indent=2),
                'style_guide': self.crew_instance.style_guide,
                'meta': self.crew_instance.meta
            }
        )
        self.state.workout_result = result
        logger.info("Workout Generation completed")
        return result
        
    @listen(generate_workout)
    async def format_to_html(self):
        """Convert workout markdown to HTML."""
        try:
            logger.info("Starting HTML formatting")
            result = await self.crew_instance.formatter_crew().kickoff_async()
            self.state.html_result = result
            logger.info("HTML formatting completed successfully")
            return result
        except Exception as e:
            logger.error(f"HTML formatting failed: {str(e)}")
            self.state.html_result = f"Error during HTML formatting: {str(e)}"
            raise
