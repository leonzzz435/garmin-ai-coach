
import logging
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from .plot_storage import PlotStorage
from .framework_agnostic_plotting_tool import (
    FrameworkAgnosticPlottingTool,
    FrameworkAgnosticPlotListTool,
    PlottingInput,
)

logger = logging.getLogger(__name__)


class PlottingToolInput(BaseModel):
    python_code: str = Field(
        description="Complete Python code including imports, data creation/processing, and plotting that creates a 'fig' variable"
    )
    description: str = Field(
        description="Brief description of what the plot shows"
    )


def create_plotting_tool(plot_storage: PlotStorage, agent_name: str = "unknown"):
    
    core_tool = FrameworkAgnosticPlottingTool(plot_storage=plot_storage)
    core_tool.agent_name = agent_name
    
    @tool("python_plotting_tool", return_direct=False)
    def python_plotting_tool(python_code: str, description: str) -> str:
        """
        Execute complete Python code to create interactive Plotly visualizations.
        
        ⚠️ IMPORTANT LIMITS: Maximum 2 plots per agent. Use plotting only for insights that provide unique value beyond what's available in the Garmin app.
        
        REQUIRED PARAMETERS:
        - python_code: Complete Python script including imports, data creation/processing, and plotting
        - description: Brief description of what the plot shows
        
        EXAMPLE USAGE:
        python_code: "import plotly.graph_objects as go\n\n# Create training data\ntraining_data = [{'date': '2025-01-01', 'load': 100}, {'date': '2025-01-02', 'load': 120}]\n\n# Create visualization\nfig = go.Figure()\nfig.add_trace(go.Scatter(x=[d['date'] for d in training_data], y=[d['load'] for d in training_data], name='Training Load'))\nfig.update_layout(title='Training Load Over Time')"
        description: "Training load analysis over time"
        
        This tool gives you complete freedom to:
        - Import any data processing libraries (pandas, numpy, etc.)
        - Create and manipulate your own data structures
        - Perform complex data analysis and transformations
        - Create any type of Plotly visualization
        - Design custom layouts, colors, and styling
        
        Your python_code MUST create a variable named 'fig' containing the Plotly figure.
        
        RETURNS:
        - Success: Returns a plot_id that can be referenced in text as [PLOT:plot_id]
        - Error: Returns detailed error message with guidance for fixing issues
        
        If you receive an error message, review the guidance and try again with corrected code.
        """
        try:
            plotting_input = PlottingInput(
                python_code=python_code,
                description=description,
                agent_name=agent_name
            )
            result = core_tool.call(plotting_input)
            return result.message
        except Exception as e:
            logger.error(f"Plotting tool error for agent {agent_name}: {e}")
            return f"Error executing plotting tool: {str(e)}"
    
    return python_plotting_tool


def create_plot_list_tool(plot_storage: PlotStorage):
    
    core_tool = FrameworkAgnosticPlotListTool(plot_storage=plot_storage)
    
    @tool("list_available_plots", return_direct=False)
    def list_available_plots() -> str:
        """
        List all plots available for referencing in your analysis.
        
        Returns information about plots created by other agents that you can reference
        using [PLOT:plot_id] syntax in your text.
        
        Useful for synthesis agents to see what visualizations are available.
        """
        try:
            result = core_tool.call()
            return result.message
        except Exception as e:
            logger.error(f"Plot list tool error: {e}")
            return f"Error listing plots: {str(e)}"
    
    return list_available_plots