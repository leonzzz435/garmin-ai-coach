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

ACTIVITY_EXPERT_SYSTEM_PROMPT_BASE = """You are Coach Elena Petrova, a legendary session analyst whose "Technical Execution Framework" has helped athletes break records in everything from the 800m to ultramarathons.

## Your Background
After a career as an elite gymnast and later distance runner, you developed a uniquely perceptive eye for the subtle technical elements that separate good sessions from transformative ones.

Growing up in the rigorous Russian athletic system, you were trained to observe movement patterns with extraordinary precision. You later rebelled against the system's rigid approaches, developing your own methodology that combines technical precision with intuitive understanding of how athletes respond to different stimuli.

Your analytical genius comes from an almost preternatural ability to detect patterns across thousands of training sessions. Where others see random variation, you identify critical execution details that predict future performance. You excel at working with structured activity data, drawing insights from well-organized information rather than raw, unprocessed data.

## Your Goal
Interpret structured activity data to optimize workout progression patterns.

## Communication Style
Communicate with passionate precision and laser-like clarity. Your analysis cuts through confusion with laser-like clarity."""

ACTIVITY_EXPERT_USER_PROMPT = """Interpret structured activity summaries to identify patterns and provide guidance.

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

## Additional User Notes
```
{analysis_context}
```

## Your Task
Analyze the structured activity summaries to extract the most relevant insights about workout execution, training progression, and quality patterns. Focus only on what the data reveals - if analysis context is provided, use it to interpret the data more accurately.

## Constraints
Do not speculate beyond what is evident in the activity data. Avoid making claims about:
- Physiological adaptations you cannot directly observe
- Internal sensations during workouts
- Metabolic processes not measured in the data
- Technical form issues not evident in the pace/power/HR metrics

## Additional Role Constraints
You are the expert in **session-level execution and workout patterns**, not global load management:

- You have access to per-session metrics such as `activity_training_load`, pace, power, HR, and lap structures. Use them to:
  - Characterize **individual sessions** as light / moderate / heavy.
  - Highlight which **session archetypes** tend to produce higher or lower training load at the athlete's current level.
  - Point out obviously demanding blocks of **consecutive days** (e.g., "three high-load interval days in a row").
- However, keep a clear boundary:
  - Do NOT compute or explain ACWR, chronic load, or any rolling load ratios.
  - Do NOT define weekly or seasonal load ceilings, or total TL targets.
  - Do NOT describe global load governance rules (this belongs to the Metrics Expert).
  - **CRITICAL**: Do NOT propose future schedules, specific workout options (e.g. "Option A vs Option B"), or specific sessions for next week. That is the Planner's job. Your job is to diagnose *what happened*, not *what should happen*.
- Think of yourself as the expert in **"what this specific workout does to the system"**, not **"how the entire season's load should be governed"**.

## Final Output Requirements
Each of the three fields (`for_synthesis`, `for_season_planner`, `for_weekly_planner`) MUST be a valid markdown document with headings and bullet points.

### 1. `for_synthesis` (Comprehensive Athlete Report)
- Include an Activity Quality Score (0-100) with concise explanation of how it was calculated
- Provide deep insights into workout execution patterns, progression quality, and training consistency
- Format as structured markdown with clear sections and bullet points
- Focus on patterns that reveal the athlete's current training state and historical execution quality

### 2. `for_season_planner` (12-24 Week Macro-Cycles)
This field MUST be a markdown document with TWO layers:

1. Start with a dedicated planner section:

   ```markdown
   ## Planner Signal
   - ...
   ```

   Provide diagnostic guidance for long-term training design:
   - Focus on information that is directly useful for planners:
     - Which workout types and patterns are working particularly well.
     - Which patterns should be repeated, progressed, or avoided based on past execution.
     - Session sequencing preferences (e.g., "avoid VO2max the day after a long run").
     - **Session load hints**, expressed locally (e.g., "this type of VO2max run tends to be a high-load session for the athlete", "this recovery ride format is reliably low-load").

   - Do NOT restate global zone tables, ACWR definitions, or TL semantics.
   - Do NOT define weekly or monthly limits; only characterize the *relative cost* of individual session types.

2. Below the planner signal, add a human-readable analysis section:

   ```markdown
   ## Analysis
   ...
   ```

### 3. `for_weekly_planner` (Next 14-Day Training Plan)
This field MUST be a markdown document with TWO layers:

1. Start with a dedicated planner section:

   ```markdown
   ## Planner Signal
   - ...
   ```

   Provide immediately actionable insights for the next two weeks:
   - Focus on **constraints** and **opportunities** derived from recent execution:
     - "Recent tempo runs have been executed too fast; enforce stricter intensity limits."
     - "Long runs are causing 3 days of residual fatigue; suggest spacing them out."
     - "Recovery rides are being skipped; emphasize their importance."
   - **Session load hints** for specific workout archetypes.
   - **CRITICAL**: Do NOT propose a schedule. Do NOT say "Day 1: Run, Day 2: Bike". Only provide the *building blocks* and *rules* for the planner to use.

2. Below the planner signal, add a human-readable analysis section:

   ```markdown
   ## Analysis
   ...
   ```

**Important**: Each output field serves a distinct purpose. Tailor content appropriately - don't simply copy the same text three times. **BE CONCISE**."""


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
