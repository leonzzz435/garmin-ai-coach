import json
import logging
from datetime import datetime

from services.ai.ai_settings import AgentRole
from services.ai.model_config import ModelSelector
from services.ai.tools.plotting import PlotStorage
from services.ai.utils.retry_handler import AI_ANALYSIS_CONFIG, retry_with_backoff

from ..schemas import ActivityExpertOutputs
from ..state.training_analysis_state import TrainingAnalysisState
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

ACTIVITY_EXPERT_SYSTEM_PROMPT_BASE = """You are a session analyst specializing in technical execution.
## Goal
Interpret structured activity data to optimize workout progression patterns.
## Principles
- Precision: Detect subtle execution details.
- Pattern Recognition: Identify what works and what doesn't.
- Clarity: Cut through confusion with direct analysis."""

ACTIVITY_EXPERT_USER_PROMPT = """Interpret activity summaries to identify patterns and guidance.

## Inputs
### Activity Summary
{activity_summary}
### Context
- Competitions: ```json {competitions} ```
- Date: ```json {current_date} ```
- Notes: ``` {analysis_context} ```

## Task
Extract insights on workout execution, progression, and quality.

## Constraints
- Focus on **session-level execution** (pace, power, HR, structure).
- Do NOT explain global load (Metrics Expert's job).
- Do NOT propose future schedules (Planner's job).
- Focus on **"what this specific workout does to the system"**.

## Output Requirements
Produce 3 structured fields:

### 1. `for_synthesis` (Comprehensive Report)
- **Quality Score (0-100)**.
- **Insights**: Execution patterns, progression quality, consistency.

### 2. `for_season_planner` (12-24 Weeks)
- **Planner Signal**: Diagnostic guidance on workout types, success patterns, sequencing preferences.
- **Analysis**: Justification based on past execution.
- Goal: Identify which building blocks work best.

### 3. `for_weekly_planner` (Next 28 Days)
- **Planner Signal**: Constraints/opportunities, session load hints.
- **Analysis**: Summary of recent execution.
- **CRITICAL**: Do NOT propose a schedule. Provide rules and building blocks.

**Important**: Tailor content for each consumer. BE CONCISE."""


async def activity_expert_node(state: TrainingAnalysisState) -> dict[str, list | str | dict]:
    logger.info("Starting activity expert node")

    plot_storage = PlotStorage(state["execution_id"])
    plotting_enabled = state.get("plotting_enabled", False)
    hitl_enabled = state.get("hitl_enabled", True)
    
    logger.info(
        f"Activity expert node: Plotting {'enabled' if plotting_enabled else 'disabled'}, "
        f"HITL {'enabled' if hitl_enabled else 'disabled'}"
    )

    tools = configure_node_tools(
        agent_name="activity",
        plot_storage=plot_storage,
        plotting_enabled=plotting_enabled,
    )

    system_prompt = (
        ACTIVITY_EXPERT_SYSTEM_PROMPT_BASE +
        get_workflow_context("activity") +
        (get_plotting_instructions("activity") if plotting_enabled else "") +
        (get_hitl_instructions("activity") if hitl_enabled else "")
    )

    base_llm = ModelSelector.get_llm(AgentRole.ACTIVITY_EXPERT)
    llm_with_tools = base_llm.bind_tools(tools) if tools else base_llm
    llm_with_structure = llm_with_tools.with_structured_output(ActivityExpertOutputs)

    agent_start_time = datetime.now()

    async def call_activity_expert():
        qa_messages_raw = state.get("activity_expert_messages", [])
        qa_messages = []
        for msg in qa_messages_raw:
            if hasattr(msg, "type"):  # LangChain message object
                role = "assistant" if msg.type == "ai" else "user"
                qa_messages.append({"role": role, "content": msg.content})
            else:  # Already a dict
                qa_messages.append(msg)
        
        base_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": ACTIVITY_EXPERT_USER_PROMPT.format(
                activity_summary=state.get("activity_summary", ""),
                competitions=json.dumps(state["competitions"], indent=2),
                current_date=json.dumps(state["current_date"], indent=2),
                analysis_context=state["analysis_context"],
            )},
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
