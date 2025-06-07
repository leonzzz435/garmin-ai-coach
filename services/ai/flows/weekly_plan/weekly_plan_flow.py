"""Weekly Planning Flow implementation using CrewAI."""

import json
import logging
from datetime import datetime, timedelta
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

class WeeklyPlanState(BaseModel):
    """State management for weekly planning flow."""
    season_plan: str = ""     # New field for high-level season plan
    two_week_plan: str = ""   # Renamed from weekly_plan
    html_result: str = ""

@CrewBase
class WeeklyPlanCrew:
    """Weekly planning crew implementation."""

    def __init__(self, user_id: str, athlete_name: str, garmin_data: GarminData):
        """Initialize the weekly planning crew."""
        self.user_id = user_id
        self.athlete_name = athlete_name
        
        # Convert GarminData to dict
        self.data = asdict(garmin_data)
        
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
        
        # Calculate the two-week dates
        self.week_dates = []
        for i in range(14):
            day = current_date + timedelta(days=i)
            self.week_dates.append({
                'date': day.isoformat(),
                'date_formatted': day.strftime('%Y-%m-%d'),
                'day_name': day.strftime('%A')
            })
        
        # Ensure output directory exists
        Path("stuff/weekly_plans").mkdir(parents=True, exist_ok=True)
        logger.info("Initialized WeeklyPlanCrew")
    
    @agent
    def season_planner_agent(self) -> Agent:
        """Create season planning agent."""
        return Agent(
            config=self.agents_config['season_planner_agent'],
            llm=ModelSelector.get_llm(AgentRole.SEASON_PLANNER)
        )
    
    @agent
    def weekly_planner_agent(self) -> Agent:
        """Create weekly planning agent."""
        return Agent(
            config=self.agents_config['weekly_planner_agent'],
            llm=ModelSelector.get_llm(AgentRole.WORKOUT)
        )
    
    @agent
    def formatter_agent(self) -> Agent:
        """Create formatter agent."""
        return Agent(
            config=self.agents_config['formatter_agent'],
            llm=ModelSelector.get_llm(AgentRole.FORMATTER)
        )
    
    @task
    def season_plan_task(self) -> Task:
        """Create season planning task."""
        return Task(
            config=self.tasks_config['season_plan_task']
        )
    
    @task
    def weekly_plan_task(self) -> Task:
        """Create two-week planning task."""
        return Task(
            config=self.tasks_config['weekly_plan_task'],
            context=[self.season_plan_task()]
        )
    
    @task
    def formatter_task(self) -> Task:
        """Create formatter task."""
        return Task(
            config=self.tasks_config['formatter_task'],
            context=[self.weekly_plan_task()]
        )
    
    @crew
    def season_planner_crew(self) -> Crew:
        """Create season planner crew."""
        return Crew(
            agents=[self.season_planner_agent()],
            tasks=[self.season_plan_task()],
            process=Process.sequential
        )
    
    @crew
    def weekly_planner_crew(self) -> Crew:
        """Create two-week planning crew."""
        return Crew(
            agents=[self.weekly_planner_agent()],
            tasks=[self.weekly_plan_task()],
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

class WeeklyPlanFlow(Flow[WeeklyPlanState]):
    """Weekly planning flow implementation with integrated season planning."""
    
    def __init__(self, user_id: str, athlete_name: str, garmin_data: GarminData, athlete_context: str = ""):
        """Initialize the weekly planning flow."""
        super().__init__()
        self.crew_instance = WeeklyPlanCrew(user_id, athlete_name, garmin_data)
        self.athlete_name = athlete_name
        self.athlete_context = athlete_context
    
    @start()
    async def generate_season_plan(self):
        """Generate high-level season plan."""
        try:
            result = await self.crew_instance.season_planner_crew().kickoff_async(
                inputs={
                    'athlete_name': self.athlete_name,
                    'competitions': json.dumps(self.crew_instance.competitions, indent=2),
                    'current_date': json.dumps(self.crew_instance.current_date, indent=2)
                }
            )
            self.state.season_plan = result
            logger.info("Season Plan Generation completed")
            return result
        except Exception as e:
            logger.error(f"Season plan generation failed: {str(e)}")
            self.state.season_plan = f"Error during season plan generation: {str(e)}"
            raise
    
    @listen(generate_season_plan)
    async def generate_two_week_plan(self):
        """Generate two-week training plan."""
        try:
            # Load cached analysis results directly
            metrics_cache = SecureMetricsCache(self.crew_instance.user_id)
            activity_cache = SecureActivityCache(self.crew_instance.user_id)
            physiology_cache = SecurePhysiologyCache(self.crew_instance.user_id)
            
            # Get cached results
            metrics_analysis = metrics_cache.get() or ""
            activity_analysis = activity_cache.get() or ""
            physiology_analysis = physiology_cache.get() or ""
            
            result = await self.crew_instance.weekly_planner_crew().kickoff_async(
                inputs={
                    'athlete_name': self.athlete_name,
                    'athlete_context': self.athlete_context,
                    'metrics_analysis': metrics_analysis,
                    'activity_analysis': activity_analysis,
                    'physiology_analysis': physiology_analysis,
                    'competitions': json.dumps(self.crew_instance.competitions, indent=2),
                    'current_date': json.dumps(self.crew_instance.current_date, indent=2),
                    'week_dates': json.dumps(self.crew_instance.week_dates, indent=2)
                }
            )
            self.state.two_week_plan = result
            logger.info("Two-Week Plan Generation completed")
            return result
        except Exception as e:
            logger.error(f"Two-week plan generation failed: {str(e)}")
            self.state.two_week_plan = f"Error during two-week plan generation: {str(e)}"
            raise
    
    @listen(generate_two_week_plan)
    async def format_to_html(self):
        """Convert weekly plan markdown to HTML."""
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