import logging
from dataclasses import dataclass
from typing import Any, Literal

from langchain_core.messages import ToolMessage

from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import interrupt
from services.ai.ai_settings import AgentRole
from services.ai.model_config import ModelSelector
from services.ai.tools.hitl import create_communicate_with_human_tool
from services.ai.tools.plotting import PlotStorage, create_plotting_tools

from ..state.training_analysis_state import TrainingAnalysisState

logger = logging.getLogger(__name__)


@dataclass
class ExpertNodeConfig:
    node_name: str
    display_name: str
    agent_role: AgentRole
    system_prompt: str
    user_prompt_template: str
    state_result_key: str
    plotting_enabled: bool = True
    max_iterations: int = 15


def create_expert_subgraph(
    config: ExpertNodeConfig,
    plot_storage: PlotStorage | None = None,
    checkpointer: Any | None = None,
) -> StateGraph:
    tools = []
    hitl_tool = create_communicate_with_human_tool(config.display_name)
    tools.append(hitl_tool)
    
    if config.plotting_enabled and plot_storage:
        plotting_tool = create_plotting_tools(plot_storage, config.node_name)
        tools.append(plotting_tool)
    
    standard_tools = [t for t in tools if t.name != "communicate_with_human"]
    
    llm_with_tools = ModelSelector.get_llm(config.agent_role).bind_tools(tools)
    
    async def call_model(state: TrainingAnalysisState) -> dict:
        messages = state["messages"]
        logger.debug(f"{config.node_name}: Calling model with {len(messages)} messages")
        
        response = await llm_with_tools.ainvoke(messages)
        logger.info(
            f"{config.node_name}: Model responded with "
            f"{len(response.tool_calls) if hasattr(response, 'tool_calls') and response.tool_calls else 0} tool calls"
        )
        
        return {"messages": [response]}
    
    def route_action(state: TrainingAnalysisState) -> Literal["hitl", "tools", "end"]:
        last_message = state["messages"][-1]
        
        if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
            logger.info(f"{config.node_name}: No tool calls, ending")
            return "end"
        
        hitl_calls = [
            tc for tc in last_message.tool_calls 
            if tc["name"] == "communicate_with_human"
        ]
        
        if hitl_calls:
            logger.info(f"{config.node_name}: Routing to HITL interrupt")
            return "hitl"
        
        logger.info(f"{config.node_name}: Routing to standard tools")
        return "tools"
    
    async def hitl_interrupt(state: TrainingAnalysisState) -> dict:
        import json
        
        last_message = state["messages"][-1]
        
        # Robust tool-call parsing for different providers
        hitl_tc = next(
            tc for tc in last_message.tool_calls
            if tc.get("name") == "communicate_with_human"
        )
        
        original_tool_call_id = hitl_tc.get("id") or hitl_tc["id"]
        question_payload = hitl_tc.get("args") or hitl_tc.get("input") or {}
        
        # Add agent name for UI display
        question_payload = {**question_payload, "agent": config.display_name}
        
        logger.info(
            f"{config.node_name}: HITL interrupt triggered "
            f"(tool_call_id={original_tool_call_id})"
        )
        
        user_response = interrupt(question_payload)
        
        # Handle both str and dict payloads
        if isinstance(user_response, str):
            answer_content = user_response
        elif isinstance(user_response, dict):
            # Support multiple shapes
            answer_content = (
                user_response.get("content")
                or user_response.get("answer")
                or user_response.get("message")
                or json.dumps(user_response)
            )
        else:
            answer_content = str(user_response)
        
        tool_message = ToolMessage(
            content=answer_content,
            tool_call_id=original_tool_call_id
        )
        
        logger.info(
            f"{config.node_name}: HITL resumed, paired answer with "
            f"tool_call_id={original_tool_call_id}"
        )
        
        return {"messages": [tool_message]}
    
    standard_tools_node = ToolNode(standard_tools) if standard_tools else None
    
    subgraph = StateGraph(TrainingAnalysisState)
    
    subgraph.add_node(f"{config.node_name}_call_model", call_model)
    subgraph.add_node(f"{config.node_name}_hitl", hitl_interrupt)
    if standard_tools_node:
        subgraph.add_node(f"{config.node_name}_tools", standard_tools_node)
    
    subgraph.set_entry_point(f"{config.node_name}_call_model")
    
    routes = {
        "hitl": f"{config.node_name}_hitl",
        "end": END
    }
    if standard_tools_node:
        routes["tools"] = f"{config.node_name}_tools"
    
    subgraph.add_conditional_edges(
        f"{config.node_name}_call_model",
        route_action,
        routes
    )
    
    subgraph.add_edge(f"{config.node_name}_hitl", f"{config.node_name}_call_model")
    if standard_tools_node:
        subgraph.add_edge(f"{config.node_name}_tools", f"{config.node_name}_call_model")
    
    if checkpointer:
        logger.info(f"Created expert subgraph for {config.node_name} with checkpointer")
        return subgraph.compile(checkpointer=checkpointer)
    else:
        logger.warning(f"Created expert subgraph for {config.node_name} WITHOUT checkpointer - HITL will not work!")
        return subgraph.compile()