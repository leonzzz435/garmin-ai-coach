
import logging
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class PlotMetadata:
    plot_id: str
    description: str
    agent_name: str
    created_at: datetime
    html_content: str
    data_summary: str

class PlotStorage:
    
    def __init__(self, execution_id: str):
        self.execution_id = execution_id
        self.plots: Dict[str, PlotMetadata] = {}
        self.plot_counter = 0
        logger.info(f"Initialized plot storage for execution {execution_id}")
    
    def generate_plot_id(self, agent_name: str) -> str:
        self.plot_counter += 1
        timestamp = int(time.time() * 1000)  # Millisecond precision
        return f"{agent_name}_{timestamp}_{self.plot_counter:03d}"
    
    def store_plot(self, html_content: str, description: str, agent_name: str, data_summary: str = "") -> str:
        plot_id = self.generate_plot_id(agent_name)
        
        metadata = PlotMetadata(
            plot_id=plot_id,
            description=description,
            agent_name=agent_name,
            created_at=datetime.now(),
            html_content=html_content,
            data_summary=data_summary
        )
        
        self.plots[plot_id] = metadata
        logger.info(f"Stored plot {plot_id} from agent {agent_name}")
        return plot_id
    
    def get_plot(self, plot_id: str) -> Optional[PlotMetadata]:
        return self.plots.get(plot_id)
    
    def get_plot_html(self, plot_id: str) -> Optional[str]:
        plot = self.get_plot(plot_id)
        return plot.html_content if plot else None
    
    def list_available_plots(self) -> List[Dict[str, Any]]:
        plots_list = []
        for plot_id, metadata in self.plots.items():
            plots_list.append({
                'plot_id': plot_id,
                'description': metadata.description,
                'agent_name': metadata.agent_name,
                'created_at': metadata.created_at.isoformat(),
                'data_summary': metadata.data_summary
            })
        
        # Sort by creation time
        plots_list.sort(key=lambda x: x['created_at'])
        return plots_list
    
    def get_plots_by_agent(self, agent_name: str) -> List[PlotMetadata]:
        agent_plots = [plot for plot in self.plots.values() if plot.agent_name == agent_name]
        agent_plots.sort(key=lambda x: x.created_at)
        return agent_plots
    
    def get_all_plots(self) -> Dict[str, PlotMetadata]:
        return self.plots.copy()
    
    def clear_plots(self):
        plot_count = len(self.plots)
        self.plots.clear()
        self.plot_counter = 0
        logger.info(f"Cleared {plot_count} plots from execution {self.execution_id}")
    
    def get_storage_stats(self) -> Dict[str, Any]:
        total_plots = len(self.plots)
        agents = set(plot.agent_name for plot in self.plots.values())
        total_html_size = sum(len(plot.html_content) for plot in self.plots.values())
        
        return {
            'execution_id': self.execution_id,
            'total_plots': total_plots,
            'unique_agents': len(agents),
            'agents': list(agents),
            'total_html_size_bytes': total_html_size,
            'total_html_size_mb': round(total_html_size / (1024 * 1024), 2)
        }
    
    def __str__(self) -> str:
        stats = self.get_storage_stats()
        return f"PlotStorage(execution_id={self.execution_id}, plots={stats['total_plots']}, agents={stats['unique_agents']})"