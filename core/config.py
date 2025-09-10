
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from specified env file or default to .env
env_file = os.getenv('ENV_FILE', '.env')
load_dotenv(env_file)

from enum import Enum
import logging
logger = logging.getLogger(__name__)

class AIMode(Enum):
    STANDARD = "standard"
    COST_EFFECTIVE = "cost_effective"
    DEVELOPMENT = "development"

@dataclass
class Config:
    bot_token: str
    anthropic_api_key: str
    openai_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    llm_model: Optional[str] = None  # Main model for reasoning
    function_calling_llm: Optional[str] = None  # Model for tool operations
    
    # AI configuration
    ai_mode: AIMode = AIMode.STANDARD

    @classmethod
    def from_env(cls) -> 'Config':
        bot_token = os.getenv('TELE_BOT_KEY')
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

        # Validate required environment variables
        missing_vars = []
        if not bot_token:
            missing_vars.append('TELE_BOT_KEY')
        if not anthropic_api_key:
            missing_vars.append('ANTHROPIC_API_KEY')

        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}\n"
                "Please set these variables in your environment or .env file."
            )

        # Validate token formats
        if not bot_token.count(':') == 1:
            raise ValueError("Invalid BOT_TOKEN format. Expected format: <bot_id>:<token>")
        
        if not anthropic_api_key.startswith(('sk-ant-api03-', 'sk-ant-')):
            raise ValueError("Invalid ANTHROPIC_API_KEY format")

        if openai_api_key and not openai_api_key.startswith('sk-'):
            raise ValueError("Invalid OPENAI_API_KEY format")
            

        # Get LLM configuration
        llm_model = os.getenv('OPENAI_MODEL_NAME')
        function_calling_llm = os.getenv('FUNCTION_CALLING_LLM')

        return cls(
            bot_token=bot_token,
            anthropic_api_key=anthropic_api_key,
            ai_mode=ai_mode,
            openai_api_key=openai_api_key,
            deepseek_api_key=deepseek_api_key,
            openrouter_api_key=openrouter_api_key,
            llm_model=llm_model,
            function_calling_llm=function_calling_llm
        )

# Global config instance
_config: Optional[Config] = None

def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config
