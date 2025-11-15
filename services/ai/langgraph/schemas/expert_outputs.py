"""Expert-specific output schemas for analysis agents."""

from pydantic import BaseModel, Field, field_validator

from .agent_outputs import Question


class ExpertOutputBase(BaseModel):
    """Base class for expert outputs with common three-consumer structure.
    
    Each expert provides tailored output for three different consumers:
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
    questions: list[Question] | None = Field(
        None,
        description="Optional questions requiring user clarification for HITL"
    )
    
    @field_validator("questions", mode="before")
    @classmethod
    def handle_none_string(cls, v):
        """Convert string 'None' or 'null' to actual None."""
        if isinstance(v, str) and v.lower() in ("none", "null"):
            return None
        return v


class MetricsExpertOutputs(ExpertOutputBase):
    """Structured outputs from Metrics Expert."""
    pass


class ActivityExpertOutputs(ExpertOutputBase):
    """Structured outputs from Activity Expert."""
    pass


class PhysiologyExpertOutputs(ExpertOutputBase):
    """Structured outputs from Physiology Expert."""
    pass