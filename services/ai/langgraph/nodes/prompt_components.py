from typing import Literal

AgentType = Literal[
    "metrics_summarizer",
    "physiology_summarizer",
    "activity_summarizer",
    "metrics",
    "physiology",
    "activity",
    "synthesis",
    "season_planner",
    "weekly_planner"
]


def get_workflow_context(agent_type: AgentType) -> str:
    """Role-specialized workflow context."""
    
    # Summarizer agents
    if agent_type in ["metrics_summarizer", "physiology_summarizer", "activity_summarizer"]:
        domain = agent_type.replace("_summarizer", "")
        return f"""
## System Role
You are the **{agent_type.replace('_', ' ').title()}**.
- **Input**: Raw `garmin_data`
- **Output**: Structured `{domain}_summary`
- **Goal**: Condense raw data into a factual, structured summary for the {domain} expert. Do NOT interpret."""

    # Expert agents
    elif agent_type in ["metrics", "physiology", "activity"]:
        return f"""
## System Role
You are the **{agent_type.title()} Expert**.
- **Input**: `{agent_type}_summary`
- **Output**: `{agent_type}_outputs` with 3 fields:
  1. `for_synthesis`: For the comprehensive report.
  2. `for_season_planner`: Strategic insights (12-24 weeks).
  3. `for_weekly_planner`: Tactical details (next 28 days).
- **Goal**: Analyze patterns and provide specific insights for each consumer.
- **Context**: You are 1 of 3 parallel experts. Focus ONLY on your domain."""

    # Synthesis agent
    elif agent_type == "synthesis":
        return """
## System Role
You are the **Synthesis Agent**.
- **Input**: `for_synthesis` fields from Metrics, Physiology, and Activity experts.
- **Output**: `synthesis_result` (Comprehensive Athlete Report).
- **Goal**: Integrate domain insights into a coherent story. Focus on historical patterns, not future planning."""

    # Planner agents
    elif agent_type in ["season_planner", "weekly_planner"]:
        timeframe = "12-24 week strategy" if agent_type == "season_planner" else "next 28-day workouts"
        return f"""
## System Role
You are the **{agent_type.replace('_', ' ').title()}**.
- **Input**: `for_{agent_type}` fields from Metrics, Physiology, and Activity experts.
- **Output**: `{agent_type.replace('_planner', '_plan')}` ({timeframe}).
- **Goal**: Translate expert insights into a concrete {timeframe}.
- **Context**: Use the expert signals as your primary constraints and guides."""

    return ""


def get_plotting_instructions(agent_name: str) -> str:
    return f"""
## Visualization Rules
- **Constraint**: Create plots ONLY for unique insights not visible in standard Garmin reports. Max 2 plots.
- **Reference**: You MUST reference each plot EXACTLY ONCE in your text using `[PLOT:{agent_name}_TIMESTAMP_ID]`.
- **Placement**: Place the reference where it best supports your analysis. Do not repeat it."""


def get_hitl_instructions(agent_name: str) -> str:
    return """
## Human Interaction
- **Questions**: If you need clarification, populate the `questions` field.
- **Criteria**: Only ask if data is ambiguous or user preference is required. Do not ask for obvious info.
- **Process**: If you ask questions, your execution pauses until the user answers."""