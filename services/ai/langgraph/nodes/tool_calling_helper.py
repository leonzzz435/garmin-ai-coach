import logging

from langchain_core.messages import ToolMessage

from langgraph.errors import GraphInterrupt

logger = logging.getLogger(__name__)


def extract_text_content(content) -> str:
    if not isinstance(content, list):
        return str(content)
    
    text_item = next(
        (item["text"] for item in content
         if isinstance(item, dict) and item.get("type") == "text" and "text" in item),
        None
    )
    if text_item:
        return text_item
    
    return next(
        (item["text"] for item in content if isinstance(item, dict) and "text" in item),
        str(content)
    )


async def handle_tool_calling_in_node(
    llm_with_tools, messages: list[dict[str, str]], tools: list, max_iterations: int = 5
) -> str:
    conversation = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in messages if msg["role"] in ("system", "user")
    ]

    iteration = 0
    while iteration < max_iterations:
        iteration += 1
        logger.debug(f"Tool calling iteration {iteration}")

        response = await llm_with_tools.ainvoke(conversation)

        if hasattr(response, "tool_calls") and response.tool_calls:
            logger.info(f"LLM requested {len(response.tool_calls)} tool calls")

            conversation.append(response)

            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id = tool_call["id"]

                logger.info(f"Executing tool: {tool_name}")

                tool = next(
                    (tool_candidate for tool_candidate in tools
                     if hasattr(tool_candidate, "name") and tool_candidate.name == tool_name),
                    None
                )

                if tool is None:
                    error_msg = f"Tool {tool_name} not found"
                    logger.error(error_msg)
                    tool_result = error_msg
                else:
                    try:
                        if hasattr(tool, "ainvoke"):
                            tool_result = await tool.ainvoke(tool_args)
                        elif hasattr(tool, "invoke"):
                            tool_result = tool.invoke(tool_args)
                        elif callable(tool):
                            tool_result = await tool.ainvoke(tool_args)
                        else:
                            tool_result = f"Unable to invoke tool {tool_name}"

                        logger.info(f"Tool {tool_name} executed successfully")
                    
                    except GraphInterrupt:
                        logger.info(f"Tool {tool_name} triggered HITL interrupt - pausing workflow")
                        raise

                tool_message = ToolMessage(content=str(tool_result), tool_call_id=tool_id)
                conversation.append(tool_message)

        else:
            content = response.content if hasattr(response, "content") else str(response)
            final_response = extract_text_content(content)
            logger.info(f"Final response received after {iteration} iterations")
            return final_response

    logger.warning(f"Max iterations ({max_iterations}) reached in tool calling")
    content = response.content if hasattr(response, "content") else str(response)
    return extract_text_content(content)
