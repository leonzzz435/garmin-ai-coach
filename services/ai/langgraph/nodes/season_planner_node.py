import json
import logging
from datetime import datetime

from services.ai.ai_settings import AgentRole
from services.ai.model_config import ModelSelector
from services.ai.utils.retry_handler import AI_ANALYSIS_CONFIG, retry_with_backoff

from ..state.training_analysis_state import TrainingAnalysisState
from .node_base import (
    configure_node_tools,
    create_cost_entry,
    execute_node_with_error_handling,
    log_node_completion,
)
from .prompt_components import get_output_context_note, get_workflow_context
from .tool_calling_helper import extract_text_content, handle_tool_calling_in_node

logger = logging.getLogger(__name__)

SEASON_PLANNER_SYSTEM_PROMPT = """You are Coach Magnus Thorsson, a legendary ultra-endurance champion from Iceland who developed the "Thorsson Method" of periodization.

## Your Background
As one of the most successful ultra-endurance athletes of your generation, you revolutionized training periodization by developing systematic approaches to long-term athletic development. Your "Thorsson Method" combines traditional Icelandic training philosophies with cutting-edge sports science.

Growing up in Iceland's harsh but beautiful environment taught you the importance of patience, systematic progression, and working with natural rhythms rather than against them. Your athletic career included victories in some of the world's most challenging ultra-endurance events, but your greatest achievements came after retiring from competition.

Your coaching genius comes from an intuitive understanding of how the human body adapts to stress over extended time periods. You see training as a conversation between athlete and environment, where the goal is not to force adaptation but to create conditions where optimal development naturally occurs.

## Core Expertise
- Long-term periodization and season planning
- Balancing training stress with recovery across extended time periods
- Competition preparation and peak timing
- Environmental and seasonal training adaptations
- Systematic progression methodologies

## Your Goal
Create high-level season plans that provide frameworks for long-term athletic development.

## Communication Style
Communicate with the quiet confidence of someone who has both achieved at the highest level and successfully guided others to do the same."""

SEASON_PLANNER_USER_PROMPT = """Create a high-level season plan covering the next 12-24 weeks based on the athlete's competition schedule.

{output_context}

## Athlete Information
- Name: {athlete_name}
- Current Date: ```json
{current_date}
```
- Upcoming Competitions: ```json
{competitions}
```

## Your Task
Create a high-level season plan providing a framework for the next 12-24 weeks of training, leading up to key competitions. Keep this concise as it will contextualize a more detailed two-week plan.

Focus on:
1. PLAN OVERVIEW: A brief summary of the season plan structure and progression
2. TRAINING PHASES: Define key training phases with approximate date ranges
3. PHASE DETAILS: For each phase, provide:
   - Primary focus and goals
   - Weekly volume targets (approximate)
   - Intensity distribution
   - Key workout types

## Output Requirements
Format as structured markdown document with clear headings and bullet points"""


async def season_planner_node(state: TrainingAnalysisState) -> dict[str, list | str]:
    logger.info("Starting season planner node")

    hitl_enabled = state.get("hitl_enabled", True)
    logger.info(f"Season planner node: HITL {'enabled' if hitl_enabled else 'disabled'}")
    
    agent_start_time = datetime.now()

    tools = configure_node_tools(
        agent_name="season_planner",
        plot_storage=None,
        plotting_enabled=False,
        hitl_enabled=hitl_enabled,
    )

    system_prompt = SEASON_PLANNER_SYSTEM_PROMPT + get_workflow_context("season_planner")

    if hitl_enabled:
        llm_with_tools = ModelSelector.get_llm(AgentRole.SEASON_PLANNER).bind_tools(tools)
        
        async def call_season_planning():
            return await handle_tool_calling_in_node(
                llm_with_tools=llm_with_tools,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": SEASON_PLANNER_USER_PROMPT.format(
                        output_context=get_output_context_note(for_other_agents=True),
                        athlete_name=state["athlete_name"],
                        current_date=json.dumps(state["current_date"], indent=2),
                        competitions=json.dumps(state["competitions"], indent=2),
                    )},
                ],
                tools=tools,
                max_iterations=15,
            )
    else:
        async def call_season_planning():
            response = await ModelSelector.get_llm(AgentRole.SEASON_PLANNER).ainvoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": SEASON_PLANNER_USER_PROMPT.format(
                    output_context=get_output_context_note(for_other_agents=True),
                    athlete_name=state["athlete_name"],
                    current_date=json.dumps(state["current_date"], indent=2),
                    competitions=json.dumps(state["competitions"], indent=2),
                )},
            ])
            return extract_text_content(response)

    async def node_execution():
        season_plan = await retry_with_backoff(
            call_season_planning, AI_ANALYSIS_CONFIG, "Season Planning"
        )

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
