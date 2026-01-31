import os
from unittest.mock import patch

import pytest
from langchain_openai import ChatOpenAI

from core.config import reload_config
from services.ai.ai_settings import AgentRole, ai_settings
from services.ai.model_config import ModelSelector


@pytest.fixture
def azure_env_vars():
    return {
        "AZURE_OPENAI_API_KEY": "test-azure-api-key",
        "AZURE_OPENAI_ENDPOINT": "https://test-resource.openai.azure.com",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "gpt-4o-test-deployment",
        "AI_MODE": "standard",
    }


@pytest.fixture
def clean_env():
    yield
    reload_config()
    ai_settings.reload()


def test_azure_openai_v1_instantiation(azure_env_vars, clean_env):
    with patch.dict(os.environ, azure_env_vars, clear=False):
        reload_config()
        ai_settings.reload()

        llm = ModelSelector.get_llm(AgentRole.SUMMARIZER)

        assert isinstance(llm, ChatOpenAI), f"Expected ChatOpenAI (Azure v1 mode), got {type(llm)}"
        assert llm.model_name == azure_env_vars["AZURE_OPENAI_DEPLOYMENT_NAME"]
        assert llm.openai_api_base is not None
        assert azure_env_vars["AZURE_OPENAI_ENDPOINT"] in llm.openai_api_base
        assert "/openai/v1/" in llm.openai_api_base


def test_azure_openai_takes_precedence(azure_env_vars, clean_env):
    env_with_openai = {
        **azure_env_vars,
        "OPENAI_API_KEY": "sk-standard-openai-key",
    }

    with patch.dict(os.environ, env_with_openai, clear=False):
        reload_config()
        ai_settings.reload()

        llm = ModelSelector.get_llm(AgentRole.SUMMARIZER)

        assert isinstance(llm, ChatOpenAI), "Azure should take precedence when AZURE_OPENAI_ENDPOINT is set"
        assert llm.openai_api_base is not None
        assert "/openai/v1/" in llm.openai_api_base


def test_azure_missing_api_key(azure_env_vars, clean_env):
    incomplete_env = {
        "AZURE_OPENAI_ENDPOINT": azure_env_vars["AZURE_OPENAI_ENDPOINT"],
        "AZURE_OPENAI_DEPLOYMENT_NAME": azure_env_vars["AZURE_OPENAI_DEPLOYMENT_NAME"],
    }

    with patch.dict(os.environ, incomplete_env, clear=True):
        reload_config()

        with pytest.raises(RuntimeError, match="AZURE_OPENAI_API_KEY is required"):
            ModelSelector.get_llm(AgentRole.SUMMARIZER)


def test_azure_missing_deployment_name(azure_env_vars, clean_env):
    incomplete_env = {
        "AZURE_OPENAI_ENDPOINT": azure_env_vars["AZURE_OPENAI_ENDPOINT"],
        "AZURE_OPENAI_API_KEY": azure_env_vars["AZURE_OPENAI_API_KEY"],
    }

    with patch.dict(os.environ, incomplete_env, clear=True):
        reload_config()

        with pytest.raises(RuntimeError, match="AZURE_OPENAI_DEPLOYMENT_NAME is required"):
            ModelSelector.get_llm(AgentRole.SUMMARIZER)


def test_azure_endpoint_normalization(azure_env_vars, clean_env):
    test_cases = [
        "https://test-resource.openai.azure.com",
        "https://test-resource.openai.azure.com/",
        "https://test-resource.openai.azure.com/openai/v1",
        "https://test-resource.openai.azure.com/openai/v1/",
    ]

    for endpoint in test_cases:
        env = {**azure_env_vars, "AZURE_OPENAI_ENDPOINT": endpoint}
        with patch.dict(os.environ, env, clear=True):
            reload_config()
            ai_settings.reload()
            llm = ModelSelector.get_llm(AgentRole.SUMMARIZER)

            assert isinstance(llm, ChatOpenAI)
            assert llm.openai_api_base is not None
            assert llm.openai_api_base.endswith("/openai/v1/")
            assert llm.openai_api_base.count("/openai/v1/") == 1
