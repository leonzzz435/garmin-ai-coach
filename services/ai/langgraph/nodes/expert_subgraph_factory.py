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
        from langchain_core.messages import AIMessage, ToolMessage
        
        messages = state["messages"]
        
        # Count message types for diagnostics
        tool_msg_count = sum(1 for m in messages if isinstance(m, ToolMessage))
        ai_msg_count = sum(1 for m in messages if isinstance(m, AIMessage))
        
        logger.critical(
            f"CALL_MODEL_START | node={config.node_name} | "
            f"message_count={len(messages)} | "
            f"last_message_type={type(messages[-1]).__name__} | "
            f"tool_messages={tool_msg_count} | "
            f"ai_messages={ai_msg_count}"
        )
        
        # Log all ToolMessages with their tool_call_ids for verification
        for i, msg in enumerate(messages):
            if isinstance(msg, ToolMessage):
                logger.critical(
                    f"CALL_MODEL_TOOLMSG | node={config.node_name} | "
                    f"index={i} | tool_call_id={msg.tool_call_id} | "
                    f"content_preview='{msg.content[:50]}...'"
                )
        
        response = await llm_with_tools.ainvoke(messages)
        
        logger.critical(
            f"CALL_MODEL_END | node={config.node_name} | "
            f"response_type={type(response).__name__} | "
            f"has_tool_calls={hasattr(response, 'tool_calls') and bool(response.tool_calls)} | "
            f"tool_call_count={len(response.tool_calls) if hasattr(response, 'tool_calls') and response.tool_calls else 0}"
        )
        
        # Log each tool call in the response
        if hasattr(response, 'tool_calls') and response.tool_calls:
            for tc in response.tool_calls:
                logger.critical(
                    f"CALL_MODEL_TOOLCALL | node={config.node_name} | "
                    f"tool_name={tc.get('name')} | "
                    f"tool_call_id={tc.get('id')} | "
                    f"args_preview={str(tc.get('args', {}))[:100]}"
                )
        
        return {"messages": [response]}
    
    def route_action(state: TrainingAnalysisState) -> Literal["hitl", "tools", "end"]:
        from langchain_core.messages import AIMessage
        
        last_message = state["messages"][-1]
        
        if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
            logger.info(f"{config.node_name}: No tool calls, ending")
            return "end"
        
        # Count existing HITL interactions by finding ToolMessages that responded to communicate_with_human
        hitl_response_count = 0
        for msg in state["messages"]:
            if isinstance(msg, ToolMessage):
                # Check if this ToolMessage is responding to a communicate_with_human call
                # by finding the corresponding AIMessage with matching tool_call_id
                for ai_msg in state["messages"]:
                    if isinstance(ai_msg, AIMessage) and hasattr(ai_msg, "tool_calls"):
                        for tc in ai_msg.tool_calls:
                            if tc.get("id") == msg.tool_call_id and tc.get("name") == "communicate_with_human":
                                hitl_response_count += 1
                                break
        
        logger.critical(
            f"ROUTE_ACTION | node={config.node_name} | "
            f"existing_hitl_responses={hitl_response_count}"
        )
        
        hitl_calls = [
            tc for tc in last_message.tool_calls
            if tc["name"] == "communicate_with_human"
        ]
        
        # If we have HITL calls but already hit the limit, filter them out
        if hitl_calls and hitl_response_count >= 1:
            logger.warning(
                f"{config.node_name}: HITL call requested but limit reached "
                f"(count={hitl_response_count}), filtering out HITL calls"
            )
            # Remove HITL calls from consideration
            other_calls = [
                tc for tc in last_message.tool_calls
                if tc["name"] != "communicate_with_human"
            ]
            if other_calls:
                logger.info(f"{config.node_name}: Routing to standard tools (HITL filtered)")
                return "tools"
            else:
                logger.info(f"{config.node_name}: No valid tool calls after filtering, ending")
                return "end"
        
        if hitl_calls:
            logger.info(f"{config.node_name}: Routing to HITL interrupt (count={hitl_response_count})")
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
        
        # Add agent name and tool_call_id for stable interrupt tracking
        question_payload = {
            **question_payload,
            "agent": config.display_name,
            "tool_call_id": original_tool_call_id
        }
        
        # Extract question text for diagnostic logging
        question_text = question_payload.get("message", str(question_payload))[:50]
        
        logger.critical(
            f"HITL_INTERRUPT_START | node={config.node_name} | "
            f"tool_call_id={original_tool_call_id} | "
            f"question='{question_text}...' | "
            f"state_message_count={len(state['messages'])} | "
            f"last_ai_message_id={id(last_message)}"
        )
        
        user_response = interrupt(question_payload)
        
        logger.critical(
            f"HITL_INTERRUPT_RESUME | node={config.node_name} | "
            f"tool_call_id={original_tool_call_id} | "
            f"answer={str(user_response)[:100]} | "
            f"answer_type={type(user_response).__name__} | "
            f"answer_keys={list(user_response.keys()) if isinstance(user_response, dict) else 'N/A'}"
        )
        
        # Extract the answer for THIS tool_call_id from the resume dict
        if isinstance(user_response, dict) and original_tool_call_id in user_response:
            # Answer dict contains {tool_call_id: payload} - extract our payload
            our_payload = user_response[original_tool_call_id]
            logger.critical(
                f"HITL_EXTRACT_PAYLOAD | node={config.node_name} | "
                f"tool_call_id={original_tool_call_id} | "
                f"payload_type={type(our_payload).__name__} | "
                f"payload_value={str(our_payload)[:100]}"
            )
            
            # Now unwrap the payload content
            if isinstance(our_payload, str):
                answer_content = our_payload
            elif isinstance(our_payload, dict):
                answer_content = (
                    our_payload.get("content")
                    or our_payload.get("answer")
                    or our_payload.get("message")
                    or str(our_payload)  # Don't JSON dump if not content field
                )
            else:
                answer_content = str(our_payload)
        elif isinstance(user_response, dict) and original_tool_call_id not in user_response:
            # Mismatch: response dict doesn't contain our tool_call_id
            # Check if there's only one key and use it anyway (parent might have wrong key)
            if len(user_response) == 1:
                logger.critical(
                    f"HITL_RESUME_MISMATCH_SINGLE | node={config.node_name} | "
                    f"expected_tool_call_id={original_tool_call_id} | "
                    f"received_keys={list(user_response.keys())} | "
                    f"action=using_single_key_anyway"
                )
                # Extract the single value regardless of key
                single_value = next(iter(user_response.values()))
                if isinstance(single_value, str):
                    answer_content = single_value
                elif isinstance(single_value, dict):
                    answer_content = (
                        single_value.get("content")
                        or single_value.get("answer")
                        or single_value.get("message")
                        or str(single_value)
                    )
                else:
                    answer_content = str(single_value)
            else:
                # Multiple keys but none match - log error and use placeholder
                logger.critical(
                    f"HITL_RESUME_MISMATCH_MULTI | node={config.node_name} | "
                    f"expected_tool_call_id={original_tool_call_id} | "
                    f"received_keys={list(user_response.keys())} | "
                    f"action=using_placeholder"
                )
                answer_content = "[Response mismatch - please retry]"
        elif isinstance(user_response, str):
            # Direct string answer
            answer_content = user_response
        elif isinstance(user_response, dict):
            # Legacy: single-item dict without tool_call_id key
            answer_content = (
                user_response.get("content")
                or user_response.get("answer")
                or user_response.get("message")
                or str(user_response)  # Don't JSON dump entire dict
            )
        else:
            answer_content = str(user_response)
        
        tool_message = ToolMessage(
            content=answer_content,
            tool_call_id=original_tool_call_id
        )
        
        logger.critical(
            f"HITL_TOOLMESSAGE_CREATED | node={config.node_name} | "
            f"tool_call_id={original_tool_call_id} | "
            f"content='{answer_content[:100]}...' | "
            f"message_id={id(tool_message)}"
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