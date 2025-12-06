from typing import Literal

from pydantic import BaseModel, Field

from .agent_outputs import Question


class QuestionsVariant(BaseModel):
    """Questions for human-in-the-loop interaction."""
    
    type: Literal["questions"] = Field(
        default="questions",
        description="Discriminator field. Set to 'questions' when asking user questions."
    )
    items: list[Question] = Field(
        ...,
        description="List of questions to ask the user"
    )


class AnalysisVariant(BaseModel):
    """Analysis outputs for downstream consumers."""
    
    type: Literal["analysis"] = Field(
        default="analysis",
        description="Discriminator field. Set to 'analysis' when providing analysis outputs."
    )
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

    output: QuestionsVariant | AnalysisVariant = Field(
        ...,
        discriminator="type",
        description="EITHER questions (type='questions') OR analysis outputs (type='analysis')"
    )


class MetricsExpertOutputs(ExpertOutputBase):
    pass


class ActivityExpertOutputs(ExpertOutputBase):
    pass


class PhysiologyExpertOutputs(ExpertOutputBase):
    pass