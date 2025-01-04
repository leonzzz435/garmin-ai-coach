"""
Model configuration and selection for CrewAI LLM integration.
"""

from dataclasses import dataclass
from typing import Dict
from crewai import LLM
from core.config import get_config
from .ai_settings import ai_settings, AgentRole

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
            name="o1",
            base_url="https://api.openai.com/v1"
        ),
        "o1-mini": ModelConfiguration(
            name="o1-mini",
            base_url="https://api.openai.com/v1"
        ),
        
        # Anthropic Models
        "claude-3-5-sonnet-20241022": ModelConfiguration(
            name="claude-3-5-sonnet-20241022",
            base_url="https://api.anthropic.com"
        ),
        "claude-3-haiku-20240307": ModelConfiguration(
            name="claude-3-haiku-20240307",
            base_url="https://api.anthropic.com"
        )
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
        
        # Determine API key based on provider
        api_key = (
            config.anthropic_api_key
            if "anthropic" in model_config.base_url
            else config.openai_api_key
        )
        
        return LLM(
            model=model_config.name,
            base_url=model_config.base_url,
            api_key=api_key
        )
