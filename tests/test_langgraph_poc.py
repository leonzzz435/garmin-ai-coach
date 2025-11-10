"""Minimal tests for LangGraph proof of concept."""

from unittest.mock import patch

import pytest

from services.ai.langgraph.state.training_analysis_state import create_initial_state
from services.ai.langgraph.workflows.analysis_workflow import create_analysis_workflow


@pytest.fixture
def sample_garmin_data():
    return {
        "training_load_history": [{"date": "2024-01-01", "load": 150}],
        "vo2_max_history": [{"date": "2024-01-01", "vo2_max": 45.2}],
        "training_status": {"status": "productive"},
    }


@pytest.fixture
def sample_state(sample_garmin_data):
    return create_initial_state(
        user_id="test_user",
        athlete_name="Test Athlete",
        garmin_data=sample_garmin_data,
        execution_id="test_exec_123",
        plotting_enabled=True
    )


def test_state_creation(sample_garmin_data):
    state = create_initial_state(
        user_id="user123",
        athlete_name="John Doe",
        garmin_data=sample_garmin_data,
        execution_id="exec_123",
    )

    assert state["user_id"] == "user123"
    assert state["athlete_name"] == "John Doe"
    assert state["garmin_data"] == sample_garmin_data
    assert state["metrics_result"] is None
    assert state["plots"] == []


@patch("services.ai.langgraph.config.langsmith_config.LangSmithConfig.setup_langsmith")
def test_workflow_creation(mock_langsmith):
    assert create_analysis_workflow() is not None
    mock_langsmith.assert_called_once()
