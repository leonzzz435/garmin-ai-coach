
import logging
import asyncio
from typing import TYPE_CHECKING, Any, Optional, Protocol, runtime_checkable
from pydantic import BaseModel, Field, ValidationError

if TYPE_CHECKING:
    from .secure_executor import SecurePythonExecutor

from .plot_storage import PlotStorage
from .secure_executor import SecurePythonExecutor

logger = logging.getLogger(__name__)


class PlottingInput(BaseModel):
    python_code: Optional[str] = Field(
        default=None,
        description="Complete Python code including imports, data creation/processing, and plotting that creates a 'fig' variable",
    )
    description: Optional[str] = Field(
        default=None, 
        description="Brief description of what the plot shows"
    )
    agent_name: str = Field(
        default="unknown", 
        description="Name of the agent creating the plot"
    )


class PlotResult(BaseModel):
    success: bool = Field(..., description="Whether the plotting operation succeeded")
    plot_id: Optional[str] = Field(None, description="ID of the created plot if successful")
    message: str = Field(..., description="Success message or error details")
    error_type: Optional[str] = Field(None, description="Type of error if failed")


@runtime_checkable
class Tool(Protocol):
    name: str
    description: str
    input_model: type[BaseModel]
    
    def call(self, args: BaseModel) -> BaseModel: ...
    async def acall(self, args: BaseModel) -> BaseModel: ...


class FrameworkAgnosticPlottingTool:
    
    name: str = "python_plotting_tool"
    description: str = """
    Execute complete Python code to create interactive Plotly visualizations.
    
    ⚠️ IMPORTANT LIMITS: Maximum 2 plots per agent. Use plotting only for insights that provide unique value beyond what's available in the Garmin app.
    
    REQUIRED PARAMETERS:
    - python_code: Complete Python script including imports, data creation/processing, and plotting
    - description: Brief description of what the plot shows
    
    EXAMPLE USAGE:
    {
        "python_code": "import plotly.graph_objects as go\\n\\n# Create training data\\ntraining_data = [{'date': '2025-01-01', 'load': 100}, {'date': '2025-01-02', 'load': 120}]\\n\\n# Create visualization\\nfig = go.Figure()\\nfig.add_trace(go.Scatter(x=[d['date'] for d in training_data], y=[d['load'] for d in training_data], name='Training Load'))\\nfig.update_layout(title='Training Load Over Time')",
        "description": "Training load analysis over time"
    }
    
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
    
    input_model: type[BaseModel] = PlottingInput
    
    def __init__(
        self, 
        plot_storage: PlotStorage, 
        progress_manager: Any = None,
        executor: Optional['SecurePythonExecutor'] = None
    ):
        self.plot_storage = plot_storage
        self.progress_manager = progress_manager
        self.executor = executor or SecurePythonExecutor()
        self.agent_name = "unknown"  # Can be set by nodes or external callers
        
    def _count_agent_plots(self, agent_name: str) -> int:
        plots = self.plot_storage.list_available_plots()
        return len([plot for plot in plots if plot.get('agent_name') == agent_name])
    
    def call(self, args: BaseModel) -> PlotResult:
        try:
            if isinstance(args, dict):
                plot_input = PlottingInput.model_validate(args)
            elif isinstance(args, PlottingInput):
                plot_input = args
            else:
                plot_input = PlottingInput.model_validate(args.model_dump())
                
        except ValidationError as e:
            return PlotResult(
                success=False,
                message=f"Invalid input: {e}",
                error_type="validation_error"
            )
        
        try:
            actual_agent_name = getattr(self, 'agent_name', plot_input.agent_name) or plot_input.agent_name

            agent_plot_count = self._count_agent_plots(actual_agent_name)
            if agent_plot_count >= 2:
                return PlotResult(
                    success=False,
                    message=f"""Plot limit reached: Agent '{actual_agent_name}' has already created {agent_plot_count} plots (maximum: 2).

⚠️ IMPORTANT: Create plots only for insights that provide unique value beyond what's available in the Garmin app.

Consider whether this visualization is truly necessary or if you can:
1. Reference existing plots using [PLOT:plot_id] syntax
2. Incorporate insights into your text analysis instead
3. Combine multiple insights into a single, comprehensive visualization.""",
                    error_type="plot_limit_exceeded"
                )

            if not plot_input.python_code or not plot_input.python_code.strip():
                return PlotResult(
                    success=False,
                    message="""Error: Missing required parameter 'python_code'.

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

