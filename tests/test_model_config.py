import types

import pytest

from core.config import AIMode, Config
from services.ai.ai_settings import AgentRole
import services.ai.model_config as model_config
from services.ai.model_config import ModelSelector


class _StubSettings:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def get_model_for_role(self, _: AgentRole) -> str:
        return self.model_name


def test_prefers_direct_anthropic_when_key_available(monkeypatch):
    config = Config(
        anthropic_api_key="sk-ant-api03-test",
        openrouter_api_key="sk-or-test",
        ai_mode=AIMode.STANDARD,
    )
    monkeypatch.setattr(model_config, "get_config", lambda: config)
    monkeypatch.setattr(model_config, "ai_settings", _StubSettings("claude-4"))

    captured = {}

    def fake_chat_anthropic(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(**kwargs)

    def fake_chat_openai(**_kwargs):
        raise AssertionError("ChatOpenAI should not be used when Anthropic key is present")

    monkeypatch.setattr(model_config, "ChatAnthropic", fake_chat_anthropic)
    monkeypatch.setattr(model_config, "ChatOpenAI", fake_chat_openai)

    ModelSelector.get_llm(AgentRole.SUMMARIZER)

    assert captured["model"] == "claude-sonnet-4-5-20250929"
    assert captured["api_key"] == "sk-ant-api03-test"
    assert "base_url" not in captured


def test_routes_anthropic_through_openrouter_when_missing_key(monkeypatch):
    config = Config(openrouter_api_key="sk-or-test", ai_mode=AIMode.STANDARD)
    monkeypatch.setattr(model_config, "get_config", lambda: config)
    monkeypatch.setattr(model_config, "ai_settings", _StubSettings("claude-4-thinking"))

    captured = {}

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(**kwargs)

    def fake_chat_anthropic(**_kwargs):
        raise AssertionError("ChatAnthropic should not be used when routing via OpenRouter")

    monkeypatch.setattr(model_config, "ChatOpenAI", fake_chat_openai)
    monkeypatch.setattr(model_config, "ChatAnthropic", fake_chat_anthropic)

    ModelSelector.get_llm(AgentRole.SUMMARIZER)

    assert captured["model"] == "anthropic/claude-sonnet-4.5"
    assert captured["api_key"] == "sk-or-test"
    assert captured["base_url"] == "https://openrouter.ai/api/v1"
    assert "thinking" not in captured
    assert "use_responses_api" not in captured


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

    assert captured["model"] == "openai/gpt-4o"
    assert captured["api_key"] == "sk-or-test"
    assert captured["base_url"] == "https://openrouter.ai/api/v1"
    assert "use_responses_api" not in captured


def test_routes_openai_gpt5_through_openrouter_and_strips_responses_api(monkeypatch):
    config = Config(openrouter_api_key="sk-or-test", ai_mode=AIMode.STANDARD)
    monkeypatch.setattr(model_config, "get_config", lambda: config)
    monkeypatch.setattr(model_config, "ai_settings", _StubSettings("gpt-5"))

    captured = {}

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        return types.SimpleNamespace(**kwargs)

    def fake_chat_anthropic(**_kwargs):
        raise AssertionError("ChatAnthropic should never be used for OpenAI models")

    monkeypatch.setattr(model_config, "ChatOpenAI", fake_chat_openai)
    monkeypatch.setattr(model_config, "ChatAnthropic", fake_chat_anthropic)

    ModelSelector.get_llm(AgentRole.SUMMARIZER)

    assert captured["model"] == "openai/gpt-5.1"
    assert captured["api_key"] == "sk-or-test"
    assert captured["base_url"] == "https://openrouter.ai/api/v1"
    assert "use_responses_api" not in captured


def test_openai_model_without_openrouter_alias_requires_openai_key(monkeypatch):
    config = Config(openrouter_api_key="sk-or-test", ai_mode=AIMode.STANDARD)
    monkeypatch.setattr(model_config, "get_config", lambda: config)
    monkeypatch.setattr(model_config, "ai_settings", _StubSettings("gpt-4.5"))

    monkeypatch.setattr(model_config, "ChatOpenAI", lambda **_kwargs: None)
    monkeypatch.setattr(model_config, "ChatAnthropic", lambda **_kwargs: None)

    with pytest.raises(RuntimeError, match="not available via OpenRouter"):
        ModelSelector.get_llm(AgentRole.SUMMARIZER)
