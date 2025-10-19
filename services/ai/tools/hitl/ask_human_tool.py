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
        Ask the human user for clarification, additional information, or validation.

        This tool pauses workflow execution and waits for human input.
        Use when you need information that isn't available in the provided data.

        Args:
            question: The question to ask the human
            context: Optional context explaining why you're asking

        Returns:
            The human's response as plain text
        """
        payload = {
            "type": "ask_human",
            "question": question,
            "context": context,
            "agent": agent_name,
        }
        reply = interrupt(payload)
        return reply.get("content", "No response provided")
    
    return ask_human_with_agent
