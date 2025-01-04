import logging
from datetime import datetime
from typing import Dict, Any
from crewai.tools import BaseTool
from core.security.competitions import SecureCompetitionManager

logger = logging.getLogger(__name__)

class GetReportTool(BaseTool):
    """Tool for providing the analysis report."""
    name: str = "get_report"
    description: str = "Retrieve the generated analysis report for further processing"
    report: str  # The report data

    def _run(self) -> Dict[str, Any]:
        return {"report": self.report}

class GetCurrentDateTool(BaseTool):
    """Tool for providing the current date."""
    name: str = "get_current_date"
    description: str = "Get the current date and time"

    def _run(self) -> Dict[str, Any]:
        current_date = datetime.now()
        return {
            'current_date': current_date.isoformat(),
            'date_formatted': current_date.strftime('%Y-%m-%d')
        }

class GetCompetitionsTool(BaseTool):
    """Tool for providing competition/race data."""
    name: str = "get_competitions"
    description: str = "Get upcoming competitions and race events for workout planning"
    user_id: str  # User ID for accessing user-specific competition data

    def _run(self) -> Dict[str, Any]:
        try:
            competition_manager = SecureCompetitionManager(self.user_id)
            competitions = competition_manager.get_upcoming_competitions()
            return {
                'upcoming_competitions': [
                    {
                        'name': comp.name,
                        'date': comp.date.isoformat(),
                        'race_type': comp.race_type,
                        'priority': comp.priority.value,
                        'target_time': comp.target_time,
                        'location': comp.location,
                        'notes': comp.notes
                    }
                    for comp in competitions
                ]
            }
        except Exception as e:
            logger.error("Error getting competition data: %s", str(e))
            return {'upcoming_competitions': []}

class GetMetricsTool(BaseTool):
    """Tool for retrieving training metrics data."""
    name: str = "get_metrics"
    description: str = "Get training metrics data including load history, VO2 max, endurance scores, and race predictions"
    data: Dict[str, Any]  # Declare data as a field

    def _run(self) -> Dict[str, Any]:
        return {
            'training_load_history': self.data.get('training_load_history', []),
            'vo2_max_history': self.data.get('vo2_max_history', []),
            'endurance_score_history': self.data.get('endurance_score_history', []),
            'hill_score': self.data.get('hill_score', []),
            'race_predictions': self.data.get('race_predictions', [])
        }

class GetActivitiesTool(BaseTool):
    """Tool for retrieving activity data."""
    name: str = "get_activities"
    description: str = "Get recent activities and training status data for analysis"
    data: Dict[str, Any]  # Declare data as a field

    def _run(self) -> Dict[str, Any]:
        return {
            'recent_activities': self.data.get('recent_activities', []),
            'training_status': self.data.get('training_status', {})
        }

class GetPhysioTool(BaseTool):
    """Tool for retrieving physiological data."""
    name: str = "get_physio"
    description: str = "Get physiological data including sleep, readiness, and daily stats"
    data: Dict[str, Any]  # Declare data as a field

    def _run(self) -> Dict[str, Any]:
        return {
            'sleep': self.data.get('sleep', []),
            'training_readiness': self.data.get('training_readiness', []),
            'daily_stats': self.data.get('daily_stats', {}),
            'physiological_markers': self.data.get('physiological_markers', {})
        }
