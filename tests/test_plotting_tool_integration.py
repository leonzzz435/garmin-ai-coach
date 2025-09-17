import pytest

from services.ai.tools.plotting.langgraph_plotting_tool import create_plotting_tools
from services.ai.tools.plotting.plot_storage import PlotStorage


class TestPlottingToolIntegration:

    def test_langchain_tool_creation(self):
        plot_storage = PlotStorage("test_execution")

        plotting_tool = create_plotting_tools(plot_storage, agent_name="test")

        assert plotting_tool.name == "python_plotting_tool"

        assert "Execute complete Python code" in plotting_tool.description

    @pytest.mark.asyncio
    async def test_tool_invocation(self):
        """Test that tools can be invoked directly."""
        plot_storage = PlotStorage("test_execution")
        plotting_tool = create_plotting_tools(plot_storage, agent_name="test")

        test_code = """
import plotly.graph_objects as go
fig = go.Figure()
fig.add_trace(go.Scatter(x=[1, 2, 3], y=[4, 5, 6], name='Test Data'))
fig.update_layout(title='Test Plot')
"""

        result = await plotting_tool.ainvoke(
            {"python_code": test_code, "description": "Test plot for integration"}
        )

        assert "Plot created successfully" in result
        assert "[PLOT:" in result

    @pytest.mark.asyncio
    async def test_model_tool_binding(self):
        from services.ai.ai_settings import AgentRole
        from services.ai.model_config import ModelSelector

        plot_storage = PlotStorage("test_execution")
        plotting_tool = create_plotting_tools(plot_storage, agent_name="test")

        llm = ModelSelector.get_llm(AgentRole.METRICS)
        llm_with_tools = llm.bind_tools([plotting_tool])

        assert hasattr(llm_with_tools, 'kwargs') and 'tools' in llm_with_tools.kwargs
        assert len(llm_with_tools.kwargs['tools']) == 1
        assert plotting_tool.name == 'python_plotting_tool'

    def test_tools_condition_compatibility(self):
        from langchain_core.messages import AIMessage
        from langgraph.prebuilt import tools_condition

        message_without_tools = AIMessage(content="This is a regular response")

        result = tools_condition({"messages": [message_without_tools]})
        assert result == "__end__"

        message_with_tools = AIMessage(
            content="I'll create a plot for you",
            tool_calls=[
                {
                    "name": "python_plotting_tool",
                    "args": {"python_code": "test", "description": "test"},
                    "id": "test_id",
                }
            ],
        )

        result = tools_condition({"messages": [message_with_tools]})
        assert result == "tools"

    def test_canonical_pattern_components(self):
        from langgraph.graph import StateGraph
        from langgraph.prebuilt import ToolNode

        plot_storage = PlotStorage("test_execution")
        plotting_tool = create_plotting_tools(plot_storage, "test")
        tools = [plotting_tool]

        tool_node = ToolNode(tools)
        assert tool_node is not None

        from services.ai.langgraph.state.training_analysis_state import TrainingAnalysisState

        workflow = StateGraph(TrainingAnalysisState)
        assert workflow is not None

        assert True  # If we get here, all components are available


if __name__ == "__main__":
    pytest.main([__file__])
