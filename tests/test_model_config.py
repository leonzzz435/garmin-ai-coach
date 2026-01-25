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
    ("model_name", "api_key_field", "expected_client"),
    [
        ("claude-4", "anthropic_api_key", "ChatAnthropic"),
        ("gpt-4o", "openai_api_key", "ChatOpenAI"),
    ],
)
def test_prefers_direct_api_when_key_available(
    monkeypatch, model_name, api_key_field, expected_client
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
    from typing import Any, cast

    config = Config(**cast("dict[str, Any]", config_dict))
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

    assert captured["api_key"] == api_key_values[api_key_field]
    assert captured["client"] == expected_client
    if expected_client == "ChatOpenAI":
        assert captured["base_url"] == "https://api.openai.com/v1"


def test_routes_anthropic_through_openrouter_when_missing_key(monkeypatch):
    config = Config(openrouter_api_key="sk-or-test", ai_mode=AIMode.STANDARD)
    monkeypatch.setattr(model_config, "get_config", lambda: config)
    monkeypatch.setattr(model_config, "ai_settings", _StubSettings("claude-4"))

    captured = {}

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(**kwargs)

    def fake_chat_anthropic(**_kwargs):
        raise AssertionError("ChatAnthropic should not be used when routing via OpenRouter")

    monkeypatch.setattr(model_config, "ChatOpenAI", fake_chat_openai)
    monkeypatch.setattr(model_config, "ChatAnthropic", fake_chat_anthropic)

    ModelSelector.get_llm(AgentRole.SUMMARIZER)

    assert captured["api_key"] == "sk-or-test"
    assert captured["base_url"] == OPENROUTER_BASE_URL
    assert "thinking" not in captured


def test_routes_openai_through_openrouter_when_missing_key(monkeypatch):
    config = Config(openrouter_api_key="sk-or-test", ai_mode=AIMode.STANDARD)
    monkeypatch.setattr(model_config, "get_config", lambda: config)
    monkeypatch.setattr(model_config, "ai_settings", _StubSettings("gpt-4o"))

    captured = {}

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(**kwargs)

    def fake_chat_anthropic(**_kwargs):
        raise AssertionError("ChatAnthropic should never be used for OpenAI models")

    monkeypatch.setattr(model_config, "ChatOpenAI", fake_chat_openai)
    monkeypatch.setattr(model_config, "ChatAnthropic", fake_chat_anthropic)

    ModelSelector.get_llm(AgentRole.SUMMARIZER)

    assert captured["api_key"] == "sk-or-test"
    assert captured["base_url"] == OPENROUTER_BASE_URL


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


def test_native_openrouter_model_uses_openrouter(monkeypatch):
    config = Config(openrouter_api_key="sk-or-test", ai_mode=AIMode.STANDARD)
    monkeypatch.setattr(model_config, "get_config", lambda: config)
    monkeypatch.setattr(model_config, "ai_settings", _StubSettings("deepseek-chat"))

    captured = {}

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(**kwargs)

    def fake_chat_anthropic(**_kwargs):
        raise AssertionError("ChatAnthropic should never be used for OpenRouter-native models")

    monkeypatch.setattr(model_config, "ChatOpenAI", fake_chat_openai)
    monkeypatch.setattr(model_config, "ChatAnthropic", fake_chat_anthropic)

    ModelSelector.get_llm(AgentRole.SUMMARIZER)

    assert captured["api_key"] == "sk-or-test"
    assert captured["base_url"] == OPENROUTER_BASE_URL


def test_native_openrouter_model_requires_openrouter_key(monkeypatch):
    config = Config(ai_mode=AIMode.STANDARD)
    monkeypatch.setattr(model_config, "get_config", lambda: config)
    monkeypatch.setattr(model_config, "ai_settings", _StubSettings("deepseek-chat"))

    monkeypatch.setattr(model_config, "ChatOpenAI", lambda **_kwargs: None)
    monkeypatch.setattr(model_config, "ChatAnthropic", lambda **_kwargs: None)

    with pytest.raises(RuntimeError, match="OpenRouter API key is required"):
        ModelSelector.get_llm(AgentRole.SUMMARIZER)


def test_missing_both_direct_and_openrouter_keys_raises(monkeypatch):
    config = Config(ai_mode=AIMode.STANDARD)
    monkeypatch.setattr(model_config, "get_config", lambda: config)
    monkeypatch.setattr(model_config, "ai_settings", _StubSettings("claude-4"))

    monkeypatch.setattr(model_config, "ChatOpenAI", lambda **_kwargs: None)
    monkeypatch.setattr(model_config, "ChatAnthropic", lambda **_kwargs: None)

    with pytest.raises(RuntimeError, match="API key"):
        ModelSelector.get_llm(AgentRole.SUMMARIZER)
