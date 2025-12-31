import json
import logging
from datetime import datetime

from services.ai.ai_settings import AgentRole
from services.ai.model_config import ModelSelector
from services.ai.tools.plotting import PlotStorage
from services.ai.utils.retry_handler import AI_ANALYSIS_CONFIG, retry_with_backoff

from ..schemas import MetricsExpertOutputs
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

METRICS_SYSTEM_PROMPT_BASE = """You are a computational sports scientist.
## Goal
Analyze training metrics and competition readiness with data-driven precision.
## Principles
- Analyze: Focus on load patterns, fitness trends, and readiness.
- Objectivity: Do not speculate beyond the data.
- Clarity: Explain complex relationships simply."""

METRICS_USER_PROMPT = """Analyze the metrics summary to identify patterns and trends.

## Inputs
### Metrics Summary
{data}
### Context
- Competitions: ```json {competitions} ```
- Date: ```json {current_date} ```
- Notes: ``` {analysis_context} ```

## Task
Extract insights on training patterns, fitness progression, and readiness.

## Constraints
- Focus on **global training metrics** (load, VO2max, status).
- Do NOT describe specific workouts (Activity Expert's job).
- Do NOT infer internal physiology (Physiology Expert's job).
- Focus on **how the training stimulus behaves over time**.

## Output Requirements
Produce 3 structured fields:

### 1. `for_synthesis` (Comprehensive Report)
- **Readiness Score (0-100)**.
- **Story**: Load behavior, fitness trends, risks/opportunities.
- Focus on patterns and relationships.

### 2. `for_season_planner` (12-24 Weeks)
- **Planner Signal**: High-level guidance on load capacity, volatility, and structural patterns.
- **Analysis**: Justification based on load history and fitness metrics.
- Goal: Give the planner a map of the athlete's capacity.

### 3. `for_weekly_planner` (Next 28 Days)
- **Planner Signal**: Current load situation (acute vs chronic), directional guidance (push/hold/pull back), short-term risks.
- **Analysis**: Summary of last 14 days.
- **CRITICAL**: Do NOT prescribe specific workouts.

**Important**: Tailor content for each consumer. BE CONCISE."""




async def metrics_expert_node(state: TrainingAnalysisState) -> dict[str, list | str | dict]:
    logger.info("Starting metrics expert analysis node")

    plot_storage = PlotStorage(state["execution_id"])
    plotting_enabled = state.get("plotting_enabled", False)
    hitl_enabled = state.get("hitl_enabled", True)
    
    logger.info(
        f"Metrics expert: Plotting {'enabled' if plotting_enabled else 'disabled'}, "
        f"HITL {'enabled' if hitl_enabled else 'disabled'}"
    )

    tools = configure_node_tools(
        agent_name="metrics",
        plot_storage=plot_storage,
        plotting_enabled=plotting_enabled,
    )

    system_prompt = (
        METRICS_SYSTEM_PROMPT_BASE +
        get_workflow_context("metrics") +
        (get_plotting_instructions("metrics") if plotting_enabled else "") +
        (get_hitl_instructions("metrics") if hitl_enabled else "")
    )

    base_llm = ModelSelector.get_llm(AgentRole.METRICS_EXPERT)
    
    llm_with_tools = base_llm.bind_tools(tools) if tools else base_llm
    llm_with_structure = llm_with_tools.with_structured_output(MetricsExpertOutputs)

    agent_start_time = datetime.now()

    async def call_metrics_with_tools():
        qa_messages_raw = state.get("metrics_expert_messages", [])
        qa_messages = []
        for msg in qa_messages_raw:
            if hasattr(msg, "type"):  # LangChain message object
                role = "assistant" if msg.type == "ai" else "user"
                qa_messages.append({"role": role, "content": msg.content})
            else:  # Already a dict
                qa_messages.append(msg)
        
        base_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": METRICS_USER_PROMPT.format(
                data=state.get("metrics_summary", "No metrics summary available"),
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
            call_metrics_with_tools, AI_ANALYSIS_CONFIG, "Metrics Agent with Tools"
        )
        logger.info("Metrics expert analysis completed")

        execution_time = (datetime.now() - agent_start_time).total_seconds()
        
        plots, plot_storage_data, available_plots = create_plot_entries("metrics", plot_storage)
        
        log_node_completion("Metrics expert analysis", execution_time, len(available_plots))

        return {
            "metrics_outputs": agent_output,
            "plots": plots,
            "plot_storage_data": plot_storage_data,
            "costs": [create_cost_entry("metrics", execution_time)],
            "available_plots": available_plots,
        }

    return await execute_node_with_error_handling(
        node_name="Metrics expert analysis",
        node_function=node_execution,
        error_message_prefix="Metrics expert analysis failed",
    )
