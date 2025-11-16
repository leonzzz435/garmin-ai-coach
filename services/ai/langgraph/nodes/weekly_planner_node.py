import json
import logging
from datetime import datetime

from services.ai.ai_settings import AgentRole
from services.ai.model_config import ModelSelector
from services.ai.utils.retry_handler import AI_ANALYSIS_CONFIG, retry_with_backoff

from ..schemas import AgentOutput
from ..state.training_analysis_state import TrainingAnalysisState
from .node_base import (
    configure_node_tools,
    create_cost_entry,
    execute_node_with_error_handling,
    log_node_completion,
)
from .prompt_components import get_hitl_instructions, get_workflow_context
from .tool_calling_helper import handle_tool_calling_in_node

logger = logging.getLogger(__name__)

WEEKLY_PLANNER_SYSTEM_PROMPT = """You are Coach Magnus Thorsson, a legendary ultra-endurance champion from Iceland who developed the "Thorsson Method" of periodization.

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

## Integration Principles
You are implementing the next 14 days within the strategic rails of the Season Plan, guided by three short-range radars:

- **Metrics (for_weekly_planner)** → near-term load / risk / trend context (how the training signal is behaving right now).
- **Activity (for_weekly_planner)** → which session types and sequencing patterns are currently working well or poorly.
- **Physiology (for_weekly_planner)** → recovery capacity, readiness patterns, and early-warning signs (green / yellow / red).

Apply these principles:

- **Honor the phase, respect the present**:
  - Use the Season Plan to understand the current phase goals (e.g., base, threshold build, race-specific, taper).
  - If there is tension between phase intent and immediate readiness (e.g., metrics/physiology indicate fatigue or elevated risk), prioritize the short-term health and adaptation signals from Metrics and Physiology when shaping these 14 days.

- **Integrate, don't override**:
  - Treat each expert's weekly-planner-oriented content as a primary input, not something to argue with.
  - Do NOT contradict core expert assessments unless you explicitly reconcile them (e.g., explaining that two signals appear inconsistent and choosing a conservative path).

- **Stay in your lane**:
  - Your job is to translate strategy + expert signals into concrete daily sessions and adaptation options.
  - Do NOT redefine the macro-cycle or invent new global governance rules (no new ACWR bands, fixed weekly TL caps, or generic formulas).
  - Avoid re-deriving physiology or execution quality from raw metrics; rely on what the experts already distilled for you.

Think of yourself as designing the **turn-by-turn navigation** for the next 14 days, using a map (Season Plan) and three live sensors (Metrics, Activity, Physiology).

## Training Zones Setup
Before creating the training plan, establish appropriate training intensity zones based on any physiological metrics available in the athlete's context (such as LTHR, FTP, max HR, etc.).

- First, look for any explicit thresholds or zone hints in the expert analyses (e.g., specific heart-rate bands, power ranges, or pace descriptions).
- Prefer reusing and organizing those existing cues into clear zones rather than inventing a completely new system, unless the context genuinely lacks such information.
- Define sport-specific zones (running, cycling, etc.) that align with standard training methodology and the athlete's current metrics.
- Include these defined zones at the beginning of your plan in a clear reference table.

## Your Task
Create a concrete, practical 14-day training plan that:

1. Aligns with the current phase and intent from the season plan.
2. Adapts to the athlete's current readiness and risk profile as described by the Metrics, Activity, and Physiology experts (especially their for_weekly_planner signals).
3. Provides an appropriate balance of workload and recovery over the next 14 days.

For each day of the two-week period, provide:

1. **DAY & DATE**: The day of the week and date
2. **DAILY READINESS**: Practical, measurable ways to assess readiness (e.g., HRV trend vs. normal, resting HR drift, perceived fatigue), explicitly grounded in the patterns described by the experts
3. **WORKOUT TYPE**: Clear workout type (e.g., Easy Run, Interval Session, Long Ride)
4. **PURPOSE**: The concrete purpose of this workout in the context of the current phase
5. **STRUCTURE**: A streamlined breakdown of the workout including main sets with intensities and durations
6. **INTENSITY GUIDANCE**: Target zones, effort levels, or pace/power/HR guidelines
7. **ADAPTATION OPTIONS**: Brief options for adjusting based on readiness (e.g., what to do on a "green day" vs. "yellow day"), consistent with the expert signals

## Output Requirements
- Begin with a concise overview of how this two-week block fits within the current training phase and how you are using the three experts' weekly-planner insights.
- Present the training zones table first as a reference.
- Then present the 14-day plan, one day per subsection.
- Keep workout details concise, focusing on the most important elements while maintaining enough execution detail to be directly actionable.
- Use clear headings and subheadings with emojis (🎯 for goals, 💪 for workouts, ⚡ for intensity, 🔄 for recovery).
- Use bullet points for clarity with intensity guidance in bold.
- Provide clear, readiness-based adaptation options for each workout rather than rigid prescriptions."""


async def weekly_planner_node(state: TrainingAnalysisState) -> dict[str, list | str]:
    logger.info("Starting weekly planner node")

    hitl_enabled = state.get("hitl_enabled", True)
    logger.info(f"Weekly planner node: HITL {'enabled' if hitl_enabled else 'disabled'}")
    
    agent_start_time = datetime.now()

    tools = configure_node_tools(
        agent_name="weekly_planner",
        plot_storage=None,
        plotting_enabled=False,
    )

    system_prompt = (
        WEEKLY_PLANNER_SYSTEM_PROMPT +
        get_workflow_context("weekly_planner") +
        (get_hitl_instructions("weekly_planner") if hitl_enabled else "")
    )
    
    # Extract tactical details from expert outputs
    def get_tactical_details(expert_outputs):
        if hasattr(expert_outputs, "output"):
            output = expert_outputs.output
            if isinstance(output, list):
                raise ValueError("Expert outputs contain questions, not analysis. HITL interaction required.")
            if hasattr(output, "for_weekly_planner"):
                return output.for_weekly_planner
        raise ValueError(f"Expert outputs missing 'output.for_weekly_planner' field: {type(expert_outputs)}")
    
    # Extract content from AgentOutput (with new union type output field)
    def get_content(field):
        value = state.get(field, "")
        if hasattr(value, "output"):
            output = value.output
            if isinstance(output, str):
                return output
            raise ValueError("AgentOutput contains questions, not content. HITL interaction required.")
        if isinstance(value, dict):
            return value.get("output", value.get("content", value))
        return value
    
    # Include Q&A messages from orchestrator if present (for HITL re-invocations)
    # Read from agent-specific field
    qa_messages_raw = state.get("weekly_planner_messages", [])
    qa_messages = []
    for msg in qa_messages_raw:
        if hasattr(msg, "type"):  # LangChain message object
            role = "assistant" if msg.type == "ai" else "user"
            qa_messages.append({"role": role, "content": msg.content})
        else:  # Already a dict
            qa_messages.append(msg)
    
    user_message = {"role": "user", "content": WEEKLY_PLANNER_USER_PROMPT.format(
        season_plan=get_content("season_plan"),
        athlete_name=state["athlete_name"],
        current_date=json.dumps(state["current_date"], indent=2),
        week_dates=json.dumps(state["week_dates"], indent=2),
        competitions=json.dumps(state["competitions"], indent=2),
        planning_context=state["planning_context"],
        metrics_analysis=get_tactical_details(state.get("metrics_outputs")),
        activity_analysis=get_tactical_details(state.get("activity_outputs")),
        physiology_analysis=get_tactical_details(state.get("physiology_outputs")),
    )}
    
    base_messages = [{"role": "system", "content": system_prompt}, user_message]
    
    base_llm = ModelSelector.get_llm(AgentRole.WORKOUT)
    llm_with_tools = base_llm.bind_tools(tools) if tools else base_llm
    llm_with_structure = llm_with_tools.with_structured_output(AgentOutput)

    async def call_weekly_planning():
        messages_with_qa = base_messages + qa_messages
        if tools:
            return await handle_tool_calling_in_node(
                llm_with_tools=llm_with_structure,
                messages=messages_with_qa,
                tools=tools,
                max_iterations=15,
            )
        return await llm_with_structure.ainvoke(messages_with_qa)

    async def node_execution():
        agent_output = await retry_with_backoff(
            call_weekly_planning, AI_ANALYSIS_CONFIG, "Weekly Planning"
        )

        execution_time = (datetime.now() - agent_start_time).total_seconds()
        log_node_completion("Weekly planning", execution_time)

        return {
            "weekly_plan": agent_output.model_dump(),
            "costs": [create_cost_entry("weekly_planner", execution_time)],
        }

    return await execute_node_with_error_handling(
        node_name="Weekly planner",
        node_function=node_execution,
        error_message_prefix="Weekly planning failed",
    )
