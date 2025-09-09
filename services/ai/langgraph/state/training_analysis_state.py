from typing import Annotated, List, Dict, Any, Optional
from typing_extensions import TypedDict
from langgraph.graph import MessagesState


class TrainingAnalysisState(MessagesState):
    user_id: str
    athlete_name: str
    garmin_data: Dict[str, Any]
    analysis_context: str
    planning_context: str
    
    competitions: List[Dict[str, Any]]
    current_date: Dict[str, str]
    week_dates: List[Dict[str, str]]
    style_guide: str
    
    metrics_result: Optional[str]
    activity_summary: Optional[str]
    activity_result: Optional[str]
    physiology_result: Optional[str]
    synthesis_result: Optional[str]
    
    season_plan: Optional[str]
    weekly_plan: Optional[str]
    
    analysis_html: Optional[str]
    planning_html: Optional[str]
    plot_resolution_stats: Optional[Dict[str, Any]]
    
    plots: Annotated[List[Dict], lambda x, y: x + y]
    plot_storage_data: Annotated[Dict[str, Dict], lambda x, y: {**x, **y}]
    costs: Annotated[List[Dict], lambda x, y: x + y]
    errors: Annotated[List[str], lambda x, y: x + y]
    tool_usage: Annotated[Dict[str, int], lambda x, y: {**x, **y}]
    
    available_plots: Annotated[List[str], lambda x, y: x + y]
    execution_id: str


def create_initial_state(
    user_id: str,
    athlete_name: str, 
    garmin_data: Dict[str, Any],
    analysis_context: str = "",
    planning_context: str = "",
    competitions: List[Dict[str, Any]] = None,
    current_date: Dict[str, str] = None,
    week_dates: List[Dict[str, str]] = None,
    style_guide: str = "",
    execution_id: str = ""
) -> TrainingAnalysisState:
    return TrainingAnalysisState(
        user_id=user_id,
        athlete_name=athlete_name,
        garmin_data=garmin_data,
        analysis_context=analysis_context,
        planning_context=planning_context,
        
        competitions=competitions or [],
        current_date=current_date or {},
        week_dates=week_dates or [],
        style_guide=style_guide,
        
        metrics_result=None,
        activity_summary=None,
        activity_result=None,
        physiology_result=None,
        synthesis_result=None,
        
        season_plan=None,
        weekly_plan=None,
        
        analysis_html=None,
        planning_html=None,
        
        plots=[],
        plot_storage_data={},
        costs=[],
        errors=[],
        tool_usage={},
        
        available_plots=[],
        execution_id=execution_id
    )