"""LangChain orchestrator for intelligent weekly training plan generation."""

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import asdict

from langchain_core.callbacks import get_usage_metadata_callback

from core.security.competitions import SecureCompetitionManager
from core.security.cache import SecureMetricsCache, SecureActivityCache, SecurePhysiologyCache
from .weekly_plan_chains import WeeklyPlanChains
from services.garmin import GarminData
from services.ai.utils.intermediate_storage import IntermediateResultStorage
from services.ai.utils.cost_tracker import CostTracker

logger = logging.getLogger(__name__)

class LangChainWeeklyPlanOrchestrator:
    """Orchestrates weekly planning using LangChain chains - no shared storage."""
    
    def __init__(self, user_id: str, athlete_name: str, garmin_data: GarminData, planning_context: str = "", progress_manager=None):
        """Initialize orchestrator for a single weekly planning execution.
        
        Args:
            user_id: User identifier
            athlete_name: Name of the athlete
            garmin_data: Garmin data for planning context
            planning_context: Custom user instructions/context for weekly planning
            progress_manager: Optional progress manager for live updates
        """
        self.user_id = user_id
        self.athlete_name = athlete_name
        self.planning_context = planning_context
        self.data = asdict(garmin_data)
        self.progress_manager = progress_manager
        
        # Initialize cost tracking
        self.cost_tracker = CostTracker()
        
        # Create execution-scoped chains
        self.chains = WeeklyPlanChains(user_id)
        
        # Get competition data and current date
        competition_manager = SecureCompetitionManager(user_id)
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
        
        logger.info(f"Initialized LangChain weekly plan orchestrator for user {user_id}")
    
    async def run_weekly_planning(self, store_intermediate: bool = True) -> tuple[str, dict[str, str]]:
        """Execute the complete weekly planning flow and return HTML result with intermediate results.
        
        Args:
            store_intermediate: Whether to store intermediate results to files (default: True)
        
        Returns:
            Tuple of (HTML formatted weekly plan, dict of intermediate results)
        """
        try:
            # Step 1: Generate Season Plan
            logger.info("Starting season plan generation")
            if self.progress_manager:
                await self.progress_manager.agent_started(
                    "Season Planning Agent",
                    "Creating season-long training strategy and competition periodization"
                )
            
            season_planner_chain = self.chains.create_season_planner_chain()
            
            # Track cost and execution time for this agent
            agent_start_time = datetime.now()
            with get_usage_metadata_callback() as cb:
                season_plan = await season_planner_chain.ainvoke({
                    'athlete_name': self.athlete_name,
                    'competitions': json.dumps(self.competitions, indent=2),
                    'current_date': json.dumps(self.current_date, indent=2)
                })
            
            # Calculate execution time and costs
            execution_time = (datetime.now() - agent_start_time).total_seconds()
            agent_cost_summary = self.cost_tracker.add_agent_cost(
                "Season Planning Agent", cb.usage_metadata, execution_time
            )
            
            if self.progress_manager:
                await self.progress_manager.agent_completed(
                    "Season Planning Agent",
                    plots_created=[],
                    tool_calls=0,
                    cost_usd=agent_cost_summary.total_cost_usd,
                    tokens=agent_cost_summary.total_tokens
                )
            logger.info("Season plan generation completed")
            
            # Step 2: Load cached analysis results
            logger.info("Loading cached analysis results")
            if self.progress_manager:
                await self.progress_manager.agent_started(
                    "Data Integration Agent",
                    "Loading previous analysis results for planning context"
                )
            
            # Track time for data loading (no LLM calls, so no cost)
            agent_start_time = datetime.now()
            
            metrics_cache = SecureMetricsCache(self.user_id)
            activity_cache = SecureActivityCache(self.user_id)
            physiology_cache = SecurePhysiologyCache(self.user_id)
            
            # Get cached results (fallback to empty if not available)
            metrics_analysis = metrics_cache.get() or ""
            activity_analysis = activity_cache.get() or ""
            physiology_analysis = physiology_cache.get() or ""
            
            # Calculate execution time (no costs for data loading)
            execution_time = (datetime.now() - agent_start_time).total_seconds()
            agent_cost_summary = self.cost_tracker.add_agent_cost(
                "Data Integration Agent", {}, execution_time
            )
            
            if self.progress_manager:
                await self.progress_manager.agent_completed(
                    "Data Integration Agent",
                    plots_created=[],
                    tool_calls=0,
                    cost_usd=agent_cost_summary.total_cost_usd,
                    tokens=agent_cost_summary.total_tokens
                )
            
            # Step 3: Generate Two-Week Plan
            logger.info("Starting two-week plan generation")
            if self.progress_manager:
                await self.progress_manager.agent_started(
                    "Weekly Planning Agent",
                    "Creating detailed two-week training schedule with daily workouts"
                )
            
            weekly_planner_chain = self.chains.create_weekly_planner_chain()
            
            # Track cost and execution time for this agent
            agent_start_time = datetime.now()
            with get_usage_metadata_callback() as cb:
                weekly_plan = await weekly_planner_chain.ainvoke({
                    'season_plan': season_plan,
                    'athlete_name': self.athlete_name,
                    'planning_context': self.planning_context,
                    'metrics_analysis': metrics_analysis,
                    'activity_analysis': activity_analysis,
                    'physiology_analysis': physiology_analysis,
                    'competitions': json.dumps(self.competitions, indent=2),
                    'current_date': json.dumps(self.current_date, indent=2),
                    'week_dates': json.dumps(self.week_dates, indent=2)
                })
            
            # Calculate execution time and costs
            execution_time = (datetime.now() - agent_start_time).total_seconds()
            agent_cost_summary = self.cost_tracker.add_agent_cost(
                "Weekly Planning Agent", cb.usage_metadata, execution_time
            )
            
            if self.progress_manager:
                await self.progress_manager.agent_completed(
                    "Weekly Planning Agent",
                    plots_created=[],
                    tool_calls=0,
                    cost_usd=agent_cost_summary.total_cost_usd,
                    tokens=agent_cost_summary.total_tokens
                )
            logger.info("Two-week plan generation completed")
            
            # Step 4: HTML Formatting
            logger.info("Starting HTML formatting")
            if self.progress_manager:
                await self.progress_manager.agent_started(
                    "Plan Formatter Agent",
                    "Formatting training plan into structured HTML report"
                )
            
            formatter_chain = self.chains.create_weekly_plan_formatter_chain()
            
            # Track cost and execution time for this agent
            agent_start_time = datetime.now()
            with get_usage_metadata_callback() as cb:
                html_result = await formatter_chain.ainvoke({
                    'season_plan': season_plan,
                    'weekly_plan': weekly_plan
                })
            
            # Calculate execution time and costs
            execution_time = (datetime.now() - agent_start_time).total_seconds()
            agent_cost_summary = self.cost_tracker.add_agent_cost(
                "Plan Formatter Agent", cb.usage_metadata, execution_time
            )
            
            if self.progress_manager:
                await self.progress_manager.agent_completed(
                    "Plan Formatter Agent",
                    plots_created=[],
                    tool_calls=0,
                    cost_usd=agent_cost_summary.total_cost_usd,
                    tokens=agent_cost_summary.total_tokens
                )
            logger.info("HTML formatting completed")
            
            # Get final cost summary
            cost_summary = self.cost_tracker.get_session_summary()
            
            # Package intermediate results with cost tracking
            intermediate_results = {
                'season_plan': season_plan,
                'weekly_plan': weekly_plan,
                'cost_summary': cost_summary
            }
            
            # Store intermediate results if requested
            if store_intermediate:
                try:
                    storage = IntermediateResultStorage(self.athlete_name)
                    stored_files = storage.store_weekly_plan_results(season_plan, weekly_plan)
                    logger.info(f"Stored {len(stored_files)} intermediate planning files for {self.athlete_name}")
                except Exception as e:
                    logger.warning(f"Failed to store intermediate planning results for {self.athlete_name}: {e}")
            
            logger.info(f"Weekly planning orchestration completed successfully for user {self.user_id}. "
                       f"Total cost: ${cost_summary['total_cost_usd']:.4f} ({cost_summary['total_tokens']:,} tokens)")
            return html_result, intermediate_results
            
        except Exception as e:
            logger.error(f"Weekly planning orchestration failed for user {self.user_id}: {str(e)}")
            raise


class LangChainWeeklyPlanFlow:
    """LangChain-based weekly planning flow for personalized training plans."""
    
    @staticmethod
    async def run_weekly_planning(user_id: str, athlete_name: str, garmin_data: GarminData, planning_context: str = "", progress_manager=None) -> tuple[str, dict[str, str]]:
        """Run complete weekly planning and return HTML result with intermediate results.
        
        Args:
            user_id: User identifier
            athlete_name: Name of the athlete
            garmin_data: Garmin data for planning context
            planning_context: Custom user instructions/context for weekly planning
            progress_manager: Optional progress manager for live updates
            
        Returns:
            Tuple of (HTML formatted weekly plan, dict of intermediate results)
        """
        orchestrator = LangChainWeeklyPlanOrchestrator(user_id, athlete_name, garmin_data, planning_context, progress_manager)
        return await orchestrator.run_weekly_planning()