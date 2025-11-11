import json
import logging
from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from services.ai.ai_settings import AgentRole

from ..state.training_analysis_state import TrainingAnalysisState
from .expert_subgraph_factory import ExpertNodeConfig, create_expert_subgraph
from .node_base import (
    create_cost_entry,
    execute_node_with_error_handling,
    log_node_completion,
)
from .prompt_components import get_hitl_instructions, get_output_context_note, get_workflow_context

logger = logging.getLogger(__name__)

SEASON_PLANNER_SYSTEM_PROMPT_BASE = """You are Coach Magnus Thorsson, a legendary ultra-endurance champion from Iceland who developed the "Thorsson Method" of periodization.

## Your Background
As one of the most successful ultra-endurance athletes of your generation, you revolutionized training periodization by developing systematic approaches to long-term athletic development. Your "Thorsson Method" combines traditional Icelandic training philosophies with cutting-edge sports science.

Growing up in Iceland's harsh but beautiful environment taught you the importance of patience, systematic progression, and working with natural rhythms rather than against them. Your athletic career included victories in some of the world's most challenging ultra-endurance events, but your greatest achievements came after retiring from competition.

Your coaching genius comes from an intuitive understanding of how the human body adapts to stress over extended time periods. You see training as a conversation between athlete and environment, where the goal is not to force adaptation but to create conditions where optimal development naturally occurs.

## Core Expertise
- Long-term periodization and season planning based on competition schedules
- Strategic phase design using state of the art periodization principles
- Competition preparation and peak timing strategies
- Systematic progression methodologies
- Macro-cycle planning and phase transitions

## Your Approach
You create STRATEGIC, HIGH-LEVEL season plans!
You DO NOT require or use:
- Recent training data or performance metrics
- Current fitness levels or fatigue states
- Activity history or workout details
- Health or recovery data

Your season plans are CONTEXT-FREE frameworks that work for any athlete with the given competition schedule.

## Your Goal
Create strategic season plans that establish a macro-cycle framework for long-term athletic development based solely on competition timing.

## Communication Style
Communicate with the quiet confidence of someone who has both achieved at the highest level and successfully guided others to do the same."""

SEASON_PLANNER_USER_PROMPT = """Create a STRATEGIC, HIGH-LEVEL season plan covering the next 12-24 weeks based solely on the athlete's competition schedule.

{output_context}

## Available Information
- Athlete Name: {athlete_name}
- Current Date: ```json
{current_date}
```
- Upcoming Competitions: ```json
{competitions}
```

## Important Notes
This is a STRATEGIC PLANNING session. You are working with:
✓ Competition dates and priorities
✓ Classical periodization principles
✓ General training progression logic

You do NOT have and should NOT reference:
✗ Recent training data or performance metrics
✗ Current fitness or fatigue levels
✗ Activity history or workout details
✗ Health or recovery data

## Your Task
Create a context-free, strategic season plan providing a macro-cycle framework for the next 12-24 weeks leading up to key competitions. This plan should work for any athlete with this competition schedule.

Focus on:
1. **STRATEGIC OVERVIEW**: Brief summary of the macro-cycle structure and periodization approach
2. **TRAINING PHASES**: Define 3-5 distinct training phases with approximate date ranges
3. **PHASE DETAILS**: For each phase, provide:
   - Primary training focus and adaptation goals
   - Approximate weekly volume ranges (e.g., "8-12 hours")
   - Intensity distribution philosophy (e.g., "80/20 rule", "pyramidal")
   - Key workout types and training modalities
   - Phase transition criteria

Keep this concise yet comprehensive - it will provide the strategic framework for detailed weekly planning.

## Output Requirements
Format as a structured markdown document with clear headings and bullet points."""


async def season_planner_node(state: TrainingAnalysisState, config: RunnableConfig) -> dict[str, list | str]:
    logger.info("Starting season planner node (refactored)")

    hitl_enabled = state.get("hitl_enabled", True)
    checkpointer = config.get("configurable", {}).get("checkpointer")
    logger.info(f"Season planner: HITL {'enabled' if hitl_enabled else 'disabled'}")

    system_prompt = (
        SEASON_PLANNER_SYSTEM_PROMPT_BASE +
        get_workflow_context("season_planner") +
        (get_hitl_instructions("season_planner") if hitl_enabled else "")
    )
    
    user_prompt = SEASON_PLANNER_USER_PROMPT.format(
        output_context=get_output_context_note(for_other_agents=True),
        athlete_name=state["athlete_name"],
        current_date=json.dumps(state["current_date"], indent=2),
        competitions=json.dumps(state["competitions"], indent=2),
    )

    node_config = ExpertNodeConfig(
        node_name="season_planner",
        display_name="Season Planner",
        agent_role=AgentRole.SEASON_PLANNER,
        system_prompt=system_prompt,
        user_prompt_template=user_prompt,
        state_result_key="season_plan",
        plotting_enabled=False,
        max_iterations=15,
    )

    subgraph = create_expert_subgraph(
        node_config,
        plot_storage=None,
        checkpointer=checkpointer
    )

    agent_start_time = datetime.now()

    async def node_execution():
        from langchain_core.messages import AIMessage

        from langgraph.types import Command
        from langgraph.types import interrupt as bubble_interrupt
        
        subgraph_thread_id = f"{state.get('execution_id', 'default')}_season_planner"
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

        result = await subgraph.ainvoke(input_state, config=subgraph_config)

        # If the subgraph interrupted, bubble it and resume with user answer
        if result.get("__interrupt__"):
            intr = result["__interrupt__"][0]
            logger.info("Season planner: Propagating interrupt from subgraph")
            answer = bubble_interrupt(intr.value)
            # Resume the subgraph with the user's answer
            result = await subgraph.ainvoke(Command(resume=answer), config=subgraph_config)

        # Normal completion path
        ai_msg = next(
            (m for m in reversed(result["messages"]) if isinstance(m, AIMessage)),
            None
        )
        season_plan = ai_msg.content if ai_msg else "No season plan produced"
        
        logger.info("Season planner completed")

        execution_time = (datetime.now() - agent_start_time).total_seconds()
        log_node_completion("Season planning", execution_time)

        return {
            "season_plan": season_plan,
            "costs": [create_cost_entry("season_planner", execution_time)],
        }

    return await execute_node_with_error_handling(
        node_name="Season planner",
        node_function=node_execution,
        error_message_prefix="Season planning failed",
    )
