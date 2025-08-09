"""
Model configuration and selection for LangChain LLM integration.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from core.config import get_config
from .ai_settings import ai_settings, AgentRole

logger = logging.getLogger(__name__)

@dataclass
class ModelConfiguration:
    """Model configuration settings."""
    name: str
    base_url: str

class ModelSelector:
    """Model selection and configuration for LangChain LLM."""
    
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
            name="claude-opus-4-1-20250805",
            base_url="https://api.anthropic.com"
        ),
        "claude-opus-thinking": ModelConfiguration(
            name="claude-opus-4-1-20250805",
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

    # Models that support web search
    WEB_SEARCH_SUPPORTED_MODELS = {
        "claude-opus-4-1-20250805",
        "claude-sonnet-4-20250514",
        "claude-3-7-sonnet-20250219",
        "claude-3-5-sonnet-latest",
        "claude-3-5-haiku-latest"
    }

    @classmethod
    def get_llm(cls, role: AgentRole):
        """
        Get a configured LLM instance for LangChain based on agent role.
        
        Args:
            role: Agent role to get model for
            
        Returns:
            LangChain LLM instance (ChatOpenAI, ChatAnthropic, etc.)
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
        
        # Base LLM parameters - optimized for training analysis tasks
        llm_params = {
            "model": model_config.name,
        }
        
        # Configure thinking mode and token limits based on model
        if model_name == "claude-opus-thinking":
            llm_params["max_tokens"] = 32000
            llm_params["thinking"] = {"type": "enabled", "budget_tokens": 16000}
            logger.info(f"Using extended thinking mode for {role.value} (max_tokens: 32000, budget_tokens: 16000)")
        elif model_name == "claude-4-thinking":
            llm_params["max_tokens"] = 64000
            llm_params["thinking"] = {"type": "enabled", "budget_tokens": 16000}
            logger.info(f"Using extended thinking mode for {role.value} (max_tokens: 64000, budget_tokens: 16000)")
        
        # Create the appropriate LangChain LLM based on provider
        if "anthropic" in model_config.base_url:
            llm_params["api_key"] = api_key
            llm = ChatAnthropic(**llm_params)
            
            # Add web search tool using bind_tools if supported
            if model_config.name in cls.WEB_SEARCH_SUPPORTED_MODELS:
                web_search_tool = {"type": "web_search_20250305", "name": "web_search", "max_uses": 3}
                llm = llm.bind_tools([web_search_tool])
                logger.info(f"Web search enabled for {model_config.name} with max 3 uses per request")
            
        elif "openrouter" in model_config.base_url:
            llm_params["openai_api_key"] = api_key
            llm_params["openai_api_base"] = model_config.base_url
            llm = ChatOpenAI(**llm_params)
        else:
            llm_params["openai_api_key"] = api_key
            llm = ChatOpenAI(**llm_params)
            
        logger.info(f"LLM configured for {model_config.name}")
        return llm
