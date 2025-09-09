# Plotting Tool Integration with LangGraph

## Overview

This document describes the **proper integration of plotting tools with LangGraph workflows** using 2025 LangChain best practices. The integration was refactored to use canonical patterns: `@tool` decorators, `.bind_tools()`, `ToolNode`, and `tools_condition`.

## Problem Identified

### Original Issue
The plotting tools were being **instantiated but never passed to the agents**:

```python
# ❌ BROKEN: Tools created but not bound
plot_storage = PlotStorage(state['execution_id'])
plotting_tool = PythonPlottingTool(plot_storage=plot_storage)  # Created
plotting_tool.agent_name = "metrics"

llm = ModelSelector.get_llm(AgentRole.METRICS)  # No tools bound
response = await llm.ainvoke(messages)  # Agents can't access plotting!
```

**Result**: Agents had no access to plotting functionality despite tools being available.

## Solution: 2025 LangChain Best Practices

### 1. LangChain `@tool` Decorator Pattern

**File**: [`services/ai/tools/plotting/langchain_tools.py`](../services/ai/tools/plotting/langchain_tools.py)

```python
@tool("python_plotting_tool", return_direct=False)
def python_plotting_tool(python_code: str, description: str) -> str:
    """Execute complete Python code to create interactive Plotly visualizations."""
    # Implementation delegates to framework-agnostic core
```

**Benefits**:
- **LangChain-native**: Direct compatibility with `.bind_tools()`
- **Framework-agnostic**: Wraps existing plotting logic
- **Type-safe**: Automatic schema generation
- **Future-ready**: Compatible with OpenAI tool calling

### 2. Proper Tool Binding

**Updated Nodes** (Example: [`services/ai/langgraph/nodes/metrics_node.py`](../services/ai/langgraph/nodes/metrics_node.py)):

```python
# ✅ CORRECT: Tools properly bound to LLM
plot_storage = PlotStorage(state['execution_id'])
plotting_tool = create_plotting_tool(plot_storage, agent_name="metrics")

llm = ModelSelector.get_llm(AgentRole.METRICS)
llm_with_tools = llm.bind_tools([plotting_tool])  # Tools bound!

# Tool calling handled within node using helper
response = await handle_tool_calling_in_node(
    llm_with_tools=llm_with_tools,
    messages=messages,
    tools=[plotting_tool],
    max_iterations=3
)
```

### 3. Tool Calling Management

**Helper**: [`services/ai/langgraph/nodes/tool_calling_helper.py`](../services/ai/langgraph/nodes/tool_calling_helper.py)

Manages the **agent → tool → agent** conversation loop within individual nodes:

```python
async def handle_tool_calling_in_node(llm_with_tools, messages, tools, max_iterations=5):
    """Handle tool calling within a LangGraph node."""
    # Manages conversation loop until final text response
    # - Detects tool calls in AI responses
    # - Executes tools and adds ToolMessages
    # - Continues until LLM returns final text
```

**Why This Approach**:
- **Preserves existing architecture**: No major workflow restructuring needed
- **Node-level control**: Each agent handles its own tool interactions
- **Maintains performance**: Avoids complex graph routing for simple tool use

## Alternative: Canonical LangGraph Pattern

**File**: [`services/ai/langgraph/workflows/analysis_workflow_with_tools.py`](../services/ai/langgraph/workflows/analysis_workflow_with_tools.py)

Implements the **full canonical pattern** with `tools_condition` and `ToolNode`:

```python
# Agent nodes with tool-bound LLMs
workflow.add_node("metrics_agent", create_metrics_agent_node)
workflow.add_node("tools", ToolNode(plotting_tools))

# Canonical routing: agent → tools_condition → ToolNode → agent → END
workflow.add_conditional_edges("metrics_agent", tools_condition)
workflow.add_edge("tools", "agent")
```

**Benefits**:
- **LangGraph standard**: Officially documented pattern
- **Automatic routing**: `tools_condition` handles tool call detection
- **Built-in tool execution**: `ToolNode` manages tool invocation
- **Future-proof**: Aligned with LangGraph evolution

## Implementation Details

### Tools Architecture

```
Framework-Agnostic Core → LangChain @tool Wrapper → LLM Integration
         ↓                        ↓                      ↓
FrameworkAgnosticPlottingTool → create_plotting_tool → llm.bind_tools()
```

### Node Integration

**Nodes with Plotting Tools**:
- [`metrics_node.py`](../services/ai/langgraph/nodes/metrics_node.py) - Training metrics visualization
- [`activity_interpreter_node.py`](../services/ai/langgraph/nodes/activity_interpreter_node.py) - Session pattern charts  
- [`physiology_node.py`](../services/ai/langgraph/nodes/physiology_node.py) - Recovery/HRV visualizations

**Nodes with Plot List Tools**:
- [`synthesis_node.py`](../services/ai/langgraph/nodes/synthesis_node.py) - References existing plots

### Tool Capabilities

**Plotting Tool Features**:
- **Complete Python execution**: Full Plotly/Matplotlib support
- **Data processing**: Pandas, NumPy integration  
- **Plot limits**: Maximum 2 plots per agent (cost control)
- **Reference system**: `[PLOT:plot_id]` linking in text
- **Error handling**: Detailed guidance for failed code

## Testing & Validation

**Test Suite**: [`tests/test_plotting_tool_integration.py`](../tests/test_plotting_tool_integration.py)

**Coverage**:
- ✅ `@tool` decorator creation 
- ✅ Direct tool invocation
- ✅ LLM tool binding validation
- ✅ `tools_condition` compatibility
- ✅ Canonical pattern components

**Results**: 5/5 tests passing with full integration validation

## Migration Benefits

### Before (Broken)
- **0% Tool Access**: Tools instantiated but never accessible to agents
- **Wasted Resources**: Tool creation without utilization
- **Missing Functionality**: No plotting capabilities in analysis

### After (Working)
- **100% Tool Access**: All agents can use plotting when needed
- **2025 Best Practices**: Modern LangChain patterns
- **Future-Proof**: Compatible with LangGraph evolution
- **Tested & Validated**: Comprehensive test coverage

## Usage Examples

### Agent Perspective
Agents can now request plots naturally:

```
"Let me create a visualization of your training load progression:

python_code: "
import plotly.graph_objects as go
import pandas as pd

# Process training data
df = pd.DataFrame(training_data)
fig = go.Figure()
fig.add_trace(go.Scatter(x=df['date'], y=df['load'], name='Training Load'))
fig.update_layout(title='Training Load Progression')
"

description: "Training load trend over the last 8 weeks"
```

### Result Integration
- Tool executes Python code securely
- Plot stored with unique ID  
- Agent receives: `"Plot created successfully! Reference as [PLOT:abc123]"`
- Agent incorporates reference in analysis text

## Future Enhancements

### Immediate (Available Now)
- **OpenAI Tool Calling**: Tools have `to_openai_tool()` method
- **Multiple Providers**: Works with Claude, GPT, etc.
- **Async Support**: Full async/await compatibility

### Planned
- **Enhanced Plot Types**: Additional visualization libraries
- **Interactive Features**: Dynamic plot parameters  
- **Plot Templates**: Pre-built chart configurations
- **Performance Metrics**: Plot generation analytics

## Migration Cleanup (Completed)

### Dead Code Removal
After successfully implementing 2025 LangChain patterns, the following **obsolete components were completely removed**:

**Removed Files**:
- ❌ `services/ai/tools/plotting/plotting_tool.py` - Legacy LangChain wrapper classes
- ❌ `services/ai/utils/intermediate_storage.py` - File-based storage replaced by LangGraph state

**Removed Classes**:
- ❌ `PythonPlottingTool` - Replaced by `@tool` decorated `python_plotting_tool`
- ❌ `PlotListTool` - Replaced by `@tool` decorated `list_available_plots`
- ❌ `IntermediateResultStorage` - Replaced by LangGraph state management

**Updated Imports**:
- All references to obsolete classes removed from `__init__.py` files
- Test suites updated to remove backward compatibility tests
- Import statements cleaned across the codebase

**Result**: **Clean, modern codebase** with only 2025 LangChain patterns remaining. No legacy wrapper classes or dead code.

## Technical Architecture

### Clean Separation
- **Tool-Free Analysis Nodes**: Pure LLM reasoning
- **Tool-Enabled Agent Nodes**: Plotting capabilities when needed
- **Framework Agnostic**: Core plotting logic independent of LangChain

### Integration Points
1. **Tool Creation**: `create_plotting_tool()` factory functions
2. **LLM Binding**: `.bind_tools([tool])` for agent nodes
3. **Execution Handling**: `handle_tool_calling_in_node()` or canonical routing
4. **Result Integration**: Plot references in analysis text

## Final Status: ✅ COMPLETE

The plotting tool integration is **fully functional and cleaned**:
- ✅ Tools properly bound to LLMs using 2025 best practices
- ✅ All LangGraph nodes updated to use `.bind_tools()`
- ✅ Comprehensive test suite passing (5/5 tests)
- ✅ Complete documentation provided
- ✅ Dead code cleanup completed
- ✅ Modern `@tool` decorator pattern implemented
- ✅ Both node-level and canonical workflow patterns available

This integration ensures plotting tools are **properly accessible to AI agents** while following **2025 LangChain best practices** for robust, maintainable, and future-proof tool integration.