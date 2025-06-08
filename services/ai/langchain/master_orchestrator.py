"""Master orchestrator that combines analysis and weekly planning flows."""

import logging
from typing import Dict, Any, Tuple
from services.garmin import GarminData
from .analysis_orchestrator import LangChainAnalysisFlow
from .weekly_plan_orchestrator import LangChainWeeklyPlanFlow

logger = logging.getLogger(__name__)

class MasterOrchestrator:
    """Simple orchestrator that runs both analysis and planning sequentially."""
    
    @staticmethod
    async def run_full_analysis(user_id: str, athlete_name: str,
                               garmin_data: GarminData, analysis_context: str = "",
                               planning_context: str = "") -> Dict[str, Any]:
        """
        Run complete analysis and weekly planning in sequence.
        
        Args:
            user_id: User identifier
            athlete_name: Name of the athlete
            garmin_data: Garmin data for analysis and planning
            analysis_context: Context for data analysis interpretation (health, stress, etc.)
            planning_context: Context for weekly planning (constraints, goals, etc.)
            
        Returns:
            Dict containing both analysis and planning results:
            {
                'analysis_html': str,
                'planning_html': str,
                'analysis_intermediates': Dict[str, str],
                'planning_intermediates': Dict[str, str]
            }
        """
        try:
            logger.info(f"Starting full analysis for user {user_id}")
            
            # Step 1: Run Analysis Orchestrator
            logger.info("Running analysis orchestrator...")
            analysis_html, analysis_intermediates = await LangChainAnalysisFlow.run_analysis(
                garmin_data, user_id, athlete_name, analysis_context
            )
            logger.info("Analysis orchestrator completed successfully")
            
            # Step 2: Run Weekly Plan Orchestrator
            logger.info("Running weekly plan orchestrator...")
            planning_html, planning_intermediates = await LangChainWeeklyPlanFlow.run_weekly_planning(
                user_id, athlete_name, garmin_data, planning_context
            )
            logger.info("Weekly plan orchestrator completed successfully")
            
            # Return combined results
            result = {
                'analysis_html': analysis_html,
                'planning_html': planning_html,
                'analysis_intermediates': analysis_intermediates,
                'planning_intermediates': planning_intermediates
            }
            
            logger.info(f"Full analysis completed successfully for user {user_id}")
            return result
            
        except Exception as e:
            logger.error(f"Full analysis failed for user {user_id}: {str(e)}")
            raise


class LangChainFullAnalysisFlow:
    """LangChain-based full analysis flow combining training insights and weekly planning."""
    
    @staticmethod
    async def run_full_analysis(user_id: str, athlete_name: str,
                               garmin_data: GarminData, analysis_context: str = "",
                               planning_context: str = "") -> Dict[str, Any]:
        """
        Run complete analysis and weekly planning.
        
        Args:
            user_id: User identifier
            athlete_name: Name of the athlete
            garmin_data: Garmin data for analysis and planning
            analysis_context: Context for data analysis interpretation (health, stress, etc.)
            planning_context: Context for weekly planning (constraints, goals, etc.)
            
        Returns:
            Dict containing both analysis and planning results
        """
        return await MasterOrchestrator.run_full_analysis(user_id, athlete_name, garmin_data, analysis_context, planning_context)