Please try again with complete Python code.""",
                    error_type="missing_python_code"
                )

            if not plot_input.description or not plot_input.description.strip():
                return PlotResult(
                    success=False,
                    message="""Error: Missing required parameter 'description'.

Please provide a brief description of what the plot shows.

Example: 'Training load analysis over time showing weekly progression'

Please try again with both python_code and description parameters.""",
                    error_type="missing_description"
                )

            logger.info(f"Agent {actual_agent_name} executing plotting code")

            success, result, error = self.executor.execute_plotting_code(plot_input.python_code)

            if not success:
                logger.error(f"Agent {actual_agent_name} plotting failed: {error}")
                return PlotResult(
                    success=False,
                    message=f"""Error executing plotting code: {error}

Please fix the following issues and try again:
1. Check for syntax errors in your Python code
2. Ensure all required libraries are imported (import plotly.graph_objects as go, import pandas as pd, etc.)
3. Verify that your code creates a 'fig' variable with a valid Plotly figure
4. Make sure date handling uses proper datetime operations
5. Check that all data references are correctly defined

Your code must create a variable named 'fig' containing the Plotly figure object.

Please review your code and try again with the corrections.""",
                    error_type="execution_error"
                )

            html_content = self.executor.plot_to_html(result)

            if not html_content:
                logger.error(
                    f"Agent {actual_agent_name} plot HTML conversion failed - no HTML content generated"
                )
                return PlotResult(
                    success=False,
                    message="""Error: Failed to convert plot to HTML.

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

Please try again with a properly created 'fig' variable.""",
                    error_type="html_conversion_error"
                )

            plot_id = self.plot_storage.store_plot(
                html_content=html_content,
                description=plot_input.description,
                agent_name=actual_agent_name,
                data_summary="Custom plotting code",
            )

            if hasattr(self, 'progress_manager') and self.progress_manager:
                try:
                    asyncio.create_task(
                        self.progress_manager.plot_generated(
                            actual_agent_name, plot_id, plot_input.description
                        )
                    )
                except Exception as e:
                    import traceback
                    full_traceback = traceback.format_exc()
                    logger.error(
                        f"Progress manager notification failed: {e}\n\nFull traceback:\n{full_traceback}"
                    )

            success_msg = f"Plot created successfully! Reference as [PLOT:{plot_id}]"
            logger.info(f"Agent {actual_agent_name} created plot {plot_id}")
            
            return PlotResult(
                success=True,
                plot_id=plot_id,
                message=success_msg
            )

        except Exception as e:
            import traceback
            full_traceback = traceback.format_exc()
            error_msg = f"Plotting tool error: {str(e)}. Please check your input and try again."
            logger.error(
                f"Agent {actual_agent_name} plotting failed: {e}\n\nFull traceback:\n{full_traceback}"
            )
            return PlotResult(
                success=False,
                message=error_msg,
                error_type="unexpected_error"
            )

    async def acall(self, args: BaseModel) -> PlotResult:
        return self.call(args)

    def to_openai_tool(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_model.model_json_schema(),
            },
        }


class FrameworkAgnosticPlotListTool:
    
    name: str = "list_available_plots"
    description: str = """
    List all plots available for referencing in your analysis.
    
    Returns information about plots created by other agents that you can reference
    using [PLOT:plot_id] syntax in your text.
    
    Useful for synthesis agents to see what visualizations are available.
    """
    input_model: type[BaseModel] = BaseModel  # No input needed
    
    def __init__(self, plot_storage: PlotStorage):
        self.plot_storage = plot_storage

    def call(self, args: BaseModel = None) -> BaseModel:
        plots = self.plot_storage.list_available_plots()

        if not plots:
            message = "No plots available yet."
        else:
            plot_list = ["Available plots for referencing:"]
            for plot in plots:
                plot_list.append(
                    f"- [PLOT:{plot['plot_id']}]: {plot['description']} "
                    f"(by {plot['agent_name']}, data: {plot['data_summary']})"
                )
            message = "\n".join(plot_list)

        class PlotListResult(BaseModel):
            message: str
            
        return PlotListResult(message=message)

    async def acall(self, args: BaseModel = None) -> BaseModel:
        return self.call(args)

    def to_openai_tool(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {"type": "object", "properties": {}},  # No parameters
            },
        }