import logging
from datetime import datetime

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from ..config.langsmith_config import LangSmithConfig
from ..nodes.activity_data_node import activity_data_node
from ..nodes.activity_interpreter_node import activity_interpreter_node
from ..nodes.formatter_node import formatter_node
from ..nodes.metrics_expert_node import metrics_expert_node
from ..nodes.metrics_summarizer_node import metrics_summarizer_node
from ..nodes.physiology_expert_node import physiology_expert_node
from ..nodes.physiology_summarizer_node import physiology_summarizer_node
from ..nodes.plot_resolution_node import plot_resolution_node
from ..nodes.synthesis_node import synthesis_node
from ..state.training_analysis_state import TrainingAnalysisState, create_initial_state

logger = logging.getLogger(__name__)


def create_analysis_workflow(debug_mode: bool = False):
    LangSmithConfig.setup_langsmith()

    workflow = StateGraph(TrainingAnalysisState)

    workflow.add_node("metrics_summarizer", metrics_summarizer_node)
    workflow.add_node("physiology_summarizer", physiology_summarizer_node)
    workflow.add_node("activity_data", activity_data_node)
    
    workflow.add_node("metrics_expert", metrics_expert_node)
    workflow.add_node("physiology_expert", physiology_expert_node)
    workflow.add_node("activity_interpreter", activity_interpreter_node)
    
    workflow.add_node("synthesis", synthesis_node)
    workflow.add_node("formatter", formatter_node)
    workflow.add_node("plot_resolution", plot_resolution_node)

    workflow.add_edge(START, "metrics_summarizer")
    workflow.add_edge(START, "physiology_summarizer")
    workflow.add_edge(START, "activity_data")

    workflow.add_edge("metrics_summarizer", "metrics_expert")
    workflow.add_edge("physiology_summarizer", "physiology_expert")
    workflow.add_edge("activity_data", "activity_interpreter")

    workflow.add_edge("metrics_expert", "synthesis")
    workflow.add_edge("physiology_expert", "synthesis")
    workflow.add_edge("activity_interpreter", "synthesis")
    workflow.add_edge("synthesis", "formatter")
    workflow.add_edge("formatter", "plot_resolution")
    workflow.add_edge("plot_resolution", END)

    checkpointer = MemorySaver()
    
    if debug_mode:
        app = workflow.compile(
            checkpointer=checkpointer,
            interrupt_before=["metrics_expert", "physiology_expert", "activity_interpreter"]
        )
        logger.info("Created LangGraph analysis workflow with BREAKPOINT after summarization nodes")
    else:
        app = workflow.compile(checkpointer=checkpointer)
        logger.info("Created complete LangGraph analysis workflow with 2-stage architecture (3 summarizers + 3 experts + synthesis + formatting)")
    
    return app


async def run_training_analysis(
    user_id: str,
    athlete_name: str,
    garmin_data: dict,
    analysis_context: str = "",
    competitions: list | None = None,
    current_date: dict | None = None,
    plotting_enabled: bool = False,
    debug_mode: bool = False,
) -> dict:
    execution_id = f"{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    config = {"configurable": {"thread_id": execution_id}}
    
    async for chunk in create_analysis_workflow(debug_mode=debug_mode).astream(
        create_initial_state(
            user_id=user_id,
            athlete_name=athlete_name,
            garmin_data=garmin_data,
            analysis_context=analysis_context,
            competitions=competitions,
            current_date=current_date,
            execution_id=execution_id,
            plotting_enabled=plotting_enabled,
        ),
        config=config,
        stream_mode="values",
    ):
        logger.info(f"Workflow step: {list(chunk.keys()) if chunk else 'None'}")
        final_state = chunk

    return final_state


def create_simple_sequential_workflow():
    workflow = StateGraph(TrainingAnalysisState)

    workflow.add_node("metrics_summarizer", metrics_summarizer_node)
    workflow.add_node("physiology_summarizer", physiology_summarizer_node)
    workflow.add_node("activity_data", activity_data_node)
    
    workflow.add_node("metrics_expert", metrics_expert_node)
    workflow.add_node("physiology_expert", physiology_expert_node)
    workflow.add_node("activity_interpreter", activity_interpreter_node)
    
    workflow.add_node("synthesis", synthesis_node)
    workflow.add_node("formatter", formatter_node)
    workflow.add_node("plot_resolution", plot_resolution_node)

    workflow.add_edge(START, "metrics_summarizer")
    workflow.add_edge("metrics_summarizer", "metrics_expert")
    workflow.add_edge("metrics_expert", "physiology_summarizer")
    workflow.add_edge("physiology_summarizer", "physiology_expert")
    workflow.add_edge("physiology_expert", "activity_data")
    workflow.add_edge("activity_data", "activity_interpreter")
    workflow.add_edge("activity_interpreter", "synthesis")
    workflow.add_edge("synthesis", "formatter")
    workflow.add_edge("formatter", "plot_resolution")
    workflow.add_edge("plot_resolution", END)

    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)
