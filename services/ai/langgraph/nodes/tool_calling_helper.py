
import logging
from typing import List, Dict, Any, Optional
from langchain_core.messages import AIMessage, ToolMessage

logger = logging.getLogger(__name__)


async def handle_tool_calling_in_node(
    llm_with_tools,
    messages: List[Dict[str, str]],
    tools: List,
    max_iterations: int = 5
) -> str:
    conversation = []
    for msg in messages:
        if msg["role"] == "system":
            conversation.append({"role": "system", "content": msg["content"]})
        elif msg["role"] == "user":
            conversation.append({"role": "user", "content": msg["content"]})
    
    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        logger.debug(f"Tool calling iteration {iteration}")
        
        response = await llm_with_tools.ainvoke(conversation)
        
        if hasattr(response, 'tool_calls') and response.tool_calls:
            logger.info(f"LLM requested {len(response.tool_calls)} tool calls")
            
            conversation.append(response)
            
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id = tool_call["id"]
                
                logger.info(f"Executing tool: {tool_name}")
                
                tool = None
                for t in tools:
                    if hasattr(t, 'name') and t.name == tool_name:
                        tool = t
                        break
                
                if tool is None:
                    error_msg = f"Tool {tool_name} not found"
                    logger.error(error_msg)
                    tool_result = error_msg
                else:
                    try:
                        if hasattr(tool, 'ainvoke'):
                            tool_result = await tool.ainvoke(tool_args)
                        elif hasattr(tool, 'invoke'):
                            tool_result = tool.invoke(tool_args)
                        elif callable(tool):
                            tool_result = await tool.ainvoke(tool_args)
                        else:
                            tool_result = f"Unable to invoke tool {tool_name}"
                        
                        logger.info(f"Tool {tool_name} executed successfully")
                    except Exception as e:
                        tool_result = f"Tool execution error: {str(e)}"
                        logger.error(f"Tool {tool_name} failed: {e}")
                
                tool_message = ToolMessage(
                    content=str(tool_result),
                    tool_call_id=tool_id
                )
                conversation.append(tool_message)
        
        else:
            final_response = response.content if hasattr(response, 'content') else str(response)
            logger.info(f"Final response received after {iteration} iterations")
            return final_response
    
    logger.warning(f"Max iterations ({max_iterations}) reached in tool calling")
    final_response = response.content if hasattr(response, 'content') else str(response)
    return final_response