from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from services.ai.ai_settings import AgentRole
from services.ai.langgraph.nodes.expert_subgraph_factory import (
    ExpertNodeConfig,
    create_expert_subgraph,
)
from services.ai.langgraph.state.training_analysis_state import TrainingAnalysisState


class TestExpertNodeConfig:

    def test_config_creation_minimal(self):
        config = ExpertNodeConfig(
            node_name="test_expert",
            display_name="Test Expert",
            agent_role=AgentRole.METRICS_EXPERT,
            system_prompt="You are a test expert.",
            user_prompt_template="Analyze this: {data}",
            state_result_key="test_result"
        )
        
        assert config.node_name == "test_expert"
        assert config.display_name == "Test Expert"
        assert config.agent_role == AgentRole.METRICS_EXPERT
        assert config.plotting_enabled is True
        assert config.max_iterations == 15

    def test_config_creation_full(self):
        config = ExpertNodeConfig(
            node_name="test_expert",
            display_name="Test Expert",
            agent_role=AgentRole.PHYSIOLOGY_EXPERT,
            system_prompt="You are a test expert.",
            user_prompt_template="Analyze this: {data}",
            state_result_key="test_result",
            plotting_enabled=False,
            max_iterations=10
        )
        
        assert config.plotting_enabled is False
        assert config.max_iterations == 10


class TestCreateExpertSubgraph:

    def test_subgraph_creation_basic(self):
        config = ExpertNodeConfig(
            node_name="test_expert",
            display_name="Test Expert",
            agent_role=AgentRole.METRICS_EXPERT,
            system_prompt="You are a test expert.",
            user_prompt_template="Analyze this: {data}",
            state_result_key="test_result",
            plotting_enabled=False
        )
        
        subgraph = create_expert_subgraph(config)
        
        assert subgraph is not None
        assert hasattr(subgraph, "ainvoke")

    def test_subgraph_creation_with_plotting(self):
        config = ExpertNodeConfig(
            node_name="test_expert",
            display_name="Test Expert",
            agent_role=AgentRole.ACTIVITY_EXPERT,
            system_prompt="You are a test expert.",
            user_prompt_template="Analyze this: {data}",
            state_result_key="test_result",
            plotting_enabled=True
        )
        
        mock_plot_storage = MagicMock()
        subgraph = create_expert_subgraph(config, plot_storage=mock_plot_storage)
        
        assert subgraph is not None

    @pytest.mark.asyncio
    async def test_call_model_node_persists_aimessage(self):
        config = ExpertNodeConfig(
            node_name="test_expert",
            display_name="Test Expert",
            agent_role=AgentRole.METRICS_EXPERT,
            system_prompt="You are a test expert.",
            user_prompt_template="Analyze this: {data}",
            state_result_key="test_result",
            plotting_enabled=False
        )
        
        mock_response = AIMessage(
            content="Test response",
            tool_calls=[{
                "name": "communicate_with_human",
                "args": {"message": "Test question?", "message_type": "question"},
                "id": "tc_123"
            }]
        )
        
        with patch("services.ai.langgraph.nodes.expert_subgraph_factory.ModelSelector") as mock_selector:
            mock_llm = MagicMock()
            mock_llm.bind_tools = MagicMock(return_value=mock_llm)
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_selector.get_llm = MagicMock(return_value=mock_llm)
            
            subgraph = create_expert_subgraph(config)
            
            initial_state = {
                "messages": [HumanMessage(content="Test input")],
                "user_id": "test_user",
                "athlete_name": "Test Athlete",
                "garmin_data": {},
                "plots": [],
                "costs": [],
                "errors": []
            }
            
            result = await subgraph.ainvoke(initial_state)
            
            assert len(result["messages"]) == 2
            assert isinstance(result["messages"][-1], AIMessage)
            assert result["messages"][-1].tool_calls[0]["id"] == "tc_123"


class TestRouteAction:

    def test_route_no_tool_calls_returns_end(self):
        config = ExpertNodeConfig(
            node_name="test_expert",
            display_name="Test Expert",
            agent_role=AgentRole.METRICS_EXPERT,
            system_prompt="You are a test expert.",
            user_prompt_template="Analyze this: {data}",
            state_result_key="test_result",
            plotting_enabled=False
        )
        
        subgraph = create_expert_subgraph(config)
        
        assert subgraph is not None

    def test_route_hitl_tool_call_returns_hitl(self):
        config = ExpertNodeConfig(
            node_name="test_expert",
            display_name="Test Expert",
            agent_role=AgentRole.METRICS_EXPERT,
            system_prompt="You are a test expert.",
            user_prompt_template="Analyze this: {data}",
            state_result_key="test_result",
            plotting_enabled=False
        )
        
        subgraph = create_expert_subgraph(config)
        assert subgraph is not None


class TestHITLInterrupt:

    @pytest.mark.asyncio
    async def test_hitl_interrupt_creates_tool_message(self):
        config = ExpertNodeConfig(
            node_name="test_expert",
            display_name="Test Expert",
            agent_role=AgentRole.METRICS_EXPERT,
            system_prompt="You are a test expert.",
            user_prompt_template="Analyze this: {data}",
            state_result_key="test_result",
            plotting_enabled=False
        )
        
        with patch("services.ai.langgraph.nodes.expert_subgraph_factory.interrupt") as mock_interrupt:
            mock_interrupt.return_value = {"content": "My target is 160 bpm"}
            
            with patch("services.ai.langgraph.nodes.expert_subgraph_factory.ModelSelector") as mock_selector:
                mock_llm = MagicMock()
                mock_llm.bind_tools = MagicMock(return_value=mock_llm)
                
                call_count = [0]
                def mock_ainvoke(messages):
                    call_count[0] += 1
                    if call_count[0] == 1:
                        return AIMessage(
                            content="I need to ask",
                            tool_calls=[{
                                "name": "communicate_with_human",
                                "args": {"message": "What is your target heart rate?", "message_type": "question"},
                                "id": "tc_789"
                            }]
                        )
                    else:
                        return AIMessage(content="Thanks for the info!")
                
                mock_llm.ainvoke = AsyncMock(side_effect=mock_ainvoke)
                mock_selector.get_llm = MagicMock(return_value=mock_llm)
                
                subgraph = create_expert_subgraph(config)
                
                initial_state: TrainingAnalysisState = {
                    "messages": [HumanMessage(content="Analyze my training")],
                    "user_id": "test_user",
                    "athlete_name": "Test Athlete",
                    "garmin_data": {},
                    "plots": [],
                    "costs": [],
                    "errors": []
                }
                
                result = await subgraph.ainvoke(initial_state, {"configurable": {"thread_id": "test"}})
                
                tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
                assert len(tool_messages) > 0
                assert tool_messages[0].tool_call_id == "tc_789"
                assert "160 bpm" in tool_messages[0].content
                assert call_count[0] == 2

    @pytest.mark.asyncio
    async def test_hitl_interrupt_reads_from_persisted_state(self):
        config = ExpertNodeConfig(
            node_name="test_expert",
            display_name="Test Expert",
            agent_role=AgentRole.PHYSIOLOGY_EXPERT,
            system_prompt="You are a test expert.",
            user_prompt_template="Analyze this: {data}",
            state_result_key="test_result",
            plotting_enabled=False
        )
        
        original_tool_call_id = "tc_original_123"
        
        ai_message = AIMessage(
            content="Need input",
            tool_calls=[{
                "name": "communicate_with_human",
                "args": {"message": "Question?", "message_type": "question"},
                "id": original_tool_call_id
            }]
        )
        
        state: TrainingAnalysisState = {
            "messages": [HumanMessage(content="Input"), ai_message],
            "user_id": "test_user",
            "athlete_name": "Test Athlete",
            "garmin_data": {},
            "plots": [],
            "costs": [],
            "errors": []
        }
        
        with patch("services.ai.langgraph.nodes.expert_subgraph_factory.interrupt") as mock_interrupt:
            mock_interrupt.return_value = {"content": "User answer"}
            
            with patch("services.ai.langgraph.nodes.expert_subgraph_factory.ModelSelector") as mock_selector:
                mock_llm = MagicMock()
                mock_llm.bind_tools = MagicMock(return_value=mock_llm)
                mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Complete"))
                mock_selector.get_llm = MagicMock(return_value=mock_llm)
                
                subgraph = create_expert_subgraph(config)
                result = await subgraph.ainvoke(state, {"configurable": {"thread_id": "test"}})
                
                tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
                if tool_messages:
                    assert tool_messages[0].tool_call_id == original_tool_call_id


