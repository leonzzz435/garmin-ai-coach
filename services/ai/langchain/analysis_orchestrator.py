"""LangChain orchestrator for comprehensive training analysis."""

import logging
from typing import Dict, Any
from datetime import datetime
from dataclasses import asdict
from pathlib import Path

from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from core.security.competitions import SecureCompetitionManager
from .analysis_chains import AnalysisChains
from services.garmin import GarminData
from services.ai.utils.intermediate_storage import IntermediateResultStorage

logger = logging.getLogger(__name__)

class LangChainAnalysisOrchestrator:
    """Orchestrates analysis using LangChain chains - no shared storage."""
    
    def __init__(self, garmin_data: GarminData, user_id: str, athlete_name: str, analysis_context: str = ""):
        """Initialize orchestrator for a single analysis execution.
        
        Args:
            garmin_data: Garmin data for analysis
            user_id: User identifier
            athlete_name: Name of the athlete
            analysis_context: Context for data analysis interpretation (health, stress, etc.)
        """
        self.user_id = user_id
        self.athlete_name = athlete_name
        self.analysis_context = analysis_context
        self.data = asdict(garmin_data)
        
        # Create execution-scoped chains
        self.chains = AnalysisChains(user_id)
        
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
        
        # Load style guide
        try:
            with open('styleGuide.md', 'r') as f:
                self.style_guide = f.read()
        except Exception as e:
            logger.error(f"Failed to load style guide: {e}")
            self.style_guide = ""
        
        logger.info(f"Initialized LangChain orchestrator for user {user_id}")
    
    async def run_analysis(self, store_intermediate: bool = True) -> tuple[str, dict[str, str]]:
        """Execute the complete analysis flow and return HTML result with intermediate results.
        
        Args:
            store_intermediate: Whether to store intermediate results to files (default: True)
        
        Returns:
            Tuple of (HTML formatted analysis report, dict of intermediate results)
        """
        try:
            # Step 1: Metrics Analysis
            logger.info("Starting metrics analysis")
            metrics_chain = self.chains.create_metrics_chain()
            metrics_result = await metrics_chain.ainvoke({
                'data': {
                    'training_load_history': self.data.get('training_load_history', []),
                    'vo2_max_history': self.data.get('vo2_max_history', []),
                    'training_status': self.data.get('training_status', {}),
                },
                'competitions': self.competitions,
                'current_date': self.current_date,
                'analysis_context': self.analysis_context
            })
            logger.info("Metrics analysis completed")
            
            # Step 2: Activity Data Extraction  
            logger.info("Starting activity data extraction")
            activity_data_chain = self.chains.create_activity_data_chain()
            activity_summary = await activity_data_chain.ainvoke({
                'data': {
                    'recent_activities': self.data.get('recent_activities', []),
                    'training_status': self.data.get('training_status', {})
                }
            })
            logger.info("Activity data extraction completed")
            
            # Step 3: Activity Interpretation
            logger.info("Starting activity interpretation")
            activity_interpreter_chain = self.chains.create_activity_interpreter_chain()
            activity_result = await activity_interpreter_chain.ainvoke({
                'activity_summary': activity_summary,
                'competitions': self.competitions,
                'current_date': self.current_date,
                'analysis_context': self.analysis_context
            })
            logger.info("Activity interpretation completed")
            
            # Step 4: Physiology Analysis
            logger.info("Starting physiology analysis")
            physiology_chain = self.chains.create_physiology_chain()
            physiology_result = await physiology_chain.ainvoke({
                'data': {
                    'recovery_indicators': self.data.get('recovery_indicators', []),
                    'daily_stats': self.data.get('daily_stats', {}),
                    'physiological_markers': self.data.get('physiological_markers', {})
                },
                'competitions': self.competitions,
                'current_date': self.current_date,
                'analysis_context': self.analysis_context
            })
            logger.info("Physiology analysis completed")
            
            # Step 5: Synthesis
            logger.info("Starting synthesis")
            synthesis_chain = self.chains.create_synthesis_chain()
            synthesis_result = await synthesis_chain.ainvoke({
                'athlete_name': self.athlete_name,
                'metrics_result': metrics_result,
                'activity_result': activity_result,
                'physiology_result': physiology_result,
                'competitions': self.competitions,
                'current_date': self.current_date,
                'style_guide': self.style_guide
            })
            logger.info("Synthesis completed")
            
            # Step 6: HTML Formatting
            logger.info("Starting HTML formatting")
            formatter_chain = self.chains.create_formatter_chain()
            html_result = await formatter_chain.ainvoke({
                'synthesis_result': synthesis_result
            })
            logger.info("HTML formatting completed")
            
            # Package intermediate results
            intermediate_results = {
                'metrics_result': metrics_result,
                'activity_result': activity_result,
                'physiology_result': physiology_result,
                'synthesis_result': synthesis_result
            }
            
            # Store intermediate results if requested
            if store_intermediate:
                try:
                    storage = IntermediateResultStorage(self.athlete_name)
                    stored_files = storage.store_analysis_results(intermediate_results)
                    logger.info(f"Stored {len(stored_files)} intermediate result files for {self.athlete_name}")
                except Exception as e:
                    logger.warning(f"Failed to store intermediate results for {self.athlete_name}: {e}")
            
            logger.info(f"Analysis orchestration completed successfully for user {self.user_id}")
            return html_result, intermediate_results
            
        except Exception as e:
            logger.error(f"Analysis orchestration failed for user {self.user_id}: {str(e)}")
            raise


class LangChainAnalysisFlow:
    """LangChain-based analysis flow for comprehensive training insights."""
    
    @staticmethod
    async def run_analysis(garmin_data: GarminData, user_id: str, athlete_name: str, analysis_context: str = "") -> tuple[str, dict[str, str]]:
        """Run complete analysis and return HTML result with intermediate results.
        
        Args:
            garmin_data: Garmin data for analysis
            user_id: User identifier
            athlete_name: Name of the athlete
            analysis_context: Context for data analysis interpretation (health, stress, etc.)
            
        Returns:
            Tuple of (HTML formatted analysis report, dict of intermediate results)
        """
        orchestrator = LangChainAnalysisOrchestrator(garmin_data, user_id, athlete_name, analysis_context)
        return await orchestrator.run_analysis()