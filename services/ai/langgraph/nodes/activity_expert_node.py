import json
import logging
from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from services.ai.ai_settings import AgentRole
from services.ai.tools.plotting import PlotStorage

from ..state.training_analysis_state import TrainingAnalysisState
from .expert_subgraph_factory import ExpertNodeConfig, create_expert_subgraph
from .node_base import (
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


async def activity_expert_node(state: TrainingAnalysisState, config: RunnableConfig) -> dict[str, list | str | dict]:
    logger.info("Starting activity expert analysis node (refactored)")

    plot_storage = PlotStorage(state["execution_id"])
    plotting_enabled = state.get("plotting_enabled", False)
    hitl_enabled = state.get("hitl_enabled", True)
    checkpointer = config.get("configurable", {}).get("checkpointer")
    
    logger.info(
        f"Activity expert: Plotting {'enabled' if plotting_enabled else 'disabled'}, "
        f"HITL {'enabled' if hitl_enabled else 'disabled'}"
    )

    system_prompt = (
        ACTIVITY_EXPERT_SYSTEM_PROMPT_BASE +
        get_workflow_context("activity") +
        (get_plotting_instructions("activity") if plotting_enabled else "") +
        (get_hitl_instructions("activity") if hitl_enabled else "")
    )

    user_prompt = ACTIVITY_EXPERT_USER_PROMPT.format(
        output_context=get_output_context_note(for_other_agents=True),
        activity_summary=state.get("activity_summary", ""),
        competitions=json.dumps(state["competitions"], indent=2),
        current_date=json.dumps(state["current_date"], indent=2),
        analysis_context=state["analysis_context"],
    )

    node_config = ExpertNodeConfig(
        node_name="activity_expert",
        display_name="Activity Expert",
        agent_role=AgentRole.ACTIVITY_EXPERT,
        system_prompt=system_prompt,
        user_prompt_template=user_prompt,
        state_result_key="activity_result",
        plotting_enabled=plotting_enabled,
        max_iterations=15,
    )

    subgraph = create_expert_subgraph(
        node_config,
        plot_storage if plotting_enabled else None,
        checkpointer=checkpointer
    )

    agent_start_time = datetime.now()

    async def node_execution():
        from langchain_core.messages import AIMessage

        from ..utils.subgraph_helpers import run_subgraph_until_done
        
        subgraph_thread_id = f"{state.get('execution_id', 'default')}_activity_expert"
        subgraph_config = {"configurable": {"thread_id": subgraph_thread_id}}
        
        # Resume if pending; otherwise seed fresh messages
        snap = subgraph.get_state(subgraph_config)
        input_state = None if snap.next else {
            **state,
            "messages": [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ],
        }

        # Run subgraph, draining all sequential HITL interrupts
        result = await run_subgraph_until_done(subgraph, input_state, subgraph_config)

        # Extract final AI message
        ai_msg = next(
            (m for m in reversed(result["messages"]) if isinstance(m, AIMessage)),
            None
        )
        activity_result = ai_msg.content if ai_msg else "No analysis produced"
        
        logger.info("Activity expert analysis completed")

        execution_time = (datetime.now() - agent_start_time).total_seconds()
        
        plots, plot_storage_data, available_plots = create_plot_entries("activity_expert", plot_storage)
        
        log_node_completion("Activity expert analysis", execution_time, len(available_plots))

        return {
            "activity_result": activity_result,
            "plots": plots,
            "plot_storage_data": plot_storage_data,
            "costs": [create_cost_entry("activity_expert", execution_time)],
            "available_plots": available_plots,
        }

    return await execute_node_with_error_handling(
        node_name="Activity expert analysis",
        node_function=node_execution,
        error_message_prefix="Activity expert analysis failed",
    )