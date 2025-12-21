import types

import pytest

from core.config import AIMode, Config
from services.ai import model_config
from services.ai.ai_settings import AgentRole
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


@pytest.mark.parametrize(
    ("model_name", "expected_openrouter_name"),
    [
        ("gpt-4.1", "openai/gpt-4.1"),
        ("gpt-4o", "openai/gpt-4o"),
        ("gpt-4o-mini", "openai/gpt-4o-mini"),
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
    assert captured["base_url"] == "https://openrouter.ai/api/v1"
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

    assert captured["base_url"] == "https://openrouter.ai/api/v1"
    assert "use_responses_api" not in captured
    assert "reasoning" not in captured
    assert "model_kwargs" not in captured


@pytest.mark.parametrize("model_name", ["gpt-4.5", "o1", "o1-mini"])
def test_openai_model_without_openrouter_alias_requires_openai_key(monkeypatch, model_name):
    config = Config(openrouter_api_key="sk-or-test", ai_mode=AIMode.STANDARD)
    monkeypatch.setattr(model_config, "get_config", lambda: config)
    monkeypatch.setattr(model_config, "ai_settings", _StubSettings(model_name))

    monkeypatch.setattr(model_config, "ChatOpenAI", lambda **_kwargs: None)
    monkeypatch.setattr(model_config, "ChatAnthropic", lambda **_kwargs: None)

    with pytest.raises(RuntimeError, match="not available via OpenRouter"):
        ModelSelector.get_llm(AgentRole.SUMMARIZER)
