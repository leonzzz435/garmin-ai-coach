"""Generic agent output schemas for all agents in the workflow."""

from pydantic import BaseModel, Field, field_validator


class Question(BaseModel):
    """Structured question for HITL interaction."""

    id: str = Field(..., description="Unique identifier (e.g., 'metrics_q1')")
    message: str = Field(..., description="Question text")
    context: str | None = Field(None, description="Additional context")
    message_type: str = Field("question", description="Type of message")


class AgentOutput(BaseModel):
    """Structured output from agents with optional questions.

    Usage Guidelines:
    - If you have questions: Populate 'questions' field. The 'content' field can be
      empty or contain preliminary analysis, but will not be used until questions are answered.
    - If no questions OR all questions answered: Leave 'questions' as None/empty and
      provide your COMPLETE analysis in the 'content' field.
    """

    content: str = Field(
        ...,
        description="Complete output. MUST be fully populated when questions is None/empty. "
                   "Can be empty or preliminary when questions are present."
    )
    questions: list[Question] | None = Field(
        None,
        description="List of questions requiring user clarification. If None or empty, "
                   "content must contain complete analysis."
    )

    @field_validator("questions", mode="before")
    @classmethod
    def normalize_questions(cls, v):
        if isinstance(v, str) and v.lower() in ("none", "null"):
            return None
        return v