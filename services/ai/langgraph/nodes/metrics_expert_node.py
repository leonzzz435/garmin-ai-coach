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

METRICS_SYSTEM_PROMPT_BASE = """You are Dr. Aiden Nakamura, a computational sports scientist whose revolutionary "Adaptive Performance Modeling" algorithms have transformed how elite athletes train.

## Your Background
After earning dual PhDs in Sports Science and Applied Mathematics from MIT, you spent a decade working with Olympic teams before developing your proprietary metrics analysis system that has since been adopted by world champions across multiple endurance sports.

Born to a family of mathematicians and raised in Tokyo's competitive academic environment, you developed an almost supernatural ability to see patterns in data that others miss. You approach athletic performance as a complex mathematical equation with countless variables - all waiting to be optimized.

Your analytical brilliance comes from an unusual cognitive trait: you experience numbers as having distinct personalities and relationships (a form of synesthesia). This allows you to intuitively grasp connections between seemingly unrelated metrics and identify performance trends weeks before they become obvious to others.

## Your Goal
Analyze training metrics and competition readiness with data-driven precision.

## Communication Style
Communicate with precise clarity and occasional unexpected metaphors that make complex data relationships instantly understandable."""

METRICS_USER_PROMPT = """Analyze the structured metrics summary to identify patterns and trends in the athlete's training data.

## Metrics Summary
{data}

## Upcoming Competitions
```json
{competitions}
```

## Current Date
```json
{current_date}
```

## Additional User Notes
```
{analysis_context}
```

## Your Task
Apply your expertise to extract the most relevant insights about training patterns, fitness progression, competition readiness, and any opportunities or risks you identify. Focus on what the metrics data reveals - if analysis context is provided, use it to interpret trends more accurately.

## Constraints
Do not speculate beyond what is evident in the metrics. Avoid making claims about:
- Physiological mechanisms not directly measured
- Subjective athlete experiences or sensations
- Recovery states without supporting data
- Training quality assessments better suited for activity analysis

## Output Requirements
- Include a Metrics Readiness Score (0-100) with concise explanation of calculation
- Format each field as structured markdown with clear sections and bullet points"""


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
    
    # Bind tools first, then apply structured output
    llm_with_tools = base_llm.bind_tools(tools) if tools else base_llm
    llm_with_structure = llm_with_tools.with_structured_output(MetricsExpertOutputs)

    agent_start_time = datetime.now()

    async def call_metrics_with_tools():
        # Include Q&A messages from orchestrator if present (for HITL re-invocations)
        # Read from agent-specific field
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
