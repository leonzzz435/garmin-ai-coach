from pydantic import BaseModel, Field

from .agent_outputs import Question


class ReceiverPayload(BaseModel):
    signals: list[str]
    evidence: list[str]
    implications: list[str]
    uncertainty: list[str] | None = None


class ReceiverOutputs(BaseModel):
    for_synthesis: ReceiverPayload = Field(
        ...,
        description="Output for Synthesis Agent creating comprehensive athlete report"
    )
    for_season_planner: ReceiverPayload = Field(
        ...,
        description="Output for Season Planner designing 12-24 week macro-cycles"
    )
    for_weekly_planner: ReceiverPayload = Field(
        ...,
        description="Output for Weekly Planner creating next 28-day training plan"
    )


class ExpertOutputBase(BaseModel):
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
