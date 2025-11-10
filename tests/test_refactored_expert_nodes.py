from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from services.ai.langgraph.nodes.activity_expert_node import (
    activity_expert_node,
)
from services.ai.langgraph.nodes.metrics_expert_node import (
    metrics_expert_node,
)
from services.ai.langgraph.nodes.physiology_expert_node import (
    physiology_expert_node,
)
from services.ai.langgraph.state.training_analysis_state import TrainingAnalysisState


@pytest.mark.parametrize("node_func,state_result_key,node_name,expert_name", [
    (metrics_expert_node, "metrics_result", "metrics_expert", "Dr. Aiden Nakamura"),
    (physiology_expert_node, "physiology_result", "physiology_expert", "Dr. Kwame Osei"),
    (activity_expert_node, "activity_result", "activity_expert", "Coach Elena Petrova"),
])
class TestRefactoredExpertNodes:
    
    @pytest.mark.asyncio
    async def test_node_calls_factory_with_correct_config(
        self, node_func, state_result_key, node_name, expert_name
    ):
        initial_state: TrainingAnalysisState = {
            "messages": [],
            "user_id": "test_user",
            "athlete_name": "Test Athlete",
            "execution_id": "test_exec_123",
            "garmin_data": {},
            "metrics_summary": "Test metrics",
            "physiology_summary": "Test physiology",
            "activity_summary": "Test activity",
            "competitions": [],
            "current_date": "2024-01-15",
            "analysis_context": "Test context",
            "plotting_enabled": False,
            "hitl_enabled": False,
            "plots": [],
            "costs": [],
            "errors": []
        }

        module_path = node_func.__module__
        with patch(f"{module_path}.create_expert_subgraph") as mock_factory:
            mock_subgraph = MagicMock()
            
            async def mock_ainvoke(state, config):
                return {
                    **state,
                    "messages": state["messages"] + [
                        AIMessage(content="Analysis complete")
                    ]
                }
            
            mock_subgraph.ainvoke = AsyncMock(side_effect=mock_ainvoke)
            mock_factory.return_value = mock_subgraph

            result = await node_func(initial_state)

            mock_factory.assert_called_once()
            call_args = mock_factory.call_args
            config_arg = call_args[0][0]
            
            assert config_arg.node_name == node_name
            assert config_arg.state_result_key == state_result_key
            assert state_result_key in result
            assert "costs" in result
            assert "plots" in result

    @pytest.mark.asyncio
    async def test_node_passes_correct_prompts_to_subgraph(
        self, node_func, state_result_key, node_name, expert_name
    ):
        initial_state: TrainingAnalysisState = {
            "messages": [],
            "user_id": "test_user",
            "athlete_name": "Test Athlete",
            "execution_id": "test_exec_456",
            "garmin_data": {},
            "metrics_summary": "Metrics data",
            "physiology_summary": "Physiology data",
            "activity_summary": "Activity data",
            "competitions": [],
            "current_date": "2024-01-15",
            "analysis_context": "Context",
            "plotting_enabled": False,
            "hitl_enabled": True,
            "plots": [],
            "costs": [],
            "errors": []
        }

        module_path = node_func.__module__
        with patch(f"{module_path}.create_expert_subgraph") as mock_factory:
            mock_subgraph = MagicMock()
            captured_state = None
            
            async def mock_ainvoke(state, config):
                nonlocal captured_state
                captured_state = state
                return {
                    **state,
                    "messages": state["messages"] + [AIMessage(content="Done")]
                }
            
            mock_subgraph.ainvoke = AsyncMock(side_effect=mock_ainvoke)
            mock_factory.return_value = mock_subgraph

            await node_func(initial_state)

            assert captured_state is not None
            assert len(captured_state["messages"]) == 2
            assert expert_name in captured_state["messages"][0].content
            assert "Analyze" in captured_state["messages"][1].content

    @pytest.mark.asyncio
    async def test_node_respects_plotting_enabled_flag(
        self, node_func, state_result_key, node_name, expert_name
    ):
        initial_state: TrainingAnalysisState = {
            "messages": [],
            "user_id": "test_user",
            "athlete_name": "Test Athlete",
            "execution_id": "test_exec_789",
            "garmin_data": {},
            "metrics_summary": "Metrics",
            "physiology_summary": "Physiology",
            "activity_summary": "Activity",
            "competitions": [],
            "current_date": "2024-01-15",
            "analysis_context": "Context",
            "plotting_enabled": True,
            "hitl_enabled": False,
            "plots": [],
            "costs": [],
            "errors": []
        }

        module_path = node_func.__module__
        with patch(f"{module_path}.create_expert_subgraph") as mock_factory:
            mock_subgraph = MagicMock()
            
            async def mock_ainvoke(state, config):
                return {
                    **state,
                    "messages": state["messages"] + [AIMessage(content="Done")]
                }
            
            mock_subgraph.ainvoke = AsyncMock(side_effect=mock_ainvoke)
            mock_factory.return_value = mock_subgraph

            await node_func(initial_state)

            call_args = mock_factory.call_args
            config_arg = call_args[0][0]
            plot_storage_arg = call_args[0][1] if len(call_args[0]) > 1 else None
            
            assert config_arg.plotting_enabled is True
            assert plot_storage_arg is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])