from unittest.mock import AsyncMock, Mock, patch

import pytest

from services.ai.langgraph.state.training_analysis_state import create_initial_state


@pytest.fixture
def basic_test_state():
    return create_initial_state(
        user_id="test_user",
        athlete_name="Test Athlete",
        garmin_data={'activities': [], 'training_load_history': []},
        execution_id="test_123",
    )


def test_all_nodes_importable():
    from services.ai.langgraph.nodes.activity_data_node import activity_data_node
    from services.ai.langgraph.nodes.activity_interpreter_node import activity_interpreter_node
    from services.ai.langgraph.nodes.formatter_node import formatter_node
    from services.ai.langgraph.nodes.metrics_node import metrics_node
    from services.ai.langgraph.nodes.physiology_node import physiology_node
    from services.ai.langgraph.nodes.synthesis_node import synthesis_node

    assert callable(metrics_node)
    assert callable(physiology_node)
    assert callable(activity_data_node)
    assert callable(activity_interpreter_node)
    assert callable(synthesis_node)
    assert callable(formatter_node)


@patch("services.ai.langgraph.config.langsmith_config.LangSmithConfig.setup_langsmith")
def test_complete_workflow_creation(mock_langsmith):
    from services.ai.langgraph.workflows.analysis_workflow import create_analysis_workflow

    workflow_app = create_analysis_workflow()
    assert workflow_app is not None
    mock_langsmith.assert_called_once()


def test_state_schema_completeness():
    state = create_initial_state(
        user_id="test", athlete_name="Test", garmin_data={}, execution_id="test"
    )

    required_fields = [
        "user_id",
        "athlete_name",
        "garmin_data",
        "execution_id",
        "metrics_result",
        "activity_summary",
        "activity_result",
        "physiology_result",
        "synthesis_result",
        "analysis_html",
        "plots",
        "costs",
        "errors",
    ]

    for field in required_fields:
        assert field in state


@pytest.mark.asyncio
@patch("services.ai.model_config.ModelSelector.get_llm")
async def test_node_basic_functionality(mock_get_llm, basic_test_state):
    from services.ai.langgraph.nodes.activity_data_node import activity_data_node

    mock_llm = AsyncMock()
    mock_response = Mock()
    mock_response.content = "Test response"
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    mock_get_llm.return_value = mock_llm

    result = await activity_data_node(basic_test_state)

    assert isinstance(result, dict)
    assert "costs" in result or "errors" in result

    if "errors" not in result:
        mock_llm.ainvoke.assert_called_once()
        call_args = mock_llm.ainvoke.call_args[0][0]

        assert isinstance(call_args, list)
        for message in call_args:
            assert isinstance(message, dict)
            assert "role" in message
            assert "content" in message


def test_workflow_structure_stability():
    try:
        with patch("services.ai.langgraph.config.langsmith_config.LangSmithConfig.setup_langsmith"):
            from services.ai.langgraph.workflows.analysis_workflow import (
                create_analysis_workflow,
                create_simple_sequential_workflow,
            )

            parallel_workflow = create_analysis_workflow()
            sequential_workflow = create_simple_sequential_workflow()

            assert parallel_workflow is not None
            assert sequential_workflow is not None

    except Exception as exception:
        pytest.fail(f"Workflow creation should be stable: {exception}")
