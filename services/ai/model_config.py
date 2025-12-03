import logging
from dataclasses import dataclass

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from core.config import get_config

from .ai_settings import AgentRole, ai_settings

logger = logging.getLogger(__name__)


@dataclass
class ModelConfiguration:
    name: str
    base_url: str


class ModelSelector:

    CONFIGURATIONS: dict[str, ModelConfiguration] = {
        # OpenAI Models
        "gpt-4o": ModelConfiguration(name="gpt-4o", base_url="https://api.openai.com/v1"),
        "gpt-4.1": ModelConfiguration(name="gpt-4.1", base_url="https://api.openai.com/v1"),
        "gpt-4.5": ModelConfiguration(name="gpt-4.5-preview", base_url="https://api.openai.com/v1"),
        "gpt-4o-mini": ModelConfiguration(name="gpt-4o-mini", base_url="https://api.openai.com/v1"),
        "o1": ModelConfiguration(name="o1-preview", base_url="https://api.openai.com/v1"),
        "o1-mini": ModelConfiguration(name="o1-mini", base_url="https://api.openai.com/v1"),
        "o3": ModelConfiguration(name="o3", base_url="https://api.openai.com/v1"),
        "o3-mini": ModelConfiguration(name="o3-mini", base_url="https://api.openai.com/v1"),
        "o4-mini": ModelConfiguration(name="o4-mini", base_url="https://api.openai.com/v1"),
        "gpt-5": ModelConfiguration(name="gpt-5.1", base_url="https://api.openai.com/v1"),
        "gpt-5-mini": ModelConfiguration(name="gpt-5-mini", base_url="https://api.openai.com/v1"),
        # Anthropic Models
        "claude-4": ModelConfiguration(
            name="claude-sonnet-4-5-20250929", base_url="https://api.anthropic.com"
        ),
        "claude-4-thinking": ModelConfiguration(
            name="claude-sonnet-4-5-20250929", base_url="https://api.anthropic.com"
        ),
        "claude-opus": ModelConfiguration(
            name="claude-opus-4-1-20250805", base_url="https://api.anthropic.com"
        ),
        "claude-opus-thinking": ModelConfiguration(
            name="claude-opus-4-1-20250805", base_url="https://api.anthropic.com"
        ),
        "claude-3-haiku": ModelConfiguration(
            name="claude-3-haiku-20240307", base_url="https://api.anthropic.com"
        ),
        # DeepSeek Models
        "deepseek-chat": ModelConfiguration(
            name="openrouter/deepseek/deepseek-chat", base_url="https://openrouter.ai/api/v1"
        ),
        "deepseek-reasoner": ModelConfiguration(
            name="openrouter/deepseek/deepseek-r1", base_url="https://openrouter.ai/api/v1"
        ),
        "deepseek-v3.2-exp": ModelConfiguration(
            name="deepseek/deepseek-v3.2-exp", base_url="https://openrouter.ai/api/v1"
        ),
        # Google Models (via OpenRouter)
        "gemini-2.5-pro": ModelConfiguration(
            name="google/gemini-2.5-pro", base_url="https://openrouter.ai/api/v1"
        ),
        # xAI Models (via OpenRouter)
        "grok-4": ModelConfiguration(
            name="x-ai/grok-4", base_url="https://openrouter.ai/api/v1"
        ),
    }

    @classmethod
    def get_llm(cls, role: AgentRole):
        model_name = ai_settings.get_model_for_role(role)
        model_config = cls.CONFIGURATIONS[model_name]
        config = get_config()
        
        api_key_map = {
            "anthropic": config.anthropic_api_key,
            "openrouter": config.openrouter_api_key,
        }
        api_key = next((api_key_map[k] for k in api_key_map if k in model_config.base_url), config.openai_api_key)

        logger.info(f"Configuring LLM for role {role.value} with model {model_config.name}")

        llm_params = {"model": model_config.name, "api_key": api_key}
        
        model_configs = {
            "claude-opus-thinking": {
                "max_tokens": 32000,
                "thinking": {"type": "enabled", "budget_tokens": 16000},
                "log": "Using extended thinking mode for {role} (max_tokens: 32000, budget_tokens: 16000)",
            },
            "claude-4-thinking": {
                "max_tokens": 64000,
                "thinking": {"type": "enabled", "budget_tokens": 16000},
                "log": "Using extended thinking mode for {role} (max_tokens: 64000, budget_tokens: 16000)",
            },
            "claude-4": {
                "max_tokens": 64000,
                "log": "Using extended output tokens for {role} (max_tokens: 64000)",
            },
            "claude-opus": {
                "max_tokens": 32000,
                "log": "Using extended output tokens for {role} (max_tokens: 32000)",
            },
            "gpt-5": {
                "use_responses_api": True,
                "reasoning": {"effort": "high"},
                "model_kwargs": {"text": {"verbosity": "medium"}},
                "log": "Using GPT-5 with Responses API for {role} (verbosity: medium, reasoning_effort: high)",
            },
            "gpt-5-mini": {
                "use_responses_api": True,
                "reasoning": {"effort": "high"},
                "model_kwargs": {"text": {"verbosity": "high"}},
                "log": "Using GPT-5-mini with Responses API for {role} (verbosity: high, reasoning_effort: high)",
            },
            "deepseek-v3.2-exp": {
                "extra_body": {"reasoning": {"enabled": True}},
                "log": "Using DeepSeek V3.2 Exp with reasoning enabled for {role}",
            },
        }
        
        if model_name in model_configs:
            config_data = model_configs[model_name]
            log_msg = config_data.pop("log", None)
            llm_params.update(config_data)
            if log_msg:
                logger.info(log_msg.format(role=role.value))

        if "anthropic" in model_config.base_url:
            return ChatAnthropic(**llm_params)
        
        llm_params["base_url"] = model_config.base_url
        return ChatOpenAI(**llm_params)
