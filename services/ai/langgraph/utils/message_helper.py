from __future__ import annotations

from collections.abc import Mapping

from langchain_core.messages import BaseMessage


def normalize_langchain_messages(messages: list[object]) -> list[dict[str, str]]:
    normalized_messages: list[dict[str, str]] = []
    for message in messages:
        if isinstance(message, BaseMessage):
            role = {
                "ai": "assistant",
                "human": "user",
                "system": "system",
            }.get(message.type, "user")
            normalized_messages.append({"role": role, "content": str(message.content)})
            continue

        if isinstance(message, Mapping):
            normalized_messages.append(
                {
                    "role": str(message.get("role", "user")),
                    "content": str(message.get("content", "")),
                }
            )
            continue

        if hasattr(message, "type") and hasattr(message, "content"):
            role = "assistant" if message.type == "ai" else "user"
            normalized_messages.append({"role": role, "content": str(message.content)})

    return normalized_messages
