import types

import pytest

from core.config import AIMode, Config
from services.ai import model_config
from services.ai.ai_settings import AgentRole
from services.ai.model_config import OPENROUTER_BASE_URL, ModelSelector


class _StubSettings:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def get_model_for_role(self, _: AgentRole) -> str:
        return self.model_name


@pytest.mark.parametrize(
    ("model_name", "api_key_field", "expected_model", "expected_client"),
    [
        ("claude-4", "anthropic_api_key", "claude-sonnet-4-5-20250929", "ChatAnthropic"),
        ("gpt-4o", "openai_api_key", "gpt-4o", "ChatOpenAI"),
    ],
)
def test_prefers_direct_api_when_key_available(
    monkeypatch, model_name, api_key_field, expected_model, expected_client
):
    api_key_values = {
        "anthropic_api_key": "sk-ant-api03-test",
        "openai_api_key": "sk-test",
    }
    config_dict = {
        api_key_field: api_key_values[api_key_field],
        "openrouter_api_key": "sk-or-test",
        "ai_mode": AIMode.STANDARD,
    }
    config = Config(**config_dict)
    monkeypatch.setattr(model_config, "get_config", lambda: config)
    monkeypatch.setattr(model_config, "ai_settings", _StubSettings(model_name))

    captured = {}

    def fake_chat_anthropic(**kwargs):
        captured.update(kwargs)
        captured["client"] = "ChatAnthropic"
        return types.SimpleNamespace(**kwargs)

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        captured["client"] = "ChatOpenAI"
        return types.SimpleNamespace(**kwargs)

    monkeypatch.setattr(model_config, "ChatAnthropic", fake_chat_anthropic)
    monkeypatch.setattr(model_config, "ChatOpenAI", fake_chat_openai)

    ModelSelector.get_llm(AgentRole.SUMMARIZER)

    assert captured["model"] == expected_model
    assert captured["api_key"] == api_key_values[api_key_field]
    if expected_client == "ChatOpenAI":
        assert captured["base_url"] == "https://api.openai.com/v1"
    else:
        assert "base_url" not in captured
    assert captured["client"] == expected_client


@pytest.mark.parametrize(
    ("model_name", "expected_openrouter_name"),
    [
        ("claude-4", "anthropic/claude-sonnet-4.5"),
        ("claude-4-thinking", "anthropic/claude-sonnet-4.5"),
        ("claude-3-haiku", "anthropic/claude-3-haiku"),
    ],
)
def test_routes_anthropic_through_openrouter_when_missing_key(
    monkeypatch, model_name, expected_openrouter_name
):
    config = Config(openrouter_api_key="sk-or-test", ai_mode=AIMode.STANDARD)
    monkeypatch.setattr(model_config, "get_config", lambda: config)
    monkeypatch.setattr(model_config, "ai_settings", _StubSettings(model_name))

    captured = {}

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(**kwargs)

    def fake_chat_anthropic(**_kwargs):
        raise AssertionError("ChatAnthropic should not be used when routing via OpenRouter")

    monkeypatch.setattr(model_config, "ChatOpenAI", fake_chat_openai)
    monkeypatch.setattr(model_config, "ChatAnthropic", fake_chat_anthropic)

    ModelSelector.get_llm(AgentRole.SUMMARIZER)

    assert captured["model"] == expected_openrouter_name
    assert captured["api_key"] == "sk-or-test"
    assert captured["base_url"] == OPENROUTER_BASE_URL
    assert "thinking" not in captured
    assert "use_responses_api" not in captured


