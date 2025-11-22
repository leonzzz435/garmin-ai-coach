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

SEASON_PLANNER_SYSTEM_PROMPT = """You are a strategic season planner.
## Goal
Create strategic season plans for long-term athletic development.
## Principles
- Strategic: Focus on macro-cycles and phases.
- Adaptive: Use expert insights to tailor the plan.
- Systematic: Ensure logical progression towards goals."""

SEASON_PLANNER_USER_PROMPT = """Create a STRATEGIC, HIGH-LEVEL season plan (12-24 weeks).

## Inputs
- Athlete: {athlete_name}
- Date: ```json {current_date} ```
- Competitions: ```json {competitions} ```

## Expert Insights
### Metrics
```markdown
{metrics_insights}
```
### Activity
```markdown
{activity_insights}
```
### Physiology
```markdown
{physiology_insights}
```

## Task
Create a macro-cycle framework.
- **Integrate**: Use expert insights as your north star.
- **Strategize**: Define phases, themes, and focus areas.
- **Respect Boundaries**: Do NOT prescribe daily workouts (Weekly Planner's job).

## Output Requirements
Format as structured markdown.
1. **Phases**: Define phases (Base, Build, etc.) with goals and themes.
2. **Expert Rationale**: Explicitly reference how Metrics, Activity, and Physiology informed the plan.
3. **Constraints**: Qualitative constraints derived from experts.

**Stay high-level**. Design the **map of the season**, not the turn-by-turn navigation. **BE CONCISE**."""




async def season_planner_node(state: TrainingAnalysisState) -> dict[str, list | str]:
    logger.info("Starting season planner node")

    hitl_enabled = state.get("hitl_enabled", True)
    logger.info(f"Season planner node: HITL {'enabled' if hitl_enabled else 'disabled'}")
    
    agent_start_time = datetime.now()

    tools = configure_node_tools(
        agent_name="season_planner",
        plot_storage=None,
        plotting_enabled=False,
    )

    system_prompt = (
        SEASON_PLANNER_SYSTEM_PROMPT +
        get_workflow_context("season_planner") +
        (get_hitl_instructions("season_planner") if hitl_enabled else "")
    )
    
    qa_messages_raw = state.get("season_planner_messages", [])
    qa_messages = []
    for msg in qa_messages_raw:
        if hasattr(msg, "type"):  # LangChain message object
            role = "assistant" if msg.type == "ai" else "user"
            qa_messages.append({"role": role, "content": msg.content})
        else:  # Already a dict
            qa_messages.append(msg)
    
    def get_strategic_insights(expert_outputs):
        if hasattr(expert_outputs, "output"):
            output = expert_outputs.output
            if isinstance(output, list):
                raise ValueError("Expert outputs contain questions, not analysis. HITL interaction required.")
            if hasattr(output, "for_season_planner"):
                return output.for_season_planner
        raise ValueError(f"Expert outputs missing 'output.for_season_planner' field: {type(expert_outputs)}")
    
    # Try to read existing season plan using PlanStorage
    from services.ai.utils.plan_storage import FilePlanStorage
    
    existing_season_plan = ""
    try:
        storage = FilePlanStorage()
        loaded_plan = storage.load_plan(state["user_id"], "season_plan")
        if loaded_plan:
            existing_season_plan = loaded_plan
    except Exception as e:
        logger.warning(f"Could not read existing season plan: {e}")

    base_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": SEASON_PLANNER_USER_PROMPT.format(
            athlete_name=state["athlete_name"],
            current_date=json.dumps(state["current_date"], indent=2),
            competitions=json.dumps(state["competitions"], indent=2),
            metrics_insights=get_strategic_insights(state.get("metrics_outputs")),
            activity_insights=get_strategic_insights(state.get("activity_outputs")),
            physiology_insights=get_strategic_insights(state.get("physiology_outputs")),
        ) + (f"\n\n## Existing Season Plan\nWe have an existing season plan. Do NOT start from scratch. Review this plan against the new expert insights. If the plan is still valid, maintain the phase structure and just refine the details. Only trigger a full replan if the new data suggests the old plan is dangerously off-track.\n\n```markdown\n{existing_season_plan}\n```" if existing_season_plan else "")},
    ]

    base_llm = ModelSelector.get_llm(AgentRole.SEASON_PLANNER)
    
    # Bind tools first, then apply structured output
    llm_with_tools = base_llm.bind_tools(tools) if tools else base_llm
    llm_with_structure = llm_with_tools.with_structured_output(AgentOutput)
    
    async def call_season_planning():
        messages_with_qa = base_messages + qa_messages
        if tools:
            return await handle_tool_calling_in_node(
                llm_with_tools=llm_with_structure,
                messages=messages_with_qa,
                tools=tools,
                max_iterations=15,
            )
        else:
            return await llm_with_structure.ainvoke(messages_with_qa)

    async def node_execution():
        agent_output = await retry_with_backoff(
            call_season_planning, AI_ANALYSIS_CONFIG, "Season Planning"
        )

        execution_time = (datetime.now() - agent_start_time).total_seconds()
        log_node_completion("Season planning", execution_time)

        return {
            "season_plan": agent_output.model_dump(),
            "costs": [create_cost_entry("season_planner", execution_time)],
        }

    return await execute_node_with_error_handling(
        node_name="Season planner",
        node_function=node_execution,
        error_message_prefix="Season planning failed",
    )
