
import os
from dataclasses import dataclass

from dotenv import load_dotenv

env_file = os.getenv('ENV_FILE', '.env')
load_dotenv(env_file)

import logging
from enum import Enum

logger = logging.getLogger(__name__)

class AIMode(Enum):
    STANDARD = "standard"
    COST_EFFECTIVE = "cost_effective"
    DEVELOPMENT = "development"

@dataclass
class Config:
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    deepseek_api_key: str | None = None
    openrouter_api_key: str | None = None
    
    # AI configuration
    ai_mode: AIMode = AIMode.STANDARD

    @classmethod
    def from_env(cls) -> 'Config':
        anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        openai_api_key = os.getenv('OPENAI_API_KEY')
        deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        
        # Get AI mode configuration
        ai_mode_str = os.getenv('AI_MODE', 'standard').lower()
        try:
            ai_mode = AIMode(ai_mode_str)
        except ValueError:
            ai_mode = AIMode.STANDARD
            logger.info(f"Warning: Invalid AI_MODE '{ai_mode_str}', using {ai_mode.value}")

        if anthropic_api_key and not anthropic_api_key.startswith(('sk-ant-api03-', 'sk-ant-')):
            raise ValueError("Invalid ANTHROPIC_API_KEY format")

        if openai_api_key and not openai_api_key.startswith('sk-'):
            raise ValueError("Invalid OPENAI_API_KEY format")

        return cls(
            anthropic_api_key=anthropic_api_key,
            ai_mode=ai_mode,
            openai_api_key=openai_api_key,
            deepseek_api_key=deepseek_api_key,
            openrouter_api_key=openrouter_api_key,
        )

def get_config() -> Config:
    if not hasattr(get_config, '_config'):
        get_config._config = Config.from_env()
    return get_config._config


def reload_config() -> Config:
    """Forces a reload of the configuration from environment variables."""
    if hasattr(get_config, '_config'):
        delattr(get_config, '_config')
    return get_config()
