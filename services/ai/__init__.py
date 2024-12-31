"""AI service module for handling AI client and prompt management."""

from .client import create_ai_client
from .prompts import (
    system,
    data_extraction_prompt_01,
    data_extraction_prompt_02,
    training_generation_prompt,
    workout_system,
    workout_generation_prompt,
    advanced_thinking_prompt
)

__all__ = [
    'create_ai_client',
    'system',
    'data_extraction_prompt_01',
    'data_extraction_prompt_02',
    'training_generation_prompt',
    'workout_system',
    'workout_generation_prompt',
    'advanced_thinking_prompt'
]
