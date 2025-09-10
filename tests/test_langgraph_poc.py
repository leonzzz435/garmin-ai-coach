"""Minimal tests for LangGraph proof of concept."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from services.ai.langgraph.nodes.metrics_node import metrics_node
from services.ai.langgraph.state.training_analysis_state import create_initial_state
from services.ai.langgraph.workflows.analysis_workflow import create_analysis_workflow


@pytest.fixture
def sample_garmin_data():
    return {
        'training_load_history': [{'date': '2024-01-01', 'load': 150}],
        'vo2_max_history': [{'date': '2024-01-01', 'vo2_max': 45.2}],
        'training_status': {'status': 'productive'},
    }


@pytest.fixture
def sample_state(sample_garmin_data):
    return create_initial_state(
        user_id="test_user",
        athlete_name="Test Athlete",
        garmin_data=sample_garmin_data,
        execution_id="test_exec_123",
    )


def test_state_creation(sample_garmin_data):
    state = create_initial_state(
        user_id="user123",
        athlete_name="John Doe",
        garmin_data=sample_garmin_data,
        execution_id="exec_123",
    )

    assert state['user_id'] == "user123"
    assert state['athlete_name'] == "John Doe"
    assert state['garmin_data'] == sample_garmin_data
    assert state['metrics_result'] is None
    assert state['plots'] == []


@patch('services.ai.langgraph.config.langsmith_config.LangSmithConfig.setup_langsmith')
def test_workflow_creation(mock_langsmith):
    workflow_app = create_analysis_workflow()

    assert workflow_app is not None
    mock_langsmith.assert_called_once()


@pytest.mark.asyncio
@patch('services.ai.model_config.ModelSelector.get_llm')
@patch('services.ai.tools.plotting.PlotStorage')
@patch('services.ai.utils.retry_handler.retry_with_backoff', new_callable=AsyncMock)
async def test_metrics_node_basic(mock_retry, mock_plot_storage, mock_get_llm, sample_state):
    mock_llm = Mock()
    mock_llm_with_tools = Mock()

    mock_response = Mock()
    mock_response.content = "Test analysis result"
    mock_response.tool_calls = []  # No tool calls, so we get the direct response
    mock_llm_with_tools.ainvoke = AsyncMock(return_value=mock_response)

    mock_llm.bind_tools.return_value = mock_llm_with_tools
    mock_get_llm.return_value = mock_llm

    mock_retry.return_value = "Test analysis result"

    mock_storage = Mock()
    mock_storage.get_all_plots.return_value = {}
    mock_plot_storage.return_value = mock_storage

    result = await metrics_node(sample_state)

    assert 'metrics_result' in result
    assert 'plots' in result
    assert 'costs' in result
    assert result['metrics_result'] == "Test analysis result"

    mock_llm.bind_tools.assert_called_once()
    mock_get_llm.assert_called_once()


def test_poc_imports():

    assert True
