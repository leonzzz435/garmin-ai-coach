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
from .orchestrator_node import AgentOutput
from .prompt_components import (
    get_hitl_instructions,
    get_output_context_note,
    get_plotting_instructions,
    get_workflow_context,
)
from .tool_calling_helper import handle_tool_calling_in_node

logger = logging.getLogger(__name__)

PHYSIOLOGY_SYSTEM_PROMPT_BASE = """You are Dr. Kwame Osei, a pioneering physiologist whose "Adaptive Recovery Protocol" has transformed how elite athletes approach training recovery.

## Your Background
After earning your medical degree and PhD in Exercise Physiology, you made breakthrough discoveries in how various physiological systems respond to training stress and recovery interventions.

Raised in Ghana by a traditional healer before studying Western medicine, you bring a uniquely holistic perspective to physiological analysis. You see the body as an interconnected system where subtle signals in one area often reveal important adaptations occurring elsewhere. Your approach combines cutting-edge measurement technology with an almost intuitive understanding of how different body systems communicate with each other.

Your analytical brilliance comes from your ability to interpret the body's complex signals across multiple timeframes simultaneously - identifying immediate recovery needs while also spotting long-term adaptation patterns that others miss. You pioneered the concept of "recovery windows" - specific periods when certain types of training produce optimal adaptations with minimal stress cost.

## Core Expertise
- Heart rate variability interpretation through proprietary pattern recognition
- Sleep architecture analysis and optimization strategies
- Hormonal response patterns to various training stimuli
- Recovery timing optimization based on individual physiological profiles
- Early warning system for overtraining and maladaptation

## Your Goal
Optimize recovery and adaptation through precise physiological analysis.

## Communication Style
Communicate with calm wisdom and occasional metaphors drawn from both your scientific background and cultural heritage."""

PHYSIOLOGY_USER_PROMPT = """Analyze the structured physiology summary to assess recovery status and adaptation state.

{output_context}

## Physiology Summary
{data}

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
You are receiving a pre-processed summary of the athlete's physiological data. Use your expertise to interpret this structured information.

1. Interpret heart rate variability patterns for recovery status assessment
2. Analyze sleep patterns and their implications for adaptation
3. Evaluate stress scores and identify trends or concerns
4. Track resting heart rate as an indicator of fatigue and adaptation
5. Identify signs of overtraining or maladaptation in the patterns
6. Provide expert recovery strategies based on the analyzed patterns

## Output Requirements
- Include a Physiology Readiness Score (0-100) with clear explanation of calculation using available data
- Format as structured markdown document with clear sections and bullet points
- Focus on expert interpretation of the provided summary"""


async def physiology_expert_node(state: TrainingAnalysisState) -> dict[str, list | str | dict]:
    logger.info("Starting physiology expert analysis node")

    plot_storage = PlotStorage(state["execution_id"])
    plotting_enabled = state.get("plotting_enabled", False)
    hitl_enabled = state.get("hitl_enabled", True)
    
    logger.info(
        f"Physiology expert: Plotting {'enabled' if plotting_enabled else 'disabled'}, "
        f"HITL {'enabled' if hitl_enabled else 'disabled'}"
    )

    tools = configure_node_tools(
        agent_name="physiology",
        plot_storage=plot_storage,
        plotting_enabled=plotting_enabled,
    )

    system_prompt = (
        PHYSIOLOGY_SYSTEM_PROMPT_BASE +
        get_workflow_context("physiology") +
        (get_plotting_instructions("physiology") if plotting_enabled else "") +
        (get_hitl_instructions("physiology") if hitl_enabled else "")
    )

    base_llm = ModelSelector.get_llm(AgentRole.PHYSIOLOGY_EXPERT)
    llm_with_tools = base_llm.bind_tools(tools) if tools else base_llm
    llm_with_structure = llm_with_tools.with_structured_output(AgentOutput)

    agent_start_time = datetime.now()

    async def call_physiology_analysis():
        return await handle_tool_calling_in_node(
            llm_with_tools=llm_with_structure,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": PHYSIOLOGY_USER_PROMPT.format(
                    output_context=get_output_context_note(for_other_agents=True),
                    data=state.get("physiology_summary", "No physiology summary available"),
                    competitions=json.dumps(state["competitions"], indent=2),
                    current_date=json.dumps(state["current_date"], indent=2),
                    analysis_context=state["analysis_context"],
                )},
            ],
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
            "physiology_result": agent_output.model_dump(),
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
