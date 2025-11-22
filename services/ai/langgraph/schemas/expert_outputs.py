from pydantic import BaseModel, Field

from .agent_outputs import Question


class ReceiverOutputs(BaseModel):
    """Tailored outputs for Synthesis Agent, Season Planner, and Weekly Planner."""
    
    for_synthesis: str = Field(
        ...,
        description="Output for Synthesis Agent creating comprehensive athlete report"
    )
    for_season_planner: str = Field(
        ...,
        description="Output for Season Planner designing 12-24 week macro-cycles"
    )
    for_weekly_planner: str = Field(
        ...,
        description="Output for Weekly Planner creating next 14-day training plan"
    )


class ExpertOutputBase(BaseModel):
    """Expert produces EITHER questions for HITL OR outputs for downstream consumers."""

    output: list[Question] | ReceiverOutputs = Field(
        ...,
        description="EITHER questions for HITL OR full output for downstream consumers"
    )


class MetricsExpertOutputs(ExpertOutputBase):
    pass


class ActivityExpertOutputs(ExpertOutputBase):
    pass


class PhysiologyExpertOutputs(ExpertOutputBase):
    pass