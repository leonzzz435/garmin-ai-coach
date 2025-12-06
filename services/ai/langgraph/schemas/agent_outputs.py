from typing import Literal

from pydantic import BaseModel, Field


class Question(BaseModel):
    id: str = Field(..., description="Unique identifier (e.g., 'metrics_q1')")
    message: str = Field(..., description="Question text")
    context: str | None = Field(None, description="Additional context")
    message_type: str = Field("question", description="Type of message")


class QuestionsAgentVariant(BaseModel):
    """Questions for human-in-the-loop interaction."""
    
    type: Literal["questions"] = Field(
        default="questions",
        description="Discriminator field. Set to 'questions' when asking user questions."
    )
    items: list[Question] = Field(
        ...,
        description="List of questions to ask the user"
    )


class ContentAgentVariant(BaseModel):
    """Content output for downstream consumers."""
    
    type: Literal["content"] = Field(
        default="content",
        description="Discriminator field. Set to 'content' when providing output."
    )
    content: str = Field(
        ...,
        description="The complete output content for downstream consumers"
    )


class AgentOutput(BaseModel):
    """Agent produces EITHER questions for HITL OR content for downstream consumers."""

    output: QuestionsAgentVariant | ContentAgentVariant = Field(
        ...,
        discriminator="type",
        description="EITHER questions (type='questions') OR content (type='content')"
    )