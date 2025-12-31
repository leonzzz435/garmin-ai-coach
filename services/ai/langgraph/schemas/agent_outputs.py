from pydantic import BaseModel, Field


class Question(BaseModel):
    id: str = Field(..., description="Unique identifier (e.g., 'metrics_q1')")
    message: str = Field(..., description="Question text")
    context: str | None = Field(None, description="Additional context")
    message_type: str = Field("question", description="Type of message")


class AgentOutput(BaseModel):
    """Agent produces EITHER questions for HITL OR content for downstream consumers."""

    output: list[Question] | str = Field(
        ...,
        description="EITHER questions for HITL OR complete output for downstream consumers"
    )