from typing import Annotated, Any

from langgraph.graph import MessagesState


class TrainingAnalysisState(MessagesState):
    user_id: str
    athlete_name: str
    garmin_data: dict[str, Any]
    analysis_context: str
    planning_context: str

    competitions: list[dict[str, Any]]
    current_date: dict[str, str]
    week_dates: list[dict[str, str]]
    style_guide: str
    plotting_enabled: bool
    hitl_enabled: bool

    metrics_summary: str | None
    physiology_summary: str | None
    metrics_result: str | None
    activity_summary: str | None
    activity_result: str | None
    physiology_result: str | None
    synthesis_result: str | None

    season_plan: str | None
    weekly_plan: str | None
    
    synthesis_complete: bool
    season_plan_complete: bool

    analysis_html: str | None
    planning_html: str | None
    plot_resolution_stats: dict[str, Any] | None

    plots: Annotated[list[dict], lambda x, y: x + y]
    plot_storage_data: Annotated[dict[str, dict], lambda x, y: {**x, **y}]
    costs: Annotated[list[dict], lambda x, y: x + y]
    errors: Annotated[list[str], lambda x, y: x + y]
    tool_usage: Annotated[dict[str, int], lambda x, y: {**x, **y}]

    available_plots: Annotated[list[str], lambda x, y: x + y]
    execution_id: str


def create_initial_state(
    user_id: str,
    athlete_name: str,
    garmin_data: dict[str, Any],
    analysis_context: str = "",
    planning_context: str = "",
    competitions: list[dict[str, Any]] | None = None,
    current_date: dict[str, str] | None = None,
    week_dates: list[dict[str, str]] | None = None,
    style_guide: str = "",
    execution_id: str = "",
    plotting_enabled: bool = False,
    hitl_enabled: bool = True,
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
        plotting_enabled=plotting_enabled,
        hitl_enabled=hitl_enabled,
        execution_id=execution_id,
        metrics_summary=None,
        physiology_summary=None,
        metrics_result=None,
        activity_summary=None,
        activity_result=None,
        physiology_result=None,
        synthesis_result=None,
        season_plan=None,
        weekly_plan=None,
        synthesis_complete=False,
        season_plan_complete=False,
        analysis_html=None,
        planning_html=None,
        plot_resolution_stats=None,
        plots=[],
        plot_storage_data={},
        costs=[],
        errors=[],
        tool_usage={},
        available_plots=[],
    )