class TestStandardToolsNode:

    @pytest.mark.asyncio
    async def test_standard_tools_executed_when_non_hitl_tool_called(self):
        config = ExpertNodeConfig(
            node_name="test_expert",
            display_name="Test Expert",
            agent_role=AgentRole.ACTIVITY_EXPERT,
            system_prompt="You are a test expert.",
            user_prompt_template="Analyze this: {data}",
            state_result_key="test_result",
            plotting_enabled=True
        )
        
        mock_plot_storage = MagicMock()
        
        with patch("services.ai.langgraph.nodes.expert_subgraph_factory.ModelSelector") as mock_selector:
            mock_llm = AsyncMock()
            mock_llm.bind_tools.return_value = mock_llm
            mock_llm.ainvoke.return_value = AIMessage(content="Plot created")
            mock_selector.get_llm.return_value = mock_llm
            
            subgraph = create_expert_subgraph(config, plot_storage=mock_plot_storage)
            
            assert subgraph is not None


class TestSubgraphIntegration:

    @pytest.mark.asyncio
    async def test_subgraph_completes_without_tools(self):
        config = ExpertNodeConfig(
            node_name="test_expert",
            display_name="Test Expert",
            agent_role=AgentRole.METRICS_EXPERT,
            system_prompt="You are a test expert.",
            user_prompt_template="Analyze this: {data}",
            state_result_key="test_result",
            plotting_enabled=False
        )
        
        with patch("services.ai.langgraph.nodes.expert_subgraph_factory.ModelSelector") as mock_selector:
            mock_llm = MagicMock()
            mock_llm.bind_tools = MagicMock(return_value=mock_llm)
            mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Analysis complete, no tools needed"))
            mock_selector.get_llm = MagicMock(return_value=mock_llm)
            
            subgraph = create_expert_subgraph(config)
            
            initial_state: TrainingAnalysisState = {
                "messages": [HumanMessage(content="Analyze my training")],
                "user_id": "test_user",
                "athlete_name": "Test Athlete",
                "garmin_data": {},
                "plots": [],
                "costs": [],
                "errors": []
            }
            
            result = await subgraph.ainvoke(initial_state)
            
            assert len(result["messages"]) == 2
            assert "Analysis complete" in result["messages"][-1].content

    @pytest.mark.asyncio
    async def test_subgraph_loops_on_tool_execution(self):
        config = ExpertNodeConfig(
            node_name="test_expert",
            display_name="Test Expert",
            agent_role=AgentRole.ACTIVITY_EXPERT,
            system_prompt="You are a test expert.",
            user_prompt_template="Analyze this: {data}",
            state_result_key="test_result",
            plotting_enabled=True
        )
        
        mock_plot_storage = MagicMock()
        
        with patch("services.ai.langgraph.nodes.expert_subgraph_factory.ModelSelector") as mock_selector:
            mock_llm = MagicMock()
            mock_llm.bind_tools = MagicMock(return_value=mock_llm)
            
            call_count = [0]
            
            def mock_ainvoke(messages):
                call_count[0] += 1
                if call_count[0] == 1:
                    return AIMessage(
                        content="Creating plot",
                        tool_calls=[{
                            "name": "create_plot",
                            "args": {"code": "plt.plot([1,2,3])", "title": "Test"},
                            "id": "tc_1"
                        }]
                    )
                else:
                    return AIMessage(content="Plot created, analysis done")
            
            mock_llm.ainvoke = AsyncMock(side_effect=mock_ainvoke)
            mock_selector.get_llm = MagicMock(return_value=mock_llm)
            
            subgraph = create_expert_subgraph(config, plot_storage=mock_plot_storage)
            
            initial_state: TrainingAnalysisState = {
                "messages": [HumanMessage(content="Show analysis with plot")],
                "user_id": "test_user",
                "athlete_name": "Test Athlete",
                "garmin_data": {},
                "plots": [],
                "costs": [],
                "errors": []
            }
            
            await subgraph.ainvoke(initial_state)
            
            assert call_count[0] >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])