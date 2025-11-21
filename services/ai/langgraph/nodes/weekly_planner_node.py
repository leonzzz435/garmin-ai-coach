import json
import logging
from datetime import datetime

from services.ai.ai_settings import AgentRole
from services.ai.model_config import ModelSelector
from services.ai.utils.retry_handler import AI_ANALYSIS_CONFIG, retry_with_backoff

from ..schemas import AgentOutput
from ..state.training_analysis_state import TrainingAnalysisState
from .node_base import (
    configure_node_tools,
    create_cost_entry,
    execute_node_with_error_handling,
    log_node_completion,
)
from .prompt_components import get_hitl_instructions, get_workflow_context
from .tool_calling_helper import handle_tool_calling_in_node

logger = logging.getLogger(__name__)

WEEKLY_PLANNER_SYSTEM_PROMPT = """You are an elite endurance coach specializing in periodization.
## Goal
Create detailed, practical training plans that balance stress and recovery.
## Principles
- Adaptation: Progressive overload with adequate recovery.
- Specificity: Training must match the demands of the event.
- Individualization: Adapt to the athlete's current state and history."""

WEEKLY_PLANNER_USER_PROMPT = """Create a detailed 28-day (4-week) training plan.

## Inputs
### Season Plan
```markdown
{season_plan}
```
### Athlete Context
- Name: {athlete_name}
- Date: ```json {current_date} ```
- Upcoming Weeks: ```json {week_dates} ```
- Competitions: ```json {competitions} ```
- Instructions: ``` {planning_context} ```

### Expert Analysis
- Metrics: ``` {metrics_analysis} ```
- Activity: ``` {activity_analysis} ```
- Physiology: ``` {physiology_analysis} ```

## Task
Translate the Season Plan strategy and Expert signals into concrete daily sessions for the next 28 days.

## Constraints
- **Honor the Phase**: Prioritize the Season Plan's phase intent.
- **Respect Readiness**: Adjust intensity based on Physiology/Metrics signals (e.g., pull back if recovery is low).
- **Integrate Signals**: Use Activity Expert advice for session structure.
- **Brevity**: Use standard notation (e.g., "4x(5' Z4, 2' r)") to keep the plan compact.

## Output Requirements
1. **Zones Table**: Define intensity zones first.
2. **Structure**: Group by Week (1-4).
3. **Daily Format**:
   - **DAY & DATE**: e.g., "Mon, Nov 24"
   - **FOCUS**: 1-2 words (e.g., "Recovery", "VO2max")
   - **WORKOUT**: Concise structure string.
   - **PURPOSE**: One short sentence.
   - **ADAPTATION**: "If tired: ..."
"""


async def weekly_planner_node(state: TrainingAnalysisState) -> dict[str, list | str]:
    logger.info("Starting weekly planner node")

    hitl_enabled = state.get("hitl_enabled", True)
    logger.info(f"Weekly planner node: HITL {'enabled' if hitl_enabled else 'disabled'}")
    
    agent_start_time = datetime.now()

    tools = configure_node_tools(
        agent_name="weekly_planner",
        plot_storage=None,
        plotting_enabled=False,
    )

    system_prompt = (
        WEEKLY_PLANNER_SYSTEM_PROMPT +
        get_workflow_context("weekly_planner") +
        (get_hitl_instructions("weekly_planner") if hitl_enabled else "")
    )
    
    def get_tactical_details(expert_outputs):
        if hasattr(expert_outputs, "output"):
            output = expert_outputs.output
            if isinstance(output, list):
                raise ValueError("Expert outputs contain questions, not analysis. HITL interaction required.")
            if hasattr(output, "for_weekly_planner"):
                return output.for_weekly_planner
        raise ValueError(f"Expert outputs missing 'output.for_weekly_planner' field: {type(expert_outputs)}")
    
    def get_content(field):
        value = state.get(field, "")
        if hasattr(value, "output"):
            output = value.output
            if isinstance(output, str):
                return output
            raise ValueError("AgentOutput contains questions, not content. HITL interaction required.")
        if isinstance(value, dict):
            return value.get("output", value.get("content", value))
        return value
    
    qa_messages_raw = state.get("weekly_planner_messages", [])
    qa_messages = []
    for msg in qa_messages_raw:
        if hasattr(msg, "type"):  # LangChain message object
            role = "assistant" if msg.type == "ai" else "user"
            qa_messages.append({"role": role, "content": msg.content})
        else:  # Already a dict
            qa_messages.append(msg)
    
    user_message = {"role": "user", "content": WEEKLY_PLANNER_USER_PROMPT.format(
        season_plan=get_content("season_plan"),
        athlete_name=state["athlete_name"],
        current_date=json.dumps(state["current_date"], indent=2),
        week_dates=json.dumps(state["week_dates"], indent=2),
        competitions=json.dumps(state["competitions"], indent=2),
        planning_context=state["planning_context"],
        metrics_analysis=get_tactical_details(state.get("metrics_outputs")),
        activity_analysis=get_tactical_details(state.get("activity_outputs")),
        physiology_analysis=get_tactical_details(state.get("physiology_outputs")),
    )}
    
    base_messages = [{"role": "system", "content": system_prompt}, user_message]
    
    base_llm = ModelSelector.get_llm(AgentRole.WORKOUT)
    llm_with_tools = base_llm.bind_tools(tools) if tools else base_llm
    llm_with_structure = llm_with_tools.with_structured_output(AgentOutput)

    async def call_weekly_planning():
        messages_with_qa = base_messages + qa_messages
        if tools:
            return await handle_tool_calling_in_node(
                llm_with_tools=llm_with_structure,
                messages=messages_with_qa,
                tools=tools,
                max_iterations=15,
            )
        return await llm_with_structure.ainvoke(messages_with_qa)

    async def node_execution():
        agent_output = await retry_with_backoff(
            call_weekly_planning, AI_ANALYSIS_CONFIG, "Weekly Planning"
        )

        execution_time = (datetime.now() - agent_start_time).total_seconds()
        log_node_completion("Weekly planning", execution_time)

        return {
            "weekly_plan": agent_output.model_dump(),
            "costs": [create_cost_entry("weekly_planner", execution_time)],
        }

    return await execute_node_with_error_handling(
        node_name="Weekly planner",
        node_function=node_execution,
        error_message_prefix="Weekly planning failed",
    )
