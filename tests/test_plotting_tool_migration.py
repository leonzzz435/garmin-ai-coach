
import pytest
from services.ai.tools.plotting.framework_agnostic_plotting_tool import (
    FrameworkAgnosticPlottingTool,
    FrameworkAgnosticPlotListTool,
    PlottingInput,
    PlotResult,
)
from services.ai.tools.plotting.plot_storage import PlotStorage


class TestFrameworkAgnosticPlottingTool:
    
    def test_framework_agnostic_tool_initialization(self):
        plot_storage = PlotStorage("test_execution")
        tool = FrameworkAgnosticPlottingTool(plot_storage=plot_storage)
        
        assert tool.name == "python_plotting_tool"
        assert "Execute complete Python code" in tool.description
        assert tool.input_model == PlottingInput
        assert tool.plot_storage == plot_storage
    
    def test_successful_plot_creation(self):
        plot_storage = PlotStorage("test_execution")
        tool = FrameworkAgnosticPlottingTool(plot_storage=plot_storage)
        
        python_code = """
import plotly.graph_objects as go

fig = go.Figure()
fig.add_trace(go.Scatter(x=[1, 2, 3], y=[4, 5, 6], name='Test Data'))
fig.update_layout(title='Test Plot')
"""
        
        args = PlottingInput(
            python_code=python_code,
            description="Test plot for validation",
            agent_name="test_agent"
        )
        
        result = tool.call(args)
        
        assert isinstance(result, PlotResult)
        assert result.success == True
        assert result.plot_id is not None
        assert "Plot created successfully" in result.message
        assert f"[PLOT:{result.plot_id}]" in result.message
    
    def test_missing_python_code_error(self):
        plot_storage = PlotStorage("test_execution")
        tool = FrameworkAgnosticPlottingTool(plot_storage=plot_storage)
        
        args = PlottingInput(
            python_code=None,
            description="Test plot",
            agent_name="test_agent"
        )
        
        result = tool.call(args)
        
        assert isinstance(result, PlotResult)
        assert result.success == False
        assert result.error_type == "missing_python_code"
        assert "Missing required parameter 'python_code'" in result.message
    
    def test_missing_description_error(self):
        plot_storage = PlotStorage("test_execution")
        tool = FrameworkAgnosticPlottingTool(plot_storage=plot_storage)
        
        args = PlottingInput(
            python_code="import plotly.graph_objects as go\nfig = go.Figure()",
            description=None,
            agent_name="test_agent"
        )
        
        result = tool.call(args)
        
        assert isinstance(result, PlotResult)
        assert result.success == False
        assert result.error_type == "missing_description"
        assert "Missing required parameter 'description'" in result.message
    
    def test_plot_limit_enforcement(self):
        plot_storage = PlotStorage("test_execution")
        tool = FrameworkAgnosticPlottingTool(plot_storage=plot_storage)
        
        python_code = """
import plotly.graph_objects as go
fig = go.Figure()
fig.add_trace(go.Scatter(x=[1, 2], y=[3, 4]))
"""
        
        args1 = PlottingInput(
            python_code=python_code,
            description="First test plot",
            agent_name="test_agent"
        )
        result1 = tool.call(args1)
        assert result1.success == True
        
        args2 = PlottingInput(
            python_code=python_code,
            description="Second test plot",
            agent_name="test_agent"
        )
        result2 = tool.call(args2)
        assert result2.success == True
        
        args3 = PlottingInput(
            python_code=python_code,
            description="Third test plot",
            agent_name="test_agent"
        )
        result3 = tool.call(args3)
        assert result3.success == False
        assert result3.error_type == "plot_limit_exceeded"
        assert "Plot limit reached" in result3.message
    
    def test_invalid_python_code_error(self):
        plot_storage = PlotStorage("test_execution")
        tool = FrameworkAgnosticPlottingTool(plot_storage=plot_storage)
        
        args = PlottingInput(
            python_code="this is not valid python code !!!",
            description="Test plot with invalid code",
            agent_name="test_agent"
        )
        
        result = tool.call(args)
        
        assert isinstance(result, PlotResult)
        assert result.success == False
        assert result.error_type == "execution_error"
        assert "Error executing plotting code" in result.message


class TestFrameworkAgnosticPlotListTool:
    
    def test_plot_list_tool_initialization(self):
        plot_storage = PlotStorage("test_execution")
        tool = FrameworkAgnosticPlotListTool(plot_storage=plot_storage)
        
        assert tool.name == "list_available_plots"
        assert "List all plots available" in tool.description
        assert tool.plot_storage == plot_storage
    
    def test_empty_plot_list(self):
        plot_storage = PlotStorage("test_execution")
        tool = FrameworkAgnosticPlotListTool(plot_storage=plot_storage)
        
        result = tool.call()
        
        assert hasattr(result, 'message')
        assert result.message == "No plots available yet."
    
    def test_plot_list_with_plots(self):
        plot_storage = PlotStorage("test_execution")
        
        plot_id = plot_storage.store_plot(
            html_content="<div>Test plot</div>",
            description="Test plot description",
            agent_name="test_agent",
            data_summary="Test data"
        )
        
        tool = FrameworkAgnosticPlotListTool(plot_storage=plot_storage)
        result = tool.call()
        
        assert hasattr(result, 'message')
        assert "Available plots for referencing:" in result.message
        assert f"[PLOT:{plot_id}]" in result.message
        assert "Test plot description" in result.message
        assert "by test_agent" in result.message


class TestOpenAIToolSchema:
    
    def test_openai_tool_schema_export(self):
        plot_storage = PlotStorage("test_execution")
        tool = FrameworkAgnosticPlottingTool(plot_storage=plot_storage)
        
        schema = tool.to_openai_tool()
        
        assert isinstance(schema, dict)
        assert schema["type"] == "function"
        assert "function" in schema
        assert schema["function"]["name"] == "python_plotting_tool"
        assert "description" in schema["function"]
        assert "parameters" in schema["function"]
        assert isinstance(schema["function"]["parameters"], dict)
    
    def test_plot_list_openai_schema(self):
        plot_storage = PlotStorage("test_execution")
        tool = FrameworkAgnosticPlotListTool(plot_storage=plot_storage)
        
        schema = tool.to_openai_tool()
        
        assert isinstance(schema, dict)
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "list_available_plots"
        assert "description" in schema["function"]
        assert "parameters" in schema["function"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])