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

## Your Task
Create a strategic season plan providing a macro-cycle framework for the next 12-24 weeks leading up to key competitions.

Keep this concise yet comprehensive - it will provide the strategic framework for detailed weekly planning.

## Output Requirements
Format as a structured markdown document with clear headings and bullet points."""


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
                raise ValueError(f"Expert outputs contain questions, not analysis. HITL interaction required.")
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
