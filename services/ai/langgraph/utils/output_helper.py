from typing import Any


def extract_expert_output(expert_output: Any, target_field: str) -> str:
    if expert_output is None:
        raise ValueError(f"Expert output is None. Cannot extract '{target_field}'.")

    if hasattr(expert_output, "output"):
        output = expert_output.output
        
        if hasattr(output, "type"):
            if output.type == "questions":
                raise ValueError("Expert output contains questions, not analysis. HITL interaction required.")
            if output.type == "analysis":
                if hasattr(output, target_field):
                    return getattr(output, target_field)
        
        if isinstance(output, list):
            raise ValueError("Expert output contains questions, not analysis. HITL interaction required.")

        if hasattr(output, target_field):
            return getattr(output, target_field)
            
        if isinstance(output, dict):
            if target_field in output:
                return output[target_field]
                
    elif isinstance(expert_output, dict):
        if "output" in expert_output:
            output = expert_output["output"]
            if isinstance(output, dict):
                if output.get("type") == "questions":
                    raise ValueError("Expert output contains questions, not analysis. HITL interaction required.")
                if target_field in output:
                    return output[target_field]
            if isinstance(output, object) and hasattr(output, target_field):
                return getattr(output, target_field)
        
        if target_field in expert_output:
            return expert_output[target_field]

    raise ValueError(f"Expert output missing '{target_field}' field. Type: {type(expert_output)}")


def extract_agent_content(value: Any) -> str:
    if not value:
        return ""
        
    if hasattr(value, "output"):
        output = value.output
        
        if hasattr(output, "type"):
            if output.type == "questions":
                raise ValueError("AgentOutput contains questions, not content. HITL interaction required.")
            if output.type == "content":
                return output.content
        
        if isinstance(output, str):
            return output
        raise ValueError("AgentOutput contains questions, not content. HITL interaction required.")
        
    if isinstance(value, dict):
        output = value.get("output", value)
        if isinstance(output, dict):
            if output.get("type") == "questions":
                raise ValueError("AgentOutput contains questions, not content. HITL interaction required.")
            if output.get("type") == "content":
                return output.get("content", "")
        return value.get("output", value.get("content", value))
        
    if isinstance(value, str):
        return value
        
    return str(value)