@pytest.mark.parametrize(
    ("model_name", "expected_openrouter_name"),
    [
        ("gpt-4.1", "openai/gpt-4.1"),
        ("gpt-4o", "openai/gpt-4o"),
        ("gpt-4.5", "openai/gpt-4.5-preview"),
        ("gpt-4o-mini", "openai/gpt-4o-mini"),
        ("o1", "openai/o1-preview"),
        ("o1-mini", "openai/o1-mini"),
        ("o3", "openai/o3"),
        ("o3-mini", "openai/o3-mini"),
        ("o4-mini", "openai/o4-mini"),
        ("gpt-5", "openai/gpt-5.1"),
        ("gpt-5-mini", "openai/gpt-5-mini"),
    ],
)
def test_routes_openai_through_openrouter_when_missing_key(
    monkeypatch, model_name, expected_openrouter_name
):
    config = Config(openrouter_api_key="sk-or-test", ai_mode=AIMode.STANDARD)
    monkeypatch.setattr(model_config, "get_config", lambda: config)
    monkeypatch.setattr(model_config, "ai_settings", _StubSettings(model_name))

    captured = {}

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(**kwargs)

    def fake_chat_anthropic(**_kwargs):
        raise AssertionError("ChatAnthropic should never be used for OpenAI models")

    monkeypatch.setattr(model_config, "ChatOpenAI", fake_chat_openai)
    monkeypatch.setattr(model_config, "ChatAnthropic", fake_chat_anthropic)

    ModelSelector.get_llm(AgentRole.SUMMARIZER)

    assert captured["model"] == expected_openrouter_name
    assert captured["api_key"] == "sk-or-test"
    assert captured["base_url"] == OPENROUTER_BASE_URL
    assert "use_responses_api" not in captured


@pytest.mark.parametrize("model_name", ["gpt-5", "gpt-5-mini"])
def test_openai_responses_params_stripped_for_openrouter(monkeypatch, model_name):
    config = Config(openrouter_api_key="sk-or-test", ai_mode=AIMode.STANDARD)
    monkeypatch.setattr(model_config, "get_config", lambda: config)
    monkeypatch.setattr(model_config, "ai_settings", _StubSettings(model_name))

    captured = {}

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(**kwargs)

    def fake_chat_anthropic(**_kwargs):
        raise AssertionError("ChatAnthropic should never be used for OpenAI models")

    monkeypatch.setattr(model_config, "ChatOpenAI", fake_chat_openai)
    monkeypatch.setattr(model_config, "ChatAnthropic", fake_chat_anthropic)

    ModelSelector.get_llm(AgentRole.SUMMARIZER)

    assert captured["base_url"] == OPENROUTER_BASE_URL
    assert "use_responses_api" not in captured
    assert "reasoning" not in captured
    assert "model_kwargs" not in captured


@pytest.mark.parametrize(
    ("model_name", "expected_model_name"),
    [
        ("deepseek-chat", "openrouter/deepseek/deepseek-chat"),
        ("deepseek-reasoner", "openrouter/deepseek/deepseek-r1"),
        ("deepseek-v3.2", "deepseek/deepseek-v3.2"),
        ("gemini-2.5-pro", "google/gemini-2.5-pro"),
        ("grok-4", "x-ai/grok-4"),
    ],
)
def test_native_openrouter_models_use_openrouter(monkeypatch, model_name, expected_model_name):
    config = Config(openrouter_api_key="sk-or-test", ai_mode=AIMode.STANDARD)
    monkeypatch.setattr(model_config, "get_config", lambda: config)
    monkeypatch.setattr(model_config, "ai_settings", _StubSettings(model_name))

    captured = {}

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(**kwargs)

    def fake_chat_anthropic(**_kwargs):
        raise AssertionError("ChatAnthropic should never be used for OpenRouter-native models")

    monkeypatch.setattr(model_config, "ChatOpenAI", fake_chat_openai)
    monkeypatch.setattr(model_config, "ChatAnthropic", fake_chat_anthropic)

    ModelSelector.get_llm(AgentRole.SUMMARIZER)

    assert captured["model"] == expected_model_name
    assert captured["api_key"] == "sk-or-test"
    assert captured["base_url"] == OPENROUTER_BASE_URL


@pytest.mark.parametrize(
    "model_name",
    ["deepseek-chat", "deepseek-reasoner", "gemini-2.5-pro", "grok-4"],
)
def test_native_openrouter_models_require_openrouter_key(monkeypatch, model_name):
    config = Config(ai_mode=AIMode.STANDARD)
    monkeypatch.setattr(model_config, "get_config", lambda: config)
    monkeypatch.setattr(model_config, "ai_settings", _StubSettings(model_name))

    monkeypatch.setattr(model_config, "ChatOpenAI", lambda **_kwargs: None)
    monkeypatch.setattr(model_config, "ChatAnthropic", lambda **_kwargs: None)

    with pytest.raises(RuntimeError, match="OpenRouter API key is required for OpenRouter-hosted models"):
        ModelSelector.get_llm(AgentRole.SUMMARIZER)
