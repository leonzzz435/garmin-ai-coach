from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import matplotlib.pyplot as plt
import seaborn as sns
import io
import base64
import logging
from typing import Dict, List, Optional, Union, Literal
import json

logger = logging.getLogger(__name__)

class PlotInput(BaseModel):
    """Input schema for visualization tool."""
    plot_type: Literal['line', 'bar', 'scatter', 'distribution'] = Field(
        ..., 
        description="Type of plot to create"
    )
    data: Dict = Field(
        ..., 
        description="Data for plotting. For line/bar/scatter plots: {'x': [...], 'y': [...] or {'label': [...]}}, for distribution: {'values': [...] or {'label': [...]}}"
    )
    title: Optional[str] = Field(
        None, 
        description="Plot title"
    )
    xlabel: Optional[str] = Field(
        None, 
        description="X-axis label"
    )
    ylabel: Optional[str] = Field(
        None, 
        description="Y-axis label"
    )
    figsize: Optional[tuple] = Field(
        (10, 6), 
        description="Figure size in inches"
    )
    grid: Optional[bool] = Field(
        True, 
        description="Whether to show grid lines"
    )

from pydantic import ConfigDict

class VisualizationTool(BaseTool):
    """Tool for creating data visualizations."""
    name: str = "visualization_tool"
    description: str = """Creates data visualizations for analysis and reporting.
    Useful for generating plots of training metrics, performance trends, and distributions.
    Can create line plots, bar charts, scatter plots, and distribution plots."""
    args_schema: type[BaseModel] = PlotInput
    plots: List[Dict] = []  # Store plots for later retrieval

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def _run(
        self, 
        plot_type: str,
        data: Dict,
        title: Optional[str] = None,
        xlabel: Optional[str] = None,
        ylabel: Optional[str] = None,
        figsize: tuple = (10, 6),
        grid: bool = True,
        plot_id: Optional[str] = None
    ) -> str:
        """
        Create a plot based on the specified parameters.
        
        Returns:
            Base64 encoded string of the plot image
        """
        logger.info(f"Creating plot: type={plot_type}, title={title}")
        logger.info(f"Plot data keys: {list(data.keys())}")
        logger.debug(f"Plot data content: {data}")
        # Set style defaults
        plt.style.use('seaborn')
        plt.figure(figsize=figsize)
        
        # Create the specified type of plot
        if plot_type == 'line':
            x = data.get('x', range(len(data['y'])))
            if isinstance(data['y'], dict):
                for label, y_data in data['y'].items():
                    plt.plot(x, y_data, label=label)
                plt.legend()
            else:
                plt.plot(x, data['y'])
                
        elif plot_type == 'bar':
            x = data.get('x', range(len(data['y'])))
            plt.bar(x, data['y'])
            
        elif plot_type == 'scatter':
            plt.scatter(data['x'], data['y'])
            
        elif plot_type == 'distribution':
            if isinstance(data['values'], dict):
                for label, values in data['values'].items():
                    sns.kdeplot(data=values, label=label)
                plt.legend()
            else:
                sns.kdeplot(data=data['values'])
        
        # Add labels and grid
        if title:
            plt.title(title)
        if xlabel:
            plt.xlabel(xlabel)
        if ylabel:
            plt.ylabel(ylabel)
        if grid:
            plt.grid(True, alpha=0.3)
            
        # Adjust layout and convert to base64
        plt.tight_layout()
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=100)
        buffer.seek(0)
        image_png = buffer.getvalue()
        buffer.close()
        plt.close()
        
        # Store plot data
        plot_data = {
            'type': plot_type,
            'data': base64.b64encode(image_png).decode(),
            'metadata': {
                'title': title,
                'xlabel': xlabel,
                'ylabel': ylabel
            }
        }
        self.plots.append(plot_data)
        
        # Return a simple message - we'll handle the plots at the flow level
        return f"Created {plot_type} visualization"

    def _handle_error(self, error: Exception) -> str:
        """Handle errors during plot creation."""
        logger.error(f"Error creating visualization: {str(error)}", exc_info=True)
        return f"Error creating visualization: {str(error)}"

    def get_plots(self) -> List[Dict]:
        """Get all plots created by this tool."""
        return self.plots

def cache_function(args: Dict, result: str) -> bool:
    """
    Determine if the result should be cached.
    
    We'll cache the path references since they're small.
    """
    return True
