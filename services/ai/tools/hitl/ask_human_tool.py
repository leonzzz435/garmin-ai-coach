from langchain_core.tools import tool
from langgraph.types import interrupt
from pydantic import BaseModel, Field


class CommunicateWithHumanInput(BaseModel):
    message: str = Field(
        ...,
        description="Your message to communicate with the human athlete or coach. Can be a question, observation, suggestion, or request for clarification.",
    )
    message_type: str = Field(
        ...,
        description="Type of communication: 'question' (seeking specific information), 'observation' (sharing insight that needs feedback), 'suggestion' (proposing idea for validation), or 'clarification' (resolving ambiguity)",
    )
    context: str = Field(
        default="",
        description="Brief context about what you're analyzing and why this communication matters",
    )


def create_communicate_with_human_tool(agent_name: str = "Agent"):
    @tool("communicate_with_human", args_schema=CommunicateWithHumanInput)
    def communicate_with_human_agent(message: str, message_type: str, context: str = "") -> str:
        """
        Communicate interactively with the human to create a collaborative coaching experience.
        
        This tool enables natural, conversational interaction during analysis. Use it to:
        - Ask questions about training context, goals, or preferences
        - Share interesting observations and get athlete feedback
        - Validate assumptions or hypotheses you've formed
        - Clarify ambiguous data points or unusual patterns
        - Propose ideas and get real-time input
        - Build rapport and understanding throughout the session
        
        The communication should feel natural and coaching-oriented, staying within your area
        of expertise while being conversational rather than purely transactional.

        Args:
            message: Your communication to the human (question, observation, or suggestion)
            message_type: Type - 'question', 'observation', 'suggestion', or 'clarification'
            context: Why this communication is relevant to your current analysis

        Returns:
            The human's response, which you should incorporate into your analysis
            
        Examples:
            - Question: "I notice your long runs have been consistently under 90 minutes.
              Are you intentionally capping duration, or is this a scheduling constraint?"
            - Observation: "Your heart rate response during intervals has improved significantly
              over the past month. Have you noticed feeling stronger during these sessions?"
            - Suggestion: "Based on your training load, I'm considering recommending a recovery
              week. How is your energy level feeling right now?"
            - Clarification: "The data shows a gap in training between Dec 15-22.
              Was this planned recovery, illness, or something else?"
        """
        return interrupt({
            "type": "communicate_with_human",
            "message": message,
            "message_type": message_type,
            "context": context,
            "agent": agent_name,
        }).get("content", "No response provided")

    return communicate_with_human_agent
