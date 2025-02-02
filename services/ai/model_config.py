"""
Model configuration and selection for CrewAI LLM integration.
"""

import logging
from dataclasses import dataclass
from typing import Dict
from crewai import LLM
from core.config import get_config
from .ai_settings import ai_settings, AgentRole

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
            name="openai/o3-mini",
            base_url="https://api.openai.com/v1"
        ),
        
        # Anthropic Models
        "claude-3-5-sonnet": ModelConfiguration(
            name="claude-3-5-sonnet-20241022",
            base_url="https://api.anthropic.com"
        ),
        "claude-3-haiku": ModelConfiguration(
            name="claude-3-haiku-20240307",
            base_url="https://api.anthropic.com"
        ),
        # DeepSeek Models
        "deepseek-chat": ModelConfiguration(
            name="deepseek/deepseek-chat",
            base_url="https://api.deepseek.com/v1"
        ),
        "deepseek-reasoner": ModelConfiguration(
            name="deepseek/deepseek-reasoner",
            base_url="https://api.deepseek.com/v1"
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
        elif "deepseek" in model_config.base_url:
            api_key = config.deepseek_api_key
        else:
            api_key = config.openai_api_key

        # Add timeout settings to prevent hanging
        logger.info(f"Configuring LLM for role {role.value} with model {model_config.name}")
        llm = LLM(
            model=model_config.name,
            base_url=model_config.base_url,
            api_key=api_key,
            reasoning_effort="high",
            #temperature=0.,
        )
        logger.info(f"LLM configured for {model_config.name}")
        return llm
