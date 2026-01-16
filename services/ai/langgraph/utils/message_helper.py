from typing import Any

from langchain_core.messages import BaseMessage


def normalize_langchain_messages(messages: list[Any]) -> list[dict[str, str]]:
    """
    Normalize a list of messages (which may contain LangChain Message objects or dicts)
    into a list of standard dictionaries with 'role' and 'content'.
    """
    normalized_messages = []
    for msg in messages:
        if isinstance(msg, BaseMessage):
            # Map LangChain types to roles
            role = "assistant" if msg.type == "ai" else "user"
            # Handle system messages if they appear in history (rare but possible)
            if msg.type == "system":
                role = "system"
            elif msg.type == "human":
                role = "user"
                
            normalized_messages.append({"role": role, "content": str(msg.content)})
        elif isinstance(msg, dict):
            normalized_messages.append(msg)
        elif hasattr(msg, "type") and hasattr(msg, "content"):
             # Duck typing for other message-like objects
            role = "assistant" if msg.type == "ai" else "user"
            normalized_messages.append({"role": role, "content": str(msg.content)})
            
    return normalized_messages
