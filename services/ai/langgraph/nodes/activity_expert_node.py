import json
import logging
from datetime import datetime

from services.ai.ai_settings import AgentRole
from services.ai.langgraph.schemas import ActivityExpertOutputs
from services.ai.langgraph.state.training_analysis_state import TrainingAnalysisState
from services.ai.langgraph.utils.message_helper import normalize_langchain_messages
from services.ai.model_config import ModelSelector
from services.ai.tools.plotting import PlotStorage
from services.ai.utils.retry_handler import AI_ANALYSIS_CONFIG, retry_with_backoff

from .node_base import (
    configure_node_tools,
    create_cost_entry,
    create_plot_entries,
    execute_node_with_error_handling,
    log_node_completion,
)
from .prompt_components import (
    get_hitl_instructions,
    get_plotting_instructions,
    get_workflow_context,
)
from .tool_calling_helper import handle_tool_calling_in_node

logger = logging.getLogger(__name__)

ACTIVITY_EXPERT_SYSTEM_PROMPT_BASE = """## Goal
Interpret structured activity data to optimize workout progression patterns.
## Principles
- Precision: Detect subtle execution details.
- Pattern Recognition: Identify what works and what doesn't.
- Clarity: Cut through confusion with direct analysis."""

ACTIVITY_EXPERT_USER_PROMPT = """## Task
Interpret activity summaries to identify patterns and guidance.

## Constraints
- Focus on **session-level execution** (pace, power, HR, structure).
- Do NOT explain global load (Metrics Expert's job).
- Do NOT propose future schedules (Planner's job).
- Focus on **"what this specific workout does to the system"**.

## Inputs
### Activity Summary
{activity_summary}
### Context
- Competitions: ```json {competitions} ```
- Date: ```json {current_date} ```
- **User Context**: ``` {analysis_context} ```

## Output Requirements
Produce 3 structured fields. For EACH field, use this internal layout:
- **Signals**: what changed (concise)
- **Evidence**: numbers + date ranges
- **Implications**: constraints/opportunities for this receiver
- **Uncertainty**: gaps/low coverage if any

**Important**: Tailor content for each consumer.

### 1. `for_synthesis` (Comprehensive Report)
- **Context**: This feeds the **"Whole Athlete"** view (Summary & Synthesis).
- **Goal**: Provide a qualitative assessment of execution quality.
- **Freedom**: Highlight what matters most—execution patterns, progression quality, or consistency.

### 2. `for_season_planner` (12-24 Weeks)
- **Context**: This informs **Long-Term Structural Decisions** (Macro-cycle).
- **Goal**: Identify which "building blocks" (workout types) are effective for this specific athlete.
- **Freedom**: Focus on success patterns and sequencing preferences.

### 3. `for_weekly_planner` (Next 28 Days)
- **Context**: This informs **Immediate Scheduling & Constraints** (Mesocycle).
- **Goal**: Provide actionable rules for the next block.
- **Freedom**: define constraints, opportunities, and session load hints as needed.
- **CRITICAL**: Do NOT propose a schedule. Provide rules and building blocks."""

ACTIVITY_FINAL_CHECKLIST = """
## Final Checklist
- Use Signals/Evidence/Implications/Uncertainty per receiver.
- Stay within activity execution domain only.
- No schedule proposals.
"""


async def activity_expert_node(state: TrainingAnalysisState) -> dict[str, list | str | dict]:
    logger.info("Starting activity expert node")

    plot_storage = PlotStorage(state["execution_id"])
    plotting_enabled = state.get("plotting_enabled", False)
    hitl_enabled = state.get("hitl_enabled", True)

    logger.info(
        "Activity expert node: Plotting %s, HITL %s",
        "enabled" if plotting_enabled else "disabled",
        "enabled" if hitl_enabled else "disabled",
    )

    tools = configure_node_tools(
        agent_name="activity",
        plot_storage=plot_storage,
        plotting_enabled=plotting_enabled,
    )

    system_prompt = (
        get_workflow_context("activity")
        + ACTIVITY_EXPERT_SYSTEM_PROMPT_BASE
        + (get_plotting_instructions("activity") if plotting_enabled else "")
        + (get_hitl_instructions("activity") if hitl_enabled else "")
        + ACTIVITY_FINAL_CHECKLIST
    )

    base_llm = ModelSelector.get_llm(AgentRole.ACTIVITY_EXPERT)
    llm_with_tools = base_llm.bind_tools(tools) if tools else base_llm
    llm_with_structure = llm_with_tools.with_structured_output(ActivityExpertOutputs)

    agent_start_time = datetime.now()

    async def call_activity_expert():
        qa_messages = normalize_langchain_messages(state.get("activity_expert_messages", []))

        base_messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": ACTIVITY_EXPERT_USER_PROMPT.format(
                    activity_summary=state.get("activity_summary", ""),
                    competitions=json.dumps(state["competitions"], indent=2),
                    current_date=json.dumps(state["current_date"], indent=2),
                    analysis_context=state["analysis_context"],
                ),
            },
        ]

        return await handle_tool_calling_in_node(
            llm_with_tools=llm_with_structure,
            messages=base_messages + qa_messages,
            tools=tools,
            max_iterations=15,
        )

    async def node_execution():
        agent_output = await retry_with_backoff(
            call_activity_expert, AI_ANALYSIS_CONFIG, "Activity Expert Analysis with Tools"
        )

        execution_time = (datetime.now() - agent_start_time).total_seconds()
        plots, plot_storage_data, available_plots = create_plot_entries("activity_expert", plot_storage)

        log_node_completion("Activity expert", execution_time, len(available_plots))

        return {
            "activity_outputs": agent_output,
            "plots": plots,
            "plot_storage_data": plot_storage_data,
            "costs": [create_cost_entry("activity_expert", execution_time)],
            "available_plots": available_plots,
        }

    return await execute_node_with_error_handling(
        node_name="Activity expert",
        node_function=node_execution,
        error_message_prefix="Activity expert analysis failed",
    )
