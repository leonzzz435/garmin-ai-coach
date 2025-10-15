import logging
from datetime import datetime

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from ..config.langsmith_config import LangSmithConfig
from ..nodes.activity_data_node import activity_data_node
from ..nodes.activity_interpreter_node import activity_interpreter_node
from ..nodes.formatter_node import formatter_node
from ..nodes.metrics_node import metrics_node
from ..nodes.physiology_node import physiology_node
from ..nodes.plot_resolution_node import plot_resolution_node
from ..nodes.synthesis_node import synthesis_node
from ..state.training_analysis_state import TrainingAnalysisState, create_initial_state

logger = logging.getLogger(__name__)


def create_analysis_workflow():
    LangSmithConfig.setup_langsmith()

    workflow = StateGraph(TrainingAnalysisState)

    workflow.add_node("metrics", metrics_node)
    workflow.add_node("physiology", physiology_node)
    workflow.add_node("activity_data", activity_data_node)
    workflow.add_node("activity_interpreter", activity_interpreter_node)
    workflow.add_node("synthesis", synthesis_node)
    workflow.add_node("formatter", formatter_node)
    workflow.add_node("plot_resolution", plot_resolution_node)

    workflow.add_edge(START, "metrics")
    workflow.add_edge(START, "physiology")
    workflow.add_edge(START, "activity_data")

    workflow.add_edge("activity_data", "activity_interpreter")

    workflow.add_edge("metrics", "synthesis")
    workflow.add_edge("physiology", "synthesis")
    workflow.add_edge("activity_interpreter", "synthesis")
    workflow.add_edge("synthesis", "formatter")
    workflow.add_edge("formatter", "plot_resolution")
    workflow.add_edge("plot_resolution", END)

    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)

    logger.info("Created complete LangGraph analysis workflow with 6 agents + plot resolution")
    return app


async def run_training_analysis(
    user_id: str,
    athlete_name: str,
    garmin_data: dict,
    analysis_context: str = "",
    competitions: list = None,
    current_date: dict = None,
    plotting_enabled: bool = False,
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
        execution_id=execution_id,
        plotting_enabled=plotting_enabled,
    )

    final_state = None
    config = {"configurable": {"thread_id": execution_id}}
    async for chunk in app.astream(initial_state, config=config, stream_mode="values"):
        logger.info(f"Workflow step: {list(chunk.keys()) if chunk else 'None'}")
        final_state = chunk

    return final_state


def create_simple_sequential_workflow():
    workflow = StateGraph(TrainingAnalysisState)

    workflow.add_node("metrics", metrics_node)
    workflow.add_node("physiology", physiology_node)
    workflow.add_node("activity_data", activity_data_node)
    workflow.add_node("activity_interpreter", activity_interpreter_node)
    workflow.add_node("synthesis", synthesis_node)
    workflow.add_node("formatter", formatter_node)
    workflow.add_node("plot_resolution", plot_resolution_node)

    workflow.add_edge(START, "metrics")
    workflow.add_edge("metrics", "physiology")
    workflow.add_edge("physiology", "activity_data")
    workflow.add_edge("activity_data", "activity_interpreter")
    workflow.add_edge("activity_interpreter", "synthesis")
    workflow.add_edge("synthesis", "formatter")
    workflow.add_edge("formatter", "plot_resolution")
    workflow.add_edge("plot_resolution", END)

    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)
