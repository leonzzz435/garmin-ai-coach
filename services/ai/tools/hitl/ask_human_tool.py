from langchain_core.tools import tool
from langgraph.types import interrupt
from pydantic import BaseModel, Field


class AskHumanInput(BaseModel):
    question: str = Field(
        ...,
        description="Clear, specific question to ask the human. Be concise and direct.",
    )
    context: str = Field(
        default="",
        description="Optional context about why this question is being asked",
    )


def create_ask_human_tool(agent_name: str = "Agent"):
    @tool("ask_human", args_schema=AskHumanInput)
    def ask_human_with_agent(question: str, context: str = "") -> str:
        """
        Ask the human for information within YOUR domain of responsibility.

        This workflow has multiple specialized agents, each handling different aspects.
        Before asking, consider: Is this question about MY area of responsibility,
        or is another agent in the workflow handling this?

        Only ask about information that:
        - Falls within your specific role and responsibilities
        - Is not already present in your input data
        - Is truly necessary for your analysis

        Args:
            question: The question to ask the human
            context: Optional context explaining why you're asking

        Returns:
            The human's response as plain text
        """
        return interrupt({
            "type": "ask_human",
            "question": question,
            "context": context,
            "agent": agent_name,
        }).get("content", "No response provided")

    return ask_human_with_agent
