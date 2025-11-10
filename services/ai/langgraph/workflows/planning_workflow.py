import logging
from datetime import datetime

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from ..config.langsmith_config import LangSmithConfig
from ..nodes.activity_expert_node import activity_expert_node
from ..nodes.activity_summarizer_node import activity_summarizer_node
from ..nodes.data_integration_node import data_integration_node
from ..nodes.formatter_node import formatter_node
from ..nodes.metrics_expert_node import metrics_expert_node
from ..nodes.metrics_summarizer_node import metrics_summarizer_node
from ..nodes.physiology_expert_node import physiology_expert_node
from ..nodes.physiology_summarizer_node import physiology_summarizer_node
from ..nodes.plan_formatter_node import plan_formatter_node
from ..nodes.plot_resolution_node import plot_resolution_node
from ..nodes.season_planner_node import season_planner_node
from ..nodes.synthesis_node import synthesis_node
from ..nodes.weekly_planner_node import weekly_planner_node
from ..state.training_analysis_state import TrainingAnalysisState, create_initial_state
from ..utils.workflow_cost_tracker import ProgressIntegratedCostTracker

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
    competitions: list | None = None,
    current_date: dict | None = None,
    week_dates: list | None = None,
    metrics_result: str = "",
    activity_result: str = "",
    physiology_result: str = "",
    plots: list | None = None,
    available_plots: list | None = None,
) -> dict:
    execution_id = f"{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_planning"
    config = {"configurable": {"thread_id": execution_id}}
    
    initial_state = create_initial_state(
        user_id=user_id,
        athlete_name=athlete_name,
        garmin_data=garmin_data,
        planning_context=planning_context,
        competitions=competitions,
        current_date=current_date,
        week_dates=week_dates,
        execution_id=execution_id,
    )
    initial_state.update({
        "metrics_result": metrics_result,
        "activity_result": activity_result,
        "physiology_result": physiology_result,
        "plots": plots or [],
        "available_plots": available_plots or [],
    })

    async for chunk in create_planning_workflow().astream(initial_state, config=config, stream_mode="values"):
        logger.info(f"Planning workflow step: {list(chunk.keys()) if chunk else 'None'}")
        final_state = chunk

    return final_state


def create_integrated_analysis_and_planning_workflow():
    LangSmithConfig.setup_langsmith()

    checkpointer = MemorySaver()

    workflow = StateGraph(TrainingAnalysisState)

    workflow.add_node("metrics_summarizer", metrics_summarizer_node)
    workflow.add_node("physiology_summarizer", physiology_summarizer_node)
    workflow.add_node("activity_summarizer", activity_summarizer_node)

    workflow.add_node("metrics_expert", metrics_expert_node)
    workflow.add_node("physiology_expert", physiology_expert_node)
    workflow.add_node("activity_expert", activity_expert_node)
    
    workflow.add_node("synthesis", synthesis_node)
    workflow.add_node("formatter", formatter_node)
    workflow.add_node("plot_resolution", plot_resolution_node)

    workflow.add_node("season_planner", season_planner_node)
    workflow.add_node("data_integration", data_integration_node)
    workflow.add_node("weekly_planner", weekly_planner_node)
    workflow.add_node("plan_formatter", plan_formatter_node)
    
    workflow.add_node("finalize", lambda state: state, defer=True)

    workflow.add_edge(START, "metrics_summarizer")
    workflow.add_edge(START, "physiology_summarizer")
    workflow.add_edge(START, "activity_summarizer")

    workflow.add_edge("metrics_summarizer", "metrics_expert")
    workflow.add_edge("physiology_summarizer", "physiology_expert")
    workflow.add_edge("activity_summarizer", "activity_expert")

    workflow.add_edge(["metrics_expert", "physiology_expert", "activity_expert"], "synthesis")
    workflow.add_edge("synthesis", "formatter")
    workflow.add_edge("formatter", "plot_resolution")

    workflow.add_edge(["metrics_expert", "physiology_expert", "activity_expert"], "season_planner")
    workflow.add_edge("season_planner", "data_integration")
    workflow.add_edge("data_integration", "weekly_planner")
    workflow.add_edge("weekly_planner", "plan_formatter")
    
    workflow.add_edge("plot_resolution", "finalize")
    workflow.add_edge("plan_formatter", "finalize")
    workflow.add_edge("finalize", END)

    app = workflow.compile(checkpointer=checkpointer)
    logger.info(
        "Created integrated analysis + planning workflow with parallel architecture: "
        "3 summarizers → 3 experts → [analysis branch (synthesis/formatter/plots) || planning branch (season/data_integration/weekly/plan_formatter)] → finalize"
    )
    
    return app, checkpointer


async def run_complete_analysis_and_planning(
    user_id: str,
    athlete_name: str,
    garmin_data: dict,
    analysis_context: str = "",
    planning_context: str = "",
    competitions: list | None = None,
    current_date: dict | None = None,
    week_dates: list | None = None,
    progress_manager=None,
    plotting_enabled: bool = False,
    hitl_enabled: bool = True,
) -> dict:
    execution_id = f"{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_complete"
    cost_tracker = ProgressIntegratedCostTracker(f"garmin_ai_coach_{user_id}", progress_manager)

    app, checkpointer = create_integrated_analysis_and_planning_workflow()

    final_state, execution = await cost_tracker.run_workflow_with_progress(
        app,
        create_initial_state(
            user_id=user_id,
            athlete_name=athlete_name,
            garmin_data=garmin_data,
            analysis_context=analysis_context,
            planning_context=planning_context,
            competitions=competitions,
            current_date=current_date,
            week_dates=week_dates,
            execution_id=execution_id,
            plotting_enabled=plotting_enabled,
        ),
        execution_id,
        user_id,
    )

    if execution.cost_summary:
        final_state["cost_summary"] = cost_tracker.get_legacy_cost_summary(execution)
        final_state["execution_metadata"] = {
            "trace_id": execution.trace_id,
            "root_run_id": execution.root_run_id,
            "execution_time_seconds": execution.execution_time_seconds,
            "total_cost_usd": execution.cost_summary.total_cost_usd,
            "total_tokens": execution.cost_summary.total_tokens,
        }
        logger.info(
            f"Workflow complete for user {user_id}: "
            f"${execution.cost_summary.total_cost_usd:.4f} "
            f"({execution.cost_summary.total_tokens} tokens)"
        )
    else:
        logger.warning(f"No cost data available for user {user_id} workflow")
        final_state["cost_summary"] = {"total_cost_usd": 0.0, "total_tokens": 0}
        final_state["execution_metadata"] = {}

    return final_state
