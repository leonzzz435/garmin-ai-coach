"""AI service module for handling AI client and agentic framework."""

from .client import create_ai_client
from .prompts import (
    metrics_agent_prompt,
    activity_agent_prompt,
    physiological_agent_prompt,
    synthesis_agent_prompt,
    workout_agent_prompt
    )

__all__ = [
    'create_ai_client',
    'metrics_agent_prompt',
    'activity_agent_prompt',
    'physiological_agent_prompt',
    'synthesis_agent_prompt',
    'workout_agent_prompt'
]
