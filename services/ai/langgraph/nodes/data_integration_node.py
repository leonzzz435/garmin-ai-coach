import logging
from datetime import datetime

from ..state.training_analysis_state import TrainingAnalysisState

logger = logging.getLogger(__name__)


async def data_integration_node(state: TrainingAnalysisState) -> TrainingAnalysisState:
    """Data Integration node - extracts analysis results from state for planning context.
    
    In LangGraph, analysis results are already available in state, so this node
    simply formats them for use by the weekly planning agent. This replaces
    the cache loading functionality from the original orchestrator.
    """
    logger.info("Starting data integration node")
    
    try:
        agent_start_time = datetime.now()
        
        metrics_analysis = state.get('metrics_result', '')
        activity_analysis = state.get('activity_result', '')
        physiology_analysis = state.get('physiology_result', '')
        
        data_available = []
        if metrics_analysis:
            data_available.append("metrics analysis")
        if activity_analysis:
            data_available.append("activity analysis")
        if physiology_analysis:
            data_available.append("physiology analysis")
            
        logger.info(f"Data integration: Available analysis data: {', '.join(data_available) if data_available else 'none'}")
        
        execution_time = (datetime.now() - agent_start_time).total_seconds()
        
        cost_data = {
            'agent': 'data_integration',
            'execution_time': execution_time,
            'timestamp': datetime.now().isoformat(),
        }
        
        logger.info(f"Data integration completed in {execution_time:.2f}s")
        
        # No state changes needed - analysis results are already in state
        # This node just validates data availability and tracks execution
        return {
            'costs': [cost_data],
        }
        
    except Exception as e:
        logger.error(f"Data integration node failed: {e}")
        return {
            'errors': [f"Data integration failed: {str(e)}"]
        }