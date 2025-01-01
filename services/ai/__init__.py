"""AI service module for handling AI client and agentic framework."""

from .client import create_ai_client
from .prompts import (
    enhanced_system,
    metrics_agent_prompt,
    activity_agent_prompt,
    physiological_agent_prompt,
    synthesis_agent_prompt,
    workout_system,
    workout_generation_prompt,
    advanced_thinking_prompt
)

__all__ = [
    'create_ai_client',
    'enhanced_system',
    'metrics_agent_prompt',
    'activity_agent_prompt',
    'physiological_agent_prompt',
    'synthesis_agent_prompt',
    'workout_system',
    'workout_generation_prompt',
    'advanced_thinking_prompt'
]
