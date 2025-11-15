"""Expert-specific output schemas for analysis agents."""

from pydantic import BaseModel, Field

from .agent_outputs import Question


class ReceiverOutputs(BaseModel):
    """Analysis outputs for downstream consumers.
    
    Provides tailored output for three different consumers:
    - Synthesis Agent: Creates comprehensive athlete report
    - Season Planner: Designs 12-24 week macro-cycles
    - Weekly Planner: Creates next 14 days of training
    """
    
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
    """Base class for expert outputs with mutually exclusive modes.
    
    Expert must produce EITHER:
    - Questions for HITL (first invocation when clarification needed)
    - Output for downstream consumers (after HITL or when no questions needed)
    """

    output: list[Question] | ReceiverOutputs = Field(
        ...,
        description="EITHER questions for HITL OR full output for downstream consumers"
    )


class MetricsExpertOutputs(ExpertOutputBase):
    """Structured outputs from Metrics Expert."""
    pass


class ActivityExpertOutputs(ExpertOutputBase):
    """Structured outputs from Activity Expert."""
    pass


class PhysiologyExpertOutputs(ExpertOutputBase):
    """Structured outputs from Physiology Expert."""
    pass