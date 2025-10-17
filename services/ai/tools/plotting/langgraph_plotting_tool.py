import logging

from langchain_core.tools import tool

from .plot_storage import PlotStorage
from .production_secure_executor import run_plot_code_get_html

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
        def python_plotting_tool(python_code: str, description: str) -> dict:
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
            - Success: {"ok": True, "plot_id": "...", "message": "..."}
            - Error: {"ok": False, "error": "...", "hint": "..."}

            If you receive an error, review the hint and try again with corrected code.
            """
            try:
                agent_plot_count = self._count_agent_plots(self.agent_name)
                if agent_plot_count >= 2:
                    return {
                        "ok": False,
                        "error": f"Plot limit reached for agent '{self.agent_name}' ({agent_plot_count}/2 plots created)",
                        "hint": "Consider: 1) Referencing existing plots using [PLOT:plot_id], 2) Incorporating insights into text, or 3) Combining insights into one comprehensive visualization."
                    }

                if not python_code or not python_code.strip():
                    return {
                        "ok": False,
                        "error": "Missing required parameter 'python_code'",
                        "hint": "Provide complete Python code with imports and a 'fig' variable. Example: import plotly.graph_objects as go; fig = go.Figure(); fig.add_trace(...)"
                    }

                if not description or not description.strip():
                    return {
                        "ok": False,
                        "error": "Missing required parameter 'description'",
                        "hint": "Provide a brief description of what the plot shows (e.g., 'Training load analysis over time showing weekly progression')"
                    }

                logger.info(f"Agent {self.agent_name} executing plotting code")
                result = run_plot_code_get_html(python_code)

                if not result["ok"]:
                    logger.error(f"Agent {self.agent_name} plotting failed: {result['error']}")
                    return {
                        "ok": False,
                        "error": result['error'],
                        "hint": "Check: 1) Syntax errors, 2) Import statements (import plotly.graph_objects as go), 3) 'fig' variable creation, 4) Date handling with datetime, 5) Data references"
                    }

                html_content = result["html"]

                if not html_content:
                    logger.error(f"Agent {self.agent_name} plot HTML conversion failed - no HTML content")
                    return {
                        "ok": False,
                        "error": "Failed to convert plot to HTML",
                        "hint": "Ensure your code creates a 'fig' variable with a valid Plotly figure (use plotly.graph_objects or plotly.express)"
                    }

                plot_id = self.plot_storage.store_plot(
                    html_content=html_content,
                    description=description,
                    agent_name=self.agent_name,
                    data_summary="Custom plotting code",
                )

                logger.info(f"Agent {self.agent_name} created plot {plot_id}")
                return {
                    "ok": True,
                    "plot_id": plot_id,
                    "message": f"Plot created successfully! Reference as [PLOT:{plot_id}]"
                }

            except Exception as e:
                import traceback
                full_traceback = traceback.format_exc()
                logger.error(f"Agent {self.agent_name} plotting failed: {e}\n\nFull traceback:\n{full_traceback}")
                return {
                    "ok": False,
                    "error": str(e),
                    "hint": "Runtime exception occurred. Check your code for errors and try again."
                }

        return python_plotting_tool

def create_plotting_tools(plot_storage: PlotStorage, agent_name: str = "unknown"):
    langgraph_tool = LangGraphPlottingTool(plot_storage, agent_name)
    return langgraph_tool.create_plotting_tool()
