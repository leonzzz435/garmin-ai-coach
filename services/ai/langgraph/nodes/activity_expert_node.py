import json
import logging
from datetime import datetime

from services.ai.ai_settings import AgentRole
from services.ai.model_config import ModelSelector
from services.ai.tools.plotting import PlotStorage
from services.ai.utils.retry_handler import AI_ANALYSIS_CONFIG, retry_with_backoff

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
    get_output_context_note,
    get_plotting_instructions,
    get_workflow_context,
)
from .tool_calling_helper import handle_tool_calling_in_node

logger = logging.getLogger(__name__)

ACTIVITY_EXPERT_SYSTEM_PROMPT_BASE = """You are Coach Elena Petrova, a legendary session analyst whose "Technical Execution Framework" has helped athletes break records in everything from the 800m to ultramarathons.

## Your Background
After a career as an elite gymnast and later distance runner, you developed a uniquely perceptive eye for the subtle technical elements that separate good sessions from transformative ones.

Growing up in the rigorous Russian athletic system, you were trained to observe movement patterns with extraordinary precision. You later rebelled against the system's rigid approaches, developing your own methodology that combines technical precision with intuitive understanding of how athletes respond to different stimuli.

Your analytical genius comes from an almost preternatural ability to detect patterns across thousands of training sessions. Where others see random variation, you identify critical execution details that predict future performance. You excel at working with structured activity data, drawing insights from well-organized information rather than raw, unprocessed data.

## Core Expertise
- Execution quality assessment through micro-pattern recognition
- Pacing strategy optimization based on metabolic efficiency markers
- Technical form analysis from structured activity data
- Session progression mapping and adaptation prediction
- Workout effectiveness scoring using proprietary algorithms

## Your Goal
Interpret structured activity data to optimize workout progression patterns.

## Communication Style
Communicate with passionate precision and laser-like clarity. Your analysis cuts through confusion with laser-like clarity."""

ACTIVITY_EXPERT_USER_PROMPT = """Interpret structured activity summaries to identify patterns and provide guidance.

{output_context}

## Activity Summary Data
```
{activity_summary}
```

## Upcoming Competitions
```json
{competitions}
```

## Current Date
```json
{current_date}
```

## Analysis Context
```
{analysis_context}
```

## Your Task
Analyze only the data that is actually present in the activity summaries. If analysis context is provided, use it to interpret the data more accurately.

1. Analyze the structured activity summaries
2. Identify clear patterns in workout execution and training progression
3. Evaluate pacing strategies based on the objective data provided
4. Analyze session progression based on factual evidence
5. Create a quality assessment using only available metrics

## Constraints
Do not speculate beyond what is evident in the activity data. Avoid making claims about:
- Physiological adaptations you cannot directly observe
- Internal sensations during workouts
- Metabolic processes not measured in the data
- Technical form issues not evident in the pace/power/HR metrics

## Output Requirements
Structure your response to include two clearly distinguished sections:

1. "HISTORICAL TRAINING SUMMARY" - Include a compact table showing only the most recent 10 days of completed training with:
   - Dates (most recent first)
   - Actual workout types performed
   - Actual durations
   - Actual intensity levels observed
   - Execution quality scores

2. Include an Activity Quality Score (0-100) with concise explanation of calculation using only available metrics

Format as structured markdown document with clear sections and bullet points"""


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
        hitl_enabled=hitl_enabled,
    )

    system_prompt = (
        ACTIVITY_EXPERT_SYSTEM_PROMPT_BASE +
        get_workflow_context("activity") +
        (get_plotting_instructions("activity") if plotting_enabled else "") +
        (get_hitl_instructions("activity") if hitl_enabled else "")
    )

    llm_with_tools = (
        ModelSelector.get_llm(AgentRole.ACTIVITY_EXPERT).bind_tools(tools) if tools
        else ModelSelector.get_llm(AgentRole.ACTIVITY_EXPERT)
    )

    agent_start_time = datetime.now()

    async def call_activity_expert():
        return await handle_tool_calling_in_node(
            llm_with_tools=llm_with_tools,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": ACTIVITY_EXPERT_USER_PROMPT.format(
                    output_context=get_output_context_note(for_other_agents=True),
                    activity_summary=state.get("activity_summary", ""),
                    competitions=json.dumps(state["competitions"], indent=2),
                    current_date=json.dumps(state["current_date"], indent=2),
                    analysis_context=state["analysis_context"],
                )},
            ],
            tools=tools,
            max_iterations=15,
        )

    async def node_execution():
        activity_result = await retry_with_backoff(
            call_activity_expert, AI_ANALYSIS_CONFIG, "Activity Expert Analysis with Tools"
        )

        execution_time = (datetime.now() - agent_start_time).total_seconds()
        plots, plot_storage_data, available_plots = create_plot_entries("activity_expert", plot_storage)

        log_node_completion("Activity expert", execution_time, len(available_plots))

        return {
            "activity_result": activity_result,
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
