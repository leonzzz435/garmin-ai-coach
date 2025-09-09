import json
import logging
from typing import TypedDict, Optional
from langchain_core.tools import tool
from langchain_core.messages import AIMessage, ToolMessage

from .production_secure_executor import run_plot_code_get_html
from .plot_storage import PlotStorage

logger = logging.getLogger(__name__)

class LangGraphPlottingTool:
    
    def __init__(self, plot_storage: PlotStorage, agent_name: str = "unknown"):
        self.plot_storage = plot_storage
        self.agent_name = agent_name
        logger.info(f"Initialized LangGraph plotting tool for agent: {agent_name}")
    
    def _count_agent_plots(self, agent_name: str) -> int:
        plots = self.plot_storage.list_available_plots()
        return len([plot for plot in plots if plot.get('agent_name') == agent_name])
    
    def create_plotting_tool(self):
        
        @tool("python_plotting_tool", return_direct=False)
        def python_plotting_tool(python_code: str, description: str) -> str:
            """
            Execute complete Python code to create interactive Plotly visualizations.
            
            ⚠️ IMPORTANT LIMITS: Maximum 2 plots per agent. Use plotting only for insights 
            that provide unique value beyond what's available in the Garmin app.
            
            REQUIRED PARAMETERS:
            - python_code: Complete Python script that creates a 'fig' variable
            - description: Brief description of what the plot shows
            
            Your python_code MUST create a variable named 'fig' containing the Plotly figure.
            
            Available imports: plotly.graph_objects, plotly.express, plotly.io, pandas, 
            numpy, datetime, math, statistics, json, collections, re
            
            RETURNS:
            - Success: Returns a plot_id that can be referenced in text as [PLOT:plot_id]
            - Error: Returns detailed error message with guidance for fixing issues
            
            If you receive an error message, review the guidance and try again with corrected code.
            """
            try:
                agent_plot_count = self._count_agent_plots(self.agent_name)
                if agent_plot_count >= 2:
                    return f"""Plot limit reached: Agent '{self.agent_name}' has already created {agent_plot_count} plots (maximum: 2).

⚠️ IMPORTANT: Create plots only for insights that provide unique value beyond what's available in the Garmin app.

Consider whether this visualization is truly necessary or if you can:
1. Reference existing plots using [PLOT:plot_id] syntax
2. Incorporate insights into your text analysis instead
3. Combine multiple insights into a single, comprehensive visualization."""

                if not python_code or not python_code.strip():
                    return """Error: Missing required parameter 'python_code'.

Please provide complete Python code including imports, data handling, and plotting that creates a 'fig' variable.

Example format:
```python
import plotly.graph_objects as go
import pandas as pd

training_data = [{'date': '2025-01-01', 'load': 100}, {'date': '2025-01-02', 'load': 120}]

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=[d['date'] for d in training_data],
    y=[d['load'] for d in training_data],
    name='Training Load'
))
fig.update_layout(title='Training Load Over Time')
```

Please try again with complete Python code."""

                if not description or not description.strip():
                    return """Error: Missing required parameter 'description'.

Please provide a brief description of what the plot shows.

Example: 'Training load analysis over time showing weekly progression'

Please try again with both python_code and description parameters."""

                logger.info(f"Agent {self.agent_name} executing plotting code")
                result = run_plot_code_get_html(python_code)

                if not result["ok"]:
                    logger.error(f"Agent {self.agent_name} plotting failed: {result['error']}")
                    return f"""Error executing plotting code: {result['error']}

Please fix the following issues and try again:
1. Check for syntax errors in your Python code
2. Ensure all required libraries are imported (import plotly.graph_objects as go, import pandas as pd, etc.)
3. Verify that your code creates a 'fig' variable with a valid Plotly figure
4. Make sure date handling uses proper datetime operations
5. Check that all data references are correctly defined

Your code must create a variable named 'fig' containing the Plotly figure object.

Please review your code and try again with the corrections."""

                html_content = result["html"]
                
                if not html_content:
                    logger.error(f"Agent {self.agent_name} plot HTML conversion failed - no HTML content generated")
                    return """Error: Failed to convert plot to HTML.

This usually means the 'fig' variable was not created properly. Please ensure:
1. Your code creates a variable named 'fig'
2. The 'fig' variable contains a valid Plotly figure object
3. Use plotly.graph_objects or plotly.express to create the figure

Example:
```python
import plotly.graph_objects as go
fig = go.Figure()
# ... add traces and layout ...
```

Please try again with a properly created 'fig' variable."""

                plot_id = self.plot_storage.store_plot(
                    html_content=html_content,
                    description=description,
                    agent_name=self.agent_name,
                    data_summary="Custom plotting code",
                )

                success_msg = f"Plot created successfully! Reference as [PLOT:{plot_id}]"
                logger.info(f"Agent {self.agent_name} created plot {plot_id}")
                
                return success_msg

            except Exception as e:
                import traceback
                full_traceback = traceback.format_exc()
                error_msg = f"Plotting tool error: {str(e)}. Please check your input and try again."
                logger.error(f"Agent {self.agent_name} plotting failed: {e}\n\nFull traceback:\n{full_traceback}")
                return error_msg
        
        return python_plotting_tool

    def create_plot_list_tool(self):
        
        @tool("list_available_plots", return_direct=False)
        def list_available_plots() -> str:
            """
            List all plots available for referencing in your analysis.
            
            Returns information about plots created by other agents that you can reference
            using [PLOT:plot_id] syntax in your text.
            
            Useful for synthesis agents to see what visualizations are available.
            """
            try:
                plots = self.plot_storage.list_available_plots()

                if not plots:
                    return "No plots available yet."
                else:
                    plot_list = ["Available plots for referencing:"]
                    for plot in plots:
                        plot_list.append(
                            f"- [PLOT:{plot['plot_id']}]: {plot['description']} "
                            f"(by {plot['agent_name']}, data: {plot['data_summary']})"
                        )
                    return "\n".join(plot_list)

            except Exception as e:
                logger.error(f"Plot list tool error: {e}")
                return f"Error listing plots: {str(e)}"
        
        return list_available_plots


def create_plotting_tools(plot_storage: PlotStorage, agent_name: str = "unknown"):
    langgraph_tool = LangGraphPlottingTool(plot_storage, agent_name)
    return langgraph_tool.create_plotting_tool(), langgraph_tool.create_plot_list_tool()