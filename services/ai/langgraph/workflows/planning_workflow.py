import logging
from datetime import datetime

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from ..state.training_analysis_state import TrainingAnalysisState, create_initial_state
from ..nodes.season_planner_node import season_planner_node
from ..nodes.data_integration_node import data_integration_node
from ..nodes.weekly_planner_node import weekly_planner_node
from ..nodes.plan_formatter_node import plan_formatter_node
from ..config.langsmith_config import LangSmithConfig

logger = logging.getLogger(__name__)


def create_planning_workflow():
    LangSmithConfig.setup_langsmith()
    
    workflow = StateGraph(TrainingAnalysisState)
    
    workflow.add_node("season_planner", season_planner_node)
    workflow.add_node("data_integration", data_integration_node)
    workflow.add_node("weekly_planner", weekly_planner_node)
    workflow.add_node("plan_formatter", plan_formatter_node)
    
    workflow.add_edge(START, "season_planner")
    workflow.add_edge("season_planner", "data_integration")
    workflow.add_edge("data_integration", "weekly_planner")
    workflow.add_edge("weekly_planner", "plan_formatter")
    workflow.add_edge("plan_formatter", END)
    
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    
    logger.info("Created complete LangGraph planning workflow with 4 agents")
    return app


async def run_weekly_planning(
    user_id: str,
    athlete_name: str,
    garmin_data: dict,
    planning_context: str = "",
    competitions: list = None,
    current_date: dict = None,
    week_dates: list = None,
    metrics_result: str = "",
    activity_result: str = "",
    physiology_result: str = "",
    plots: list = None,
    available_plots: list = None
) -> dict:
    app = create_planning_workflow()
    
    execution_id = f"{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_planning"
    
    initial_state = create_initial_state(
        user_id=user_id,
        athlete_name=athlete_name,
        garmin_data=garmin_data,
        planning_context=planning_context,
        competitions=competitions or [],
        current_date=current_date or {},
        week_dates=week_dates or [],
        execution_id=execution_id
    )
    
    initial_state.update({
        'metrics_result': metrics_result,
        'activity_result': activity_result,
        'physiology_result': physiology_result,
        'plots': plots or [],
        'available_plots': available_plots or []
    })
    
    final_state = None
    async for chunk in app.astream(initial_state, thread_id=execution_id):
        logger.info(f"Planning workflow step: {chunk}")
        final_state = chunk
    
    return final_state


def create_integrated_analysis_and_planning_workflow():
    LangSmithConfig.setup_langsmith()
    
    workflow = StateGraph(TrainingAnalysisState)
    
    from ..nodes.metrics_node import metrics_node
    from ..nodes.physiology_node import physiology_node
    from ..nodes.activity_data_node import activity_data_node
    from ..nodes.activity_interpreter_node import activity_interpreter_node
    from ..nodes.synthesis_node import synthesis_node
    from ..nodes.formatter_node import formatter_node
    
    workflow.add_node("metrics", metrics_node)
    workflow.add_node("physiology", physiology_node)
    workflow.add_node("activity_data", activity_data_node)
    workflow.add_node("activity_interpreter", activity_interpreter_node)
    workflow.add_node("synthesis", synthesis_node)
    workflow.add_node("formatter", formatter_node)
    
    workflow.add_node("season_planner", season_planner_node)
    workflow.add_node("data_integration", data_integration_node)
    workflow.add_node("weekly_planner", weekly_planner_node)
    workflow.add_node("plan_formatter", plan_formatter_node)
    
    workflow.add_edge(START, "metrics")
    workflow.add_edge(START, "physiology")
    workflow.add_edge(START, "activity_data")
    
    workflow.add_edge("activity_data", "activity_interpreter")
    
    workflow.add_edge(["metrics", "physiology", "activity_interpreter"], "synthesis")
    
    workflow.add_edge("synthesis", "formatter")
    
    workflow.add_edge("formatter", "season_planner")
    
    workflow.add_edge("season_planner", "data_integration")
    workflow.add_edge("data_integration", "weekly_planner")
    workflow.add_edge("weekly_planner", "plan_formatter")
    workflow.add_edge("plan_formatter", END)
    
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    
    logger.info("Created integrated analysis + planning workflow with 10 agents")
    return app


async def run_complete_analysis_and_planning(
    user_id: str,
    athlete_name: str,
    garmin_data: dict,
    analysis_context: str = "",
    planning_context: str = "",
    competitions: list = None,
    current_date: dict = None,
    week_dates: list = None
) -> dict:
    app = create_integrated_analysis_and_planning_workflow()
    
    execution_id = f"{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_complete"
    
    initial_state = create_initial_state(
        user_id=user_id,
        athlete_name=athlete_name,
        garmin_data=garmin_data,
        analysis_context=analysis_context,
        planning_context=planning_context,
        competitions=competitions or [],
        current_date=current_date or {},
        week_dates=week_dates or [],
        execution_id=execution_id
    )
    
    final_state = None
    async for state in app.astream(initial_state, {"configurable": {"thread_id": execution_id}}, stream_mode="values"):
        logger.info(f"Complete workflow step: {list(state.keys())}")
        final_state = state
    
    return final_state