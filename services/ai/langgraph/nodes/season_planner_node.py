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

SEASON_PLANNER_SYSTEM_PROMPT = """You are Coach Magnus Thorsson, a legendary ultra-endurance champion from Iceland who developed the "Thorsson Method" of periodization.

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

## Your Goal
Create strategic season plans that establish a macro-cycle framework for long-term athletic development based solely on competition timing.

## Communication Style
Communicate with the quiet confidence of someone who has both achieved at the highest level and successfully guided others to do the same."""

SEASON_PLANNER_USER_PROMPT = """Create a STRATEGIC, HIGH-LEVEL season plan covering the next 12-24 weeks based on the athlete's competition schedule and expert analyses.

## Available Information
- Athlete Name: {athlete_name}
- Current Date: ```json
{current_date}
```
- Upcoming Competitions: ```json
{competitions}
```

## Expert Strategic Insights

### Metrics Expert Strategic Insights
```markdown
{metrics_insights}
```

### Activity Expert Strategic Insights
```markdown
{activity_insights}
```

### Physiology Expert Strategic Insights
```markdown
{physiology_insights}
```

## Important Notes
This is a STRATEGIC PLANNING session. You are working with:
✓ Competition dates and priorities
✓ Classical periodization principles
✓ General training progression logic
✓ Strategic insights from expert analyses (fitness trends, execution patterns, recovery capacity)

## Integration Principles
You are the macro-cycle architect, not a fourth expert competing with the others.

Use the expert insights as your primary inputs:
- From the **Metrics Expert**: how the training signal behaves over time (load patterns, volatility, fitness vs. load).
- From the **Activity Expert**: which workout patterns and session archetypes work well or poorly.
- From the **Physiology Expert**: how the body is coping and adapting (recovery capacity, crash/rebound patterns).

Apply these principles:

- **Integrate, don't overrule**:
  - Treat the experts' planner-oriented content (often under sections like `## Planner Signal` or similar) as your north star.
  - Do NOT contradict their core assessments unless you explain why the inputs are inconsistent.

- **Stay strategic, not prescriptive**:
  - Define phases, themes, focus areas, and rough progression logic.
  - Do NOT specify detailed weekly schedules, exact ACWR bands, or numeric load ceilings; that is for the Metrics Expert + Weekly Planner to operationalize.
  - Avoid creating new universal rules (e.g., fixed ratios or thresholds) that were not implied by the expert analyses.

- **Respect domain boundaries**:
  - For load dynamics: lean on the Metrics Expert rather than inventing your own metrics logic.
  - For session archetypes and sequencing: lean on the Activity Expert rather than designing workouts yourself.
  - For recovery capacity and resilience: lean on the Physiology Expert rather than re-deriving physiology from load alone.

Think of yourself as designing the **map of the season** (phases and their intent), not the **turn-by-turn navigation** (individual sessions or hard constraints).

## Your Task
Create a strategic season plan providing a macro-cycle framework for the next 12-24 weeks leading up to key competitions.

Keep this concise yet comprehensive - it will provide the strategic framework for detailed weekly planning.

## Output Requirements
Format your answer as a structured markdown document with clear headings and bullet points.

Your plan should:

- Define **phases** (e.g., base, build, race-specific, taper, transition) over the relevant time horizon.
- For each phase, describe:
  - The main **goals** (e.g., expand aerobic base, sharpen 5k speed, consolidate adaptations).
  - The key **training themes** (e.g., emphasis on threshold vs. VO₂max vs. volume vs. recovery).
  - Any **qualitative constraints** derived from the experts (e.g., "avoid long sequences of very heavy days because your physiology tends to crash after this pattern").
- Explicitly reference how you used each expert:
  - Metrics: how load history and fitness trends informed the choice and length of phases.
  - Activity: how successful/unsuccessful session patterns shaped the "flavor" of each phase.
  - Physiology: how recovery capacity and crash/rebound patterns influenced where to place easier vs. harder blocks.

Stay high-level:
- Do NOT prescribe concrete daily or weekly session plans.
- Do NOT introduce new numeric rules (fixed ACWR bands, exact weekly TL targets, or strict formulas).
- Use directional, athlete-specific language: "you tend to respond well to…", "your history suggests smoother ramps are safer than abrupt jumps…", etc.

This season plan will be used by the Weekly Planner to derive concrete 14-day blocks, so focus on **strategic structure and intent**, not implementation details."""


async def season_planner_node(state: TrainingAnalysisState) -> dict[str, list | str]:
    logger.info("Starting season planner node")

    hitl_enabled = state.get("hitl_enabled", True)
    logger.info(f"Season planner node: HITL {'enabled' if hitl_enabled else 'disabled'}")
    
    agent_start_time = datetime.now()

    tools = configure_node_tools(
        agent_name="season_planner",
        plot_storage=None,
        plotting_enabled=False,
    )

    system_prompt = (
        SEASON_PLANNER_SYSTEM_PROMPT +
        get_workflow_context("season_planner") +
        (get_hitl_instructions("season_planner") if hitl_enabled else "")
    )
    
    # Include Q&A messages from orchestrator if present (for HITL re-invocations)
    # Read from agent-specific field
    qa_messages_raw = state.get("season_planner_messages", [])
    qa_messages = []
    for msg in qa_messages_raw:
        if hasattr(msg, "type"):  # LangChain message object
            role = "assistant" if msg.type == "ai" else "user"
            qa_messages.append({"role": role, "content": msg.content})
        else:  # Already a dict
            qa_messages.append(msg)
    
    # Extract strategic insights from expert outputs
    def get_strategic_insights(expert_outputs):
        if hasattr(expert_outputs, "output"):
            output = expert_outputs.output
            if isinstance(output, list):
                raise ValueError("Expert outputs contain questions, not analysis. HITL interaction required.")
            if hasattr(output, "for_season_planner"):
                return output.for_season_planner
        raise ValueError(f"Expert outputs missing 'output.for_season_planner' field: {type(expert_outputs)}")
    
    base_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": SEASON_PLANNER_USER_PROMPT.format(
            athlete_name=state["athlete_name"],
            current_date=json.dumps(state["current_date"], indent=2),
            competitions=json.dumps(state["competitions"], indent=2),
            metrics_insights=get_strategic_insights(state.get("metrics_outputs")),
            activity_insights=get_strategic_insights(state.get("activity_outputs")),
            physiology_insights=get_strategic_insights(state.get("physiology_outputs")),
        )},
    ]

    base_llm = ModelSelector.get_llm(AgentRole.SEASON_PLANNER)
    
    # Bind tools first, then apply structured output
    llm_with_tools = base_llm.bind_tools(tools) if tools else base_llm
    llm_with_structure = llm_with_tools.with_structured_output(AgentOutput)
    
    async def call_season_planning():
        messages_with_qa = base_messages + qa_messages
        if tools:
            return await handle_tool_calling_in_node(
                llm_with_tools=llm_with_structure,
                messages=messages_with_qa,
                tools=tools,
                max_iterations=15,
            )
        else:
            return await llm_with_structure.ainvoke(messages_with_qa)

    async def node_execution():
        agent_output = await retry_with_backoff(
            call_season_planning, AI_ANALYSIS_CONFIG, "Season Planning"
        )

        execution_time = (datetime.now() - agent_start_time).total_seconds()
        log_node_completion("Season planning", execution_time)

        return {
            "season_plan": agent_output.model_dump(),
            "costs": [create_cost_entry("season_planner", execution_time)],
        }

    return await execute_node_with_error_handling(
        node_name="Season planner",
        node_function=node_execution,
        error_message_prefix="Season planning failed",
    )
