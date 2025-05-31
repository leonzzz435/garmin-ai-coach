"""
Model configuration and selection for CrewAI LLM integration.
"""

import logging
from dataclasses import dataclass
from typing import Dict
from crewai import LLM
from core.config import get_config
from .ai_settings import ai_settings, AgentRole
import litellm

logger = logging.getLogger(__name__)

@dataclass
class ModelConfiguration:
    """Model configuration settings."""
    name: str
    base_url: str

class ModelSelector:
    """Model selection and configuration for CrewAI LLM."""
    
    # Model configurations
    CONFIGURATIONS: Dict[str, ModelConfiguration] = {
        # OpenAI Models
        "gpt-4o": ModelConfiguration(
            name="gpt-4o",
            base_url="https://api.openai.com/v1"
        ),
        "gpt-4.1": ModelConfiguration(
            name="gpt-4.1",
            base_url="https://api.openai.com/v1"
        ),
        "gpt-4.5": ModelConfiguration(
            name="gpt-4.5-preview",
            base_url="https://api.openai.com/v1"
        ),
        "gpt-4o-mini": ModelConfiguration(
            name="gpt-4o-mini",
            base_url="https://api.openai.com/v1"
        ),
        "o1": ModelConfiguration(
            name="o1-preview",
            base_url="https://api.openai.com/v1"
        ),
        "o1-mini": ModelConfiguration(
            name="o1-mini",
            base_url="https://api.openai.com/v1"
        ),
        "o3": ModelConfiguration(
            name="o3",
            base_url="https://api.openai.com/v1"
        ),
        "o3-mini": ModelConfiguration(
            name="o3-mini",
            base_url="https://api.openai.com/v1"
        ),
        "o4-mini": ModelConfiguration(
            name="o4-mini",
            base_url="https://api.openai.com/v1"
        ),
        
        # Anthropic Models
        "claude-4": ModelConfiguration(
            name="claude-sonnet-4-20250514",
            base_url="https://api.anthropic.com"
        ),
        "claude-4-thinking": ModelConfiguration(
            name="claude-sonnet-4-20250514",
            base_url="https://api.anthropic.com"
        ),
        "claude-opus": ModelConfiguration(
            name="claude-opus-4-20250514",
            base_url="https://api.anthropic.com"
        ),
        "claude-opus-thinking": ModelConfiguration(
            name="claude-opus-4-20250514",
            base_url="https://api.anthropic.com"
        ),
        "claude-3-haiku": ModelConfiguration(
            name="claude-3-haiku-20240307",
            base_url="https://api.anthropic.com"
        ),
        
        # DeepSeek Models
        "deepseek-chat": ModelConfiguration(
            name="openrouter/deepseek/deepseek-chat",
            base_url="https://openrouter.ai/api/v1"
        ),
        "deepseek-reasoner": ModelConfiguration(
            name="openrouter/deepseek/deepseek-r1",
            base_url="https://openrouter.ai/api/v1"
        ),
    }

    @classmethod
    def get_llm(cls, role: AgentRole) -> LLM:
        """
        Get a configured LLM instance for CrewAI based on agent role.
        
        Args:
            role: Agent role to get model for
            
        Returns:
            LLM: Configured CrewAI LLM instance
        """
        config = get_config()
        
        # Get model configuration based on role and current mode
        model_name = ai_settings.get_model_for_role(role)
        model_config = cls.CONFIGURATIONS[model_name]
        
        # Choose the correct key based on the provider
        if "anthropic" in model_config.base_url:
            api_key = config.anthropic_api_key
        elif "openrouter" in model_config.base_url:
            api_key = config.openrouter_api_key
        else:
            api_key = config.openai_api_key

        # Add timeout settings to prevent hanging
        logger.info(f"Configuring LLM for role {role.value} with model {model_config.name}")
        
        # Base LLM parameters
        llm_params = {
            "model": model_config.name,
            "base_url": model_config.base_url,
            "api_key": api_key,
        }
        
        # Configure thinking mode and token limits based on model
        if model_name == "claude-opus-thinking":
            llm_params["thinking"] = {"type": "enabled", "budget_tokens": 16000}
            llm_params["max_tokens"] = 32000
            logger.info(f"Using thinking mode for {role.value}")
        elif model_name == "claude-4-thinking":
            llm_params["max_tokens"] = 64000
            llm_params["thinking"] = {"type": "enabled", "budget_tokens": 16000}
            
        llm = LLM(**llm_params)
        logger.info(f"LLM configured for {model_config.name}")
        return llm
