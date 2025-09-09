
import logging
from datetime import datetime
from typing import Literal

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import tools_condition

from ..state.training_analysis_state import TrainingAnalysisState, create_initial_state
from ..nodes.metrics_node import metrics_node
from ..nodes.physiology_node import physiology_node
from ..config.langsmith_config import LangSmithConfig

logger = logging.getLogger(__name__)


def create_analysis_workflow():
    LangSmithConfig.setup_langsmith()
    
    workflow = StateGraph(TrainingAnalysisState)
    
    workflow.add_node("metrics", metrics_node)
    workflow.add_node("physiology", physiology_node)
    workflow.add_node("collect_results", collect_results_node)
    
    workflow.add_edge(START, "metrics")
    workflow.add_edge(START, "physiology")
    
    workflow.add_edge("metrics", "collect_results")
    workflow.add_edge("physiology", "collect_results")
    
    workflow.add_edge("collect_results", END)
    
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    
    logger.info("Created LangGraph analysis workflow with parallel execution")
    return app


async def collect_results_node(state: TrainingAnalysisState) -> TrainingAnalysisState:
    logger.info("Collecting analysis results")
    
    if not state.get('metrics_result'):
        logger.warning("Metrics analysis result missing")
    
    if not state.get('physiology_result'):
        logger.warning("Physiology analysis result missing")
    
    total_costs = sum(cost.get('tokens', 0) for cost in state.get('costs', []))
    total_plots = len(state.get('available_plots', []))
    
    logger.info(f"Analysis complete - {total_costs} tokens, {total_plots} plots generated")
    
    return {
        'analysis_complete': True,
        'completion_timestamp': datetime.now().isoformat()
    }


async def run_training_analysis(
    user_id: str,
    athlete_name: str,
    garmin_data: dict,
    analysis_context: str = "",
    competitions: list = None,
    current_date: dict = None
) -> dict:
    
    app = create_analysis_workflow()
    
    execution_id = f"{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    initial_state = create_initial_state(
        user_id=user_id,
        athlete_name=athlete_name,
        garmin_data=garmin_data,
        analysis_context=analysis_context,
        competitions=competitions or [],
        current_date=current_date or {},
        execution_id=execution_id
    )
    
    final_state = None
    async for chunk in app.astream(initial_state, thread_id=execution_id):
        logger.info(f"Workflow step: {chunk}")
        final_state = chunk
    
    return final_state


def create_simple_sequential_workflow():
    workflow = StateGraph(TrainingAnalysisState)
    
    workflow.add_node("metrics", metrics_node)
    workflow.add_node("physiology", physiology_node)
    
    workflow.add_edge(START, "metrics")
    workflow.add_edge("metrics", "physiology") 
    workflow.add_edge("physiology", END)
    
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)