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


async def physiology_expert_node(state: TrainingAnalysisState, config: RunnableConfig) -> dict[str, list | str | dict]:
    logger.info("Starting physiology expert analysis node (refactored)")

    plot_storage = PlotStorage(state["execution_id"])
    plotting_enabled = state.get("plotting_enabled", False)
    hitl_enabled = state.get("hitl_enabled", True)
    checkpointer = config.get("configurable", {}).get("checkpointer")
    
    logger.info(
        f"Physiology expert: Plotting {'enabled' if plotting_enabled else 'disabled'}, "
        f"HITL {'enabled' if hitl_enabled else 'disabled'}"
    )

    system_prompt = (
        PHYSIOLOGY_SYSTEM_PROMPT_BASE +
        get_workflow_context("physiology") +
        (get_plotting_instructions("physiology") if plotting_enabled else "") +
        (get_hitl_instructions("physiology") if hitl_enabled else "")
    )

    user_prompt = PHYSIOLOGY_USER_PROMPT.format(
        output_context=get_output_context_note(for_other_agents=True),
        data=state.get("physiology_summary", "No physiology summary available"),
        competitions=json.dumps(state["competitions"], indent=2),
        current_date=json.dumps(state["current_date"], indent=2),
        analysis_context=state["analysis_context"],
    )

    node_config = ExpertNodeConfig(
        node_name="physiology_expert",
        display_name="Physiology Expert",
        agent_role=AgentRole.PHYSIOLOGY_EXPERT,
        system_prompt=system_prompt,
        user_prompt_template=user_prompt,
        state_result_key="physiology_result",
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
        from langgraph.types import interrupt as langgraph_interrupt
        
        subgraph_state = {
            **state,
            "messages": [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ],
        }

        subgraph_thread_id = f"{state.get('execution_id', 'default')}_physiology_expert"
        subgraph_config = {"configurable": {"thread_id": subgraph_thread_id}}
        result = None
        
        async for chunk in subgraph.astream(subgraph_state, config=subgraph_config, stream_mode="values"):
            result = chunk
        
        snapshot = subgraph.get_state(subgraph_config)
        if snapshot.next:
            for task in snapshot.tasks:
                if hasattr(task, "interrupts") and task.interrupts:
                    for intr in task.interrupts:
                        logger.info("Physiology expert: Propagating interrupt from subgraph")
                        langgraph_interrupt(intr.value)

        final_ai_message = next(
            (m for m in reversed(result["messages"]) if hasattr(m, "content") and not hasattr(m, "tool_call_id")),
            None
        )
        
        physiology_result = final_ai_message.content if final_ai_message else "No analysis produced"
        
        logger.info("Physiology expert analysis completed")

        execution_time = (datetime.now() - agent_start_time).total_seconds()
        
        plots, plot_storage_data, available_plots = create_plot_entries("physiology", plot_storage)
        
        log_node_completion("Physiology expert analysis", execution_time, len(available_plots))

        return {
            "physiology_result": physiology_result,
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