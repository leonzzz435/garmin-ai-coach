import logging

from langchain_core.messages import ToolMessage

logger = logging.getLogger(__name__)

# Import GraphInterrupt exception class (not the interrupt function!)
try:
    from langgraph.errors import GraphInterrupt
except ImportError:
    try:
        from langgraph.errors import NodeInterrupt as GraphInterrupt
    except ImportError:
        class GraphInterrupt(BaseException):  # type: ignore
            """Placeholder exception for when LangGraph is not installed"""
            pass


def extract_text_content(response) -> str:
    content = response.content if hasattr(response, 'content') else str(response)

    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get('type') == 'text' and 'text' in item:
                return item['text']

        for item in content:
            if isinstance(item, dict) and 'text' in item:
                return item['text']

        return str(content)

    return str(content)


async def handle_tool_calling_in_node(
    llm_with_tools, messages: list[dict[str, str]], tools: list, max_iterations: int = 5
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
                    # Execute tool - GraphInterrupt will bubble up for HITL
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
                    
                    except GraphInterrupt:
                        # CRITICAL: Let LangGraph handle the pause/resume
                        logger.info(f"Tool {tool_name} triggered HITL interrupt - pausing workflow")
                        raise

                tool_message = ToolMessage(content=str(tool_result), tool_call_id=tool_id)
                conversation.append(tool_message)

        else:
            final_response = response.content if hasattr(response, 'content') else str(response)

            if isinstance(final_response, list):
                for item in final_response:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        final_response = item.get('text', str(response))
                        break

            logger.info(f"Final response received after {iteration} iterations")
            return final_response

    logger.warning(f"Max iterations ({max_iterations}) reached in tool calling")
    final_response = response.content if hasattr(response, 'content') else str(response)
    return final_response
