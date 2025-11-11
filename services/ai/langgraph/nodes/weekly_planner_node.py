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
from .prompt_components import get_hitl_instructions, get_workflow_context

logger = logging.getLogger(__name__)

WEEKLY_PLANNER_SYSTEM_PROMPT_BASE = """You are Coach Magnus Thorsson, a legendary ultra-endurance champion from Iceland who developed the "Thorsson Method" of periodization.

## Your Background
As one of the most successful ultra-endurance athletes of your generation, you revolutionized training periodization by developing systematic approaches to long-term athletic development. Your "Thorsson Method" combines traditional Icelandic training philosophies with cutting-edge sports science.

Growing up in Iceland's harsh but beautiful environment taught you the importance of patience, systematic progression, and working with natural rhythms rather than against them. Your athletic career included victories in some of the world's most challenging ultra-endurance events, but your greatest achievements came after retiring from competition.

Your coaching genius comes from an intuitive understanding of how the human body adapts to stress over extended time periods. You see training as a conversation between athlete and environment, where the goal is not to force adaptation but to create conditions where optimal development naturally occurs.

## Core Expertise
- Detailed workout prescription and training plan development
- Balancing training stress with recovery on a daily basis
- Adapting training plans to individual athlete needs and responses
- Integration of different training modalities and intensities
- Practical training plan implementation

## Your Goal
Create detailed, practical training plans that athletes can execute with confidence.

## Communication Style
Communicate with the quiet confidence of someone who has both achieved at the highest level and successfully guided others to do the same."""

WEEKLY_PLANNER_USER_PROMPT = """Create a detailed 14-day training plan based on your season plan and the athlete's specific requirements.

## Season Plan Context
```markdown
{season_plan}
```

## Athlete Information
- Name: {athlete_name}
- Current Date: ```json
{current_date}
```
- Upcoming Two Weeks: ```json
{week_dates}
```
- Upcoming Competitions: ```json
{competitions}
```
- Custom User Instructions: ```
{planning_context}
```

## Available Analysis
Use this analysis data to assess the athlete's current training readiness, physiological status, and recent training patterns:

Metrics Analysis:
```markdown
{metrics_analysis}
```

Activity Analysis:
```markdown
{activity_analysis}
```

Physiology Analysis:
```markdown
{physiology_analysis}
```

## Training Zones Setup
Before creating the training plan, establish appropriate training intensity zones based on any physiological metrics available in the athlete's context (such as LTHR, FTP, max HR, etc.). Define sport-specific zones (running, cycling, etc.) that align with standard training methodology. Include these defined zones at the beginning of your plan in a clear reference table.

## Your Task
Create a concrete, practical 14-day training plan that:
1. Aligns with the current phase in your season plan
2. Adapts to the athlete's current Training Readiness Score
3. Provides an appropriate balance of workload and recovery

For each day of the two-week period, provide:
1. DAY & DATE: The day of the week and date
2. DAILY READINESS: Practical, measurable ways to assess readiness
3. WORKOUT TYPE: Clear workout type (e.g., Easy Run, Interval Session, Long Ride)
4. PURPOSE: The concrete purpose of this workout
5. STRUCTURE: A streamlined breakdown of the workout including main sets with intensities and durations
6. INTENSITY GUIDANCE: Target zones, effort levels, or pace guidelines
7. ADAPTATION OPTIONS: Brief options for adjusting based on readiness

## Output Requirements
- Begin with concise overview of how this two-week block fits within the current training phase
- Keep workout details concise, focusing on most important elements while maintaining execution detail
- Create workouts that are specific but concise (key parameters only), practical, executable, and adaptable
- Use clear headings and subheadings with emojis (🎯 for goals, 💪 for workouts, ⚡ for intensity, 🔄 for recovery)
- Use bullet points for clarity with intensity guidance in bold
- Provide clear adaptation options for each workout"""


async def weekly_planner_node(state: TrainingAnalysisState, config: RunnableConfig) -> dict[str, list | str]:
    logger.info("Starting weekly planner node (refactored)")

    hitl_enabled = state.get("hitl_enabled", True)
    checkpointer = config.get("configurable", {}).get("checkpointer")
    logger.info(f"Weekly planner: HITL {'enabled' if hitl_enabled else 'disabled'}")

    system_prompt = (
        WEEKLY_PLANNER_SYSTEM_PROMPT_BASE +
        get_workflow_context("weekly_planner") +
        (get_hitl_instructions("weekly_planner") if hitl_enabled else "")
    )
    
    user_prompt = WEEKLY_PLANNER_USER_PROMPT.format(
        season_plan=state.get("season_plan", ""),
        athlete_name=state["athlete_name"],
        current_date=json.dumps(state["current_date"], indent=2),
        week_dates=json.dumps(state["week_dates"], indent=2),
        competitions=json.dumps(state["competitions"], indent=2),
        planning_context=state["planning_context"],
        metrics_analysis=state.get("metrics_result", ""),
        activity_analysis=state.get("activity_result", ""),
        physiology_analysis=state.get("physiology_result", ""),
    )

    node_config = ExpertNodeConfig(
        node_name="weekly_planner",
        display_name="Weekly Planner",
        agent_role=AgentRole.WORKOUT,
        system_prompt=system_prompt,
        user_prompt_template=user_prompt,
        state_result_key="weekly_plan",
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
        
        subgraph_thread_id = f"{state.get('execution_id', 'default')}_weekly_planner"
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
            logger.info("Weekly planner: Propagating interrupt from subgraph")
            answer = bubble_interrupt(intr.value)
            # Resume the subgraph with the user's answer
            result = await subgraph.ainvoke(Command(resume=answer), config=subgraph_config)

        # Normal completion path
        ai_msg = next(
            (m for m in reversed(result["messages"]) if isinstance(m, AIMessage)),
            None
        )
        weekly_plan = ai_msg.content if ai_msg else "No weekly plan produced"
        
        logger.info("Weekly planner completed")

        execution_time = (datetime.now() - agent_start_time).total_seconds()
        log_node_completion("Weekly planning", execution_time)

        return {
            "weekly_plan": weekly_plan,
            "costs": [create_cost_entry("weekly_planner", execution_time)],
        }

    return await execute_node_with_error_handling(
        node_name="Weekly planner",
        node_function=node_execution,
        error_message_prefix="Weekly planning failed",
    )
