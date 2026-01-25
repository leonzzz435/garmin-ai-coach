import json
import logging
from datetime import datetime

from services.ai.ai_settings import AgentRole
from services.ai.langgraph.schemas import PhysiologyExpertOutputs
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

PHYSIOLOGY_SYSTEM_PROMPT_BASE = """## Goal
Optimize recovery and adaptation through precise physiological analysis.
## Principles
- Holistic: View the body as an interconnected system.
- Temporal: Interpret signals across immediate and long-term timeframes.
- Actionable: Identify recovery windows and stress costs."""

PHYSIOLOGY_USER_PROMPT = """## Task
Analyze the physiology summary to assess recovery and adaptation.

## Constraints
- Focus on **internal state** (HRV, sleep, RHR, stress).
- Do NOT re-derive load metrics (Metrics Expert's job).
- Do NOT redesign training structure (Planner's job).
- Focus on **how the body is handling stress**.

## Inputs
### Physiology Summary
{data}
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
- **Context**: This feeds the **"Whole Athlete"** view (Summary & Synthesis). It acts as the "Internal Body Check".
- **Goal**: Provide a qualitative assessment of recovery and adaptation.
- **Freedom**: Highlight recovery costs, adaptation status, or internal signals.

### 2. `for_season_planner` (12-24 Weeks)
- **Context**: This informs **Long-Term Structural Decisions** (Macro-cycle).
- **Goal**: Inform the athlete's **"Absorptive Capacity"**.
- **Freedom**: Focus on long-term robustness, crash risks, and resilience.

### 3. `for_weekly_planner` (Next 28 Days)
- **Context**: This acts as the **"Traffic Light"** (readiness limiter) for the next block.
- **Goal**: Provide readiness guidance.
- **Freedom**: Speak in **readiness corridors** (e.g., "High readiness, go for overload" or "Sympathetic dominance, limit intensity")."""

PHYSIOLOGY_FINAL_CHECKLIST = """
## Final Checklist
- Use Signals/Evidence/Implications/Uncertainty per receiver.
- Stay within physiology domain only.
- No training structure redesign.
"""

async def physiology_expert_node(state: TrainingAnalysisState) -> dict[str, list | str | dict]:
    logger.info("Starting physiology expert analysis node")

    plot_storage = PlotStorage(state["execution_id"])
    plotting_enabled = state.get("plotting_enabled", False)
    hitl_enabled = state.get("hitl_enabled", True)

    logger.info(
        "Physiology expert: Plotting %s, HITL %s",
        "enabled" if plotting_enabled else "disabled",
        "enabled" if hitl_enabled else "disabled",
    )

    tools = configure_node_tools(
        agent_name="physiology",
        plot_storage=plot_storage,
        plotting_enabled=plotting_enabled,
    )

    system_prompt = (
        get_workflow_context("physiology")
        + PHYSIOLOGY_SYSTEM_PROMPT_BASE
        + (get_plotting_instructions("physiology") if plotting_enabled else "")
        + (get_hitl_instructions("physiology") if hitl_enabled else "")
        + PHYSIOLOGY_FINAL_CHECKLIST
    )

    base_llm = ModelSelector.get_llm(AgentRole.PHYSIOLOGY_EXPERT)
    llm_with_tools = base_llm.bind_tools(tools) if tools else base_llm
    llm_with_structure = llm_with_tools.with_structured_output(PhysiologyExpertOutputs)

    agent_start_time = datetime.now()

    async def call_physiology_analysis():
        qa_messages = normalize_langchain_messages(state.get("physiology_expert_messages", []))

        base_messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": PHYSIOLOGY_USER_PROMPT.format(
                    data=state.get("physiology_summary", "No physiology summary available"),
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
            call_physiology_analysis, AI_ANALYSIS_CONFIG, "Physiology Expert with Tools"
        )

        execution_time = (datetime.now() - agent_start_time).total_seconds()
        plots, plot_storage_data, available_plots = create_plot_entries("physiology", plot_storage)

        log_node_completion("Physiology expert analysis", execution_time, len(available_plots))

        return {
            "physiology_outputs": agent_output,
            "plots": plots,
            "plot_storage_data": plot_storage_data,
            "costs": [create_cost_entry("physiology", execution_time)],
            "available_plots": available_plots,
        }

    return await execute_node_with_error_handling(
        node_name="Physiology expert analysis",
        node_function=node_execution,
        error_message_prefix="Physiology expert analysis failed",
    )
