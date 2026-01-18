from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _render_receiver_payload(payload: Any) -> str:
    if payload is None:
        return ""

    if hasattr(payload, "model_dump"):
        data = payload.model_dump()
    elif isinstance(payload, Mapping):
        data = payload
    else:
        return str(payload)

    sections = {
        "Signals": data.get("signals", []),
        "Evidence": data.get("evidence", []),
        "Implications": data.get("implications", []),
    }
    uncertainty = data.get("uncertainty")
    if uncertainty:
        sections["Uncertainty"] = uncertainty

    lines: list[str] = []
    for title, items in sections.items():
        lines.append(f"### {title}")
        if items:
            lines.extend([f"- {item}" for item in items])
        else:
            lines.append("- None")
        lines.append("")

    return "\n".join(lines).strip()


def extract_expert_output(expert_output: Any, target_field: str) -> str:
    if expert_output is None:
        raise ValueError(f"Expert output is None. Cannot extract '{target_field}'.")

    if hasattr(expert_output, "output"):
        output = expert_output.output
        
        if isinstance(output, list):
            raise ValueError("Expert output contains questions, not analysis. HITL interaction required.")

        if hasattr(output, target_field):
            return _render_receiver_payload(getattr(output, target_field))
            
        if isinstance(output, dict):
            if target_field in output:
                return _render_receiver_payload(output[target_field])
                
    elif isinstance(expert_output, dict):
        if "output" in expert_output:
            output = expert_output["output"]
            if isinstance(output, dict) and target_field in output:
                return _render_receiver_payload(output[target_field])
            if isinstance(output, object) and hasattr(output, target_field):
                return _render_receiver_payload(getattr(output, target_field))
        
        if target_field in expert_output:
            return _render_receiver_payload(expert_output[target_field])

    raise ValueError(f"Expert output missing '{target_field}' field. Type: {type(expert_output)}")


def extract_agent_content(value: Any) -> str:
    if not value:
        return ""
        
    if hasattr(value, "output"):
        output = value.output
        if isinstance(output, str):
            return output
        raise ValueError("AgentOutput contains questions, not content. HITL interaction required.")
        
    if isinstance(value, dict):
        return value.get("output", value.get("content", value))
        
    if isinstance(value, str):
        return value
        
    return str(value)
