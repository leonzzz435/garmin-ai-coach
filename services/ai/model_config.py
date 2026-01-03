import logging
from dataclasses import dataclass

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from core.config import get_config

from .ai_settings import AgentRole, ai_settings

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass
class ModelConfiguration:
    name: str
    base_url: str
    openrouter_name: str | None = None


class ModelSelector:

    @staticmethod
    def _detect_provider(base_url: str) -> str:
        if "anthropic" in base_url:
            return "anthropic"
        elif "openai.com" in base_url:
            return "openai"
        else:
            return "openrouter"

    CONFIGURATIONS: dict[str, ModelConfiguration] = {
        # OpenAI Models
        "gpt-4o": ModelConfiguration(
            name="gpt-4o",
            base_url="https://api.openai.com/v1",
            openrouter_name="openai/gpt-4o",
        ),
        "gpt-4.1": ModelConfiguration(
            name="gpt-4.1",
            base_url="https://api.openai.com/v1",
            openrouter_name="openai/gpt-4.1",
        ),
        "gpt-4.5": ModelConfiguration(
            name="gpt-4.5-preview",
            base_url="https://api.openai.com/v1",
            openrouter_name="openai/gpt-4.5-preview",
        ),
        "gpt-4o-mini": ModelConfiguration(
            name="gpt-4o-mini",
            base_url="https://api.openai.com/v1",
            openrouter_name="openai/gpt-4o-mini",
        ),
        "o1": ModelConfiguration(
            name="o1-preview",
            base_url="https://api.openai.com/v1",
            openrouter_name="openai/o1-preview",
        ),
        "o1-mini": ModelConfiguration(
            name="o1-mini",
            base_url="https://api.openai.com/v1",
            openrouter_name="openai/o1-mini",
        ),
        "o3": ModelConfiguration(
            name="o3",
            base_url="https://api.openai.com/v1",
            openrouter_name="openai/o3",
        ),
        "o3-mini": ModelConfiguration(
            name="o3-mini",
            base_url="https://api.openai.com/v1",
            openrouter_name="openai/o3-mini",
        ),
        "o4-mini": ModelConfiguration(
            name="o4-mini",
            base_url="https://api.openai.com/v1",
            openrouter_name="openai/o4-mini",
        ),
        "gpt-5": ModelConfiguration(
            name="gpt-5.1",
            base_url="https://api.openai.com/v1",
            openrouter_name="openai/gpt-5.1",
        ),
        "gpt-5-mini": ModelConfiguration(
            name="gpt-5-mini",
            base_url="https://api.openai.com/v1",
            openrouter_name="openai/gpt-5-mini",
        ),
        # Anthropic Models
        "claude-4": ModelConfiguration(
            name="claude-sonnet-4-5-20250929",
            base_url="https://api.anthropic.com",
            openrouter_name="anthropic/claude-sonnet-4.5",
        ),
        "claude-4-thinking": ModelConfiguration(
            name="claude-sonnet-4-5-20250929",
            base_url="https://api.anthropic.com",
            openrouter_name="anthropic/claude-sonnet-4.5",
        ),
        "claude-opus": ModelConfiguration(
            name="claude-opus-4-1-20250805",
            base_url="https://api.anthropic.com",
            openrouter_name="anthropic/claude-opus-4.1",
        ),
        "claude-opus-thinking": ModelConfiguration(
            name="claude-opus-4-1-20250805",
            base_url="https://api.anthropic.com",
            openrouter_name="anthropic/claude-opus-4.1",
        ),
        "claude-3-haiku": ModelConfiguration(
            name="claude-3-haiku-20240307",
            base_url="https://api.anthropic.com",
            openrouter_name="anthropic/claude-3-haiku",
        ),
        # DeepSeek Models
        "deepseek-chat": ModelConfiguration(
            name="openrouter/deepseek/deepseek-chat", base_url=OPENROUTER_BASE_URL
        ),
        "deepseek-reasoner": ModelConfiguration(
            name="openrouter/deepseek/deepseek-r1", base_url=OPENROUTER_BASE_URL
        ),
        "deepseek-v3.2": ModelConfiguration(
            name="deepseek/deepseek-v3.2", base_url=OPENROUTER_BASE_URL
        ),
        # Google Models (via OpenRouter)
        "gemini-2.5-pro": ModelConfiguration(
            name="google/gemini-2.5-pro", base_url=OPENROUTER_BASE_URL
        ),
        # xAI Models (via OpenRouter)
        "grok-4": ModelConfiguration(
            name="x-ai/grok-4", base_url=OPENROUTER_BASE_URL
        ),
    }

    @classmethod
    def get_llm(cls, role: AgentRole):
        model_name = ai_settings.get_model_for_role(role)
        selected_config = cls.CONFIGURATIONS.get(model_name)
        if not selected_config:
            raise RuntimeError(f"Unknown model '{model_name}' in configuration")
        config = get_config()
        
        base_url = selected_config.base_url
        final_model_name = selected_config.name
        provider = cls._detect_provider(base_url)
        
        key_map = {
            "anthropic": config.anthropic_api_key,
            "openai": config.openai_api_key,
            "openrouter": config.openrouter_api_key,
        }
        
        api_key = key_map.get(provider)
        use_fallback = False
        
        if not api_key and provider in ("anthropic", "openai"):
            if not config.openrouter_api_key:
                raise RuntimeError(f"{provider.title()} API key or OpenRouter API key is required")
            if not selected_config.openrouter_name:
                raise RuntimeError(
                    f"{provider.title()} model {selected_config.name} is not available via OpenRouter; "
                    f"provide an {provider.upper()}_API_KEY"
                )
            api_key = config.openrouter_api_key
            base_url = OPENROUTER_BASE_URL
            final_model_name = selected_config.openrouter_name
            use_fallback = True
            logger.info(
                "Routing %s model %s through OpenRouter (no %s API key available)",
                provider.title(),
                selected_config.name,
                provider.title(),
            )
        elif not api_key:
            raise RuntimeError("OpenRouter API key is required for OpenRouter-hosted models")

        logger.info(f"Configuring LLM for role {role.value} with model {final_model_name}")
        
        llm_params = {"model": final_model_name, "api_key": api_key}
        
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
            "deepseek-v3.2": {
                "extra_body": {"reasoning": {"enabled": True}},
                "log": "Using DeepSeek V3.2 with reasoning enabled for {role}",
            },
        }
        
        if model_name in model_configs:
            config_data = model_configs[model_name].copy()
            log_msg = config_data.pop("log", None)
            llm_params.update(config_data)
            if log_msg:
                logger.info(log_msg.format(role=role.value))

        if base_url == OPENROUTER_BASE_URL:
            # Strip provider-specific parameters when routing through OpenRouter
            # as they are not supported by OpenRouter's API
            llm_params.pop("use_responses_api", None)
            llm_params.pop("reasoning", None)
            llm_params.pop("model_kwargs", None)
            llm_params.pop("extra_body", None)
            if provider == "anthropic":
                llm_params.pop("thinking", None)

        if provider == "anthropic" and not use_fallback:
            return ChatAnthropic(**llm_params)

        llm_params["base_url"] = base_url
        return ChatOpenAI(**llm_params)
