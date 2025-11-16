"""Generic agent output schemas for all agents in the workflow."""

from pydantic import BaseModel, Field


class Question(BaseModel):
    """Structured question for HITL interaction."""

    id: str = Field(..., description="Unique identifier (e.g., 'metrics_q1')")
    message: str = Field(..., description="Question text")
    context: str | None = Field(None, description="Additional context")
    message_type: str = Field("question", description="Type of message")


class AgentOutput(BaseModel):
    """Structured output from agents with mutually exclusive modes.
    
    Agent must produce EITHER:
    - Questions for HITL (first invocation when clarification needed)
    - Content for downstream consumers (after HITL or when no questions needed)
    """

    output: list[Question] | str = Field(
        ...,
        description="EITHER questions for HITL OR complete output for downstream consumers"
    )