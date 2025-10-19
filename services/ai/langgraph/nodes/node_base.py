import logging
from datetime import datetime
from typing import Any, Callable, Optional

from services.ai.tools.hitl import create_ask_human_tool
from services.ai.tools.plotting import PlotStorage, create_plotting_tools

logger = logging.getLogger(__name__)

try:
    from langgraph.errors import GraphInterrupt
except ImportError:
    try:
        from langgraph.errors import NodeInterrupt as GraphInterrupt
    except ImportError:
        class GraphInterrupt(BaseException):  # type: ignore
            """Placeholder exception for when LangGraph is not installed"""
            pass


def configure_node_tools(
    agent_name: str,
    plot_storage: Optional[PlotStorage] = None,
    plotting_enabled: bool = False,
    hitl_enabled: bool = True,
) -> list:
    
    tools = []
    
    if plotting_enabled and plot_storage:
        plotting_tool = create_plotting_tools(plot_storage, agent_name=agent_name)
        tools.append(plotting_tool)
        logger.debug(f"{agent_name}: Added plotting tool")
    
    if hitl_enabled:
        display_name = agent_name.replace("_", " ").title()
        ask_human_tool = create_ask_human_tool(display_name)
        tools.append(ask_human_tool)
        logger.debug(f"{agent_name}: Added HITL tool")
    
    return tools


def create_cost_entry(agent_name: str, execution_time: float) -> dict[str, Any]:

    return {
        "agent": agent_name,
        "execution_time": execution_time,
        "timestamp": datetime.now().isoformat(),
    }


def create_plot_entries(agent_name: str, plot_storage: PlotStorage) -> tuple[list, dict, list]:
    
    all_plots = plot_storage.get_all_plots()
    timestamp_iso = datetime.now().isoformat()
    
    plots = [
        {
            "agent": agent_name,
            "plot_id": plot_id,
            "timestamp": timestamp_iso,
        }
        for plot_id in all_plots
    ]
    
    plot_storage_data = {
        plot_id: {
            "plot_id": metadata.plot_id,
            "description": metadata.description,
            "agent_name": metadata.agent_name,
            "created_at": metadata.created_at.isoformat(),
            "html_content": metadata.html_content,
            "data_summary": metadata.data_summary,
        }
        for plot_id, metadata in all_plots.items()
    }
    
    available_plots = list(all_plots.keys())
    
    return plots, plot_storage_data, available_plots


async def execute_node_with_error_handling(
    node_name: str,
    node_function: Callable,
    error_message_prefix: str,
) -> dict[str, Any]:

    try:
        return await node_function()
    
    except GraphInterrupt:
        logger.info(f"{node_name}: GraphInterrupt raised - propagating to LangGraph")
        raise
    
    except Exception as e:
        logger.error(f"{node_name} failed: {e}", exc_info=True)
        return {"errors": [f"{error_message_prefix}: {str(e)}"]}


def log_node_completion(node_name: str, execution_time: float, plot_count: int = 0) -> None:
    
    if plot_count > 0:
        logger.info(
            f"{node_name} completed in {execution_time:.2f}s with {plot_count} plots"
        )
    else:
        logger.info(f"{node_name} completed in {execution_time:.2f}s")