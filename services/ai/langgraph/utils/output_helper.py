from typing import Any, TypeVar

T = TypeVar("T")

def extract_expert_output(expert_output: Any, target_field: str) -> str:
    """
    Extracts a specific field from an expert output object or dictionary.
    
    Args:
        expert_output: The output object (Pydantic model) or dictionary from an expert agent.
        target_field: The name of the field to extract (e.g., 'for_season_planner').
        
    Returns:
        The extracted string content.
        
    Raises:
        ValueError: If the output is None, contains questions (indicating HITL needed),
                   or is missing the target field.
    """
    if expert_output is None:
        raise ValueError(f"Expert output is None. Cannot extract '{target_field}'.")

    # Handle Pydantic models or objects with attributes
    if hasattr(expert_output, "output"):
        output = expert_output.output
        
        # Check if output is a list (Questions)
        if isinstance(output, list):
            raise ValueError("Expert output contains questions, not analysis. HITL interaction required.")
            
        # Check for the target field on the inner output object
        if hasattr(output, target_field):
            return getattr(output, target_field)
            
        # If output is a dict (fallback)
        if isinstance(output, dict):
            if target_field in output:
                return output[target_field]
                
    # Handle direct dictionary
    elif isinstance(expert_output, dict):
        # Check if it has an 'output' key that might contain the data
        if "output" in expert_output:
            output = expert_output["output"]
            if isinstance(output, dict) and target_field in output:
                return output[target_field]
            # If output is the object itself
            if isinstance(output, object) and hasattr(output, target_field):
                return getattr(output, target_field)
        
        # Direct access
        if target_field in expert_output:
            return expert_output[target_field]

    raise ValueError(f"Expert output missing '{target_field}' field. Type: {type(expert_output)}")


def extract_agent_content(value: Any) -> str:
    """
    Extracts content from a generic agent output (like season_plan or weekly_plan).
    
    Args:
        value: The agent output, which could be a string, dict, or Pydantic object.
        
    Returns:
        The string content.
    """
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
