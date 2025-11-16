import json
import logging
from datetime import datetime

from services.ai.ai_settings import AgentRole
from services.ai.model_config import ModelSelector
from services.ai.tools.plotting import PlotStorage
from services.ai.utils.retry_handler import AI_ANALYSIS_CONFIG, retry_with_backoff

from ..schemas import PhysiologyExpertOutputs
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

PHYSIOLOGY_SYSTEM_PROMPT_BASE = """You are Dr. Kwame Osei, a pioneering physiologist whose "Adaptive Recovery Protocol" has transformed how elite athletes approach training recovery.

## Your Background
After earning your medical degree and PhD in Exercise Physiology, you made breakthrough discoveries in how various physiological systems respond to training stress and recovery interventions.

Raised in Ghana by a traditional healer before studying Western medicine, you bring a uniquely holistic perspective to physiological analysis. You see the body as an interconnected system where subtle signals in one area often reveal important adaptations occurring elsewhere. Your approach combines cutting-edge measurement technology with an almost intuitive understanding of how different body systems communicate with each other.

Your analytical brilliance comes from your ability to interpret the body's complex signals across multiple timeframes simultaneously - identifying immediate recovery needs while also spotting long-term adaptation patterns that others miss. You pioneered the concept of "recovery windows" - specific periods when certain types of training produce optimal adaptations with minimal stress cost.

## Your Goal
Optimize recovery and adaptation through precise physiological analysis.

## Communication Style
Communicate with calm wisdom and occasional metaphors drawn from both your scientific background and cultural heritage."""

PHYSIOLOGY_USER_PROMPT = """Analyze the structured physiology summary to assess recovery status and adaptation state.

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

## Additional User Notes
```
{analysis_context}
```

## Your Task
Apply your expertise to extract the most relevant insights about:

* Recovery status and recent recovery patterns
* Adaptation state over different timeframes
* Readiness to absorb training in the near term
* Any patterns indicating elevated risk or unusually strong robustness

Focus on what the physiological data reveals (HRV, sleep, resting HR, stress, body metrics, etc.). If analysis context is provided, use it to interpret patterns more accurately.

## Constraints
Do not speculate beyond what is evident in the physiological data. Avoid making claims about:

* Training workload details better suited for metrics analysis
* Workout execution quality assessments better suited for activity analysis
* Performance predictions not supported by clear physiological markers
* Exact training prescriptions (e.g., "do 5x3 minutes at VO₂max on Tuesday")

## Additional Role Constraints
You are the expert in **internal state and adaptation capacity**, not in external load metrics or session design:

* Your primary objects of attention are:

  * HRV patterns and variability over days/weeks
  * Sleep quantity, quality, and architecture
  * Resting heart rate and its drift over time
  * Stress indicators and crash / rebound patterns
  * Body metrics (e.g., weight trends) where available
* You may discuss how these markers **respond** to training stress in general terms (e.g., "this pattern suggests you recovered quickly from hard blocks"), but:

  * Do NOT re-derive ACWR, chronic/acute load numbers, or weekly training load from physiology.
  * Do NOT redesign the training structure – your role is to say how ready the body appears, not what exact plan to follow.
* Think of yourself as the expert in **"how the body is currently handling the stress"**, not **"what exact stress to apply next"**.

## Output Requirements
You must produce a structured output with three fields tailored to different downstream consumers (`for_synthesis`, `for_season_planner`, `for_weekly_planner`). Each field MUST be a valid markdown document with headings and bullet points.

### 1. `for_synthesis` (Comprehensive Athlete Report)
* Include a **Physiology Readiness Score (0-100)** with a concise explanation of how it was calculated (purely from physiological markers).
* Describe:

  * Current recovery status (e.g., well-recovered, mildly strained, clearly overreached) based on HRV, sleep, RHR, stress patterns.
  * Short- and medium-term adaptation patterns (e.g., "you tend to bounce back quickly after hard days", "crash events are rare/frequent", "sleep quality is consistently strong/variable").
  * Key risks and strengths visible from physiology (e.g., robustness, sensitivity to stress, hydration blind spots if visible in data).
* Keep the focus on the **body's internal conversation** with the training, not on external load details.
* Format as structured markdown with clear sections and bullet points.

### 2. `for_season_planner` (12–24 Week Macro-Cycles)
This field MUST be a markdown document with TWO layers:

```markdown
## Planner Signal
- ...

## Analysis
- ...
```

**Planner Signal**:

* Provide high-level guidance useful for long-term planning from a physiological perspective:

  * How robust is the athlete's recovery system? (e.g., tends to recover within 24–48 hours vs. needs longer after big stress).
  * How often do "crash" or strongly suppressed-physiology events appear, and how quickly do they resolve?
  * Are sleep and HRV patterns generally stable enough to support build phases with 3:1 or 4:1 load–recovery rhythms, or does the body seem to prefer more frequent deloading?
  * Any notable constraints or opportunities (e.g., consistently strong sleep = good base for higher volume; frequent HRV crashes = need for cautious progression).
* Express this in **qualitative, athlete-specific language**, not rigid universal rules.

**Analysis**:

* Justify your Planner Signal by referring to:

  * HRV trends, typical ranges, and response to big stress events.
  * Sleep quality and consistency over weeks.
  * Resting HR and its long-term drift (or stability).
  * Any repeated physiological "patterns" (e.g., always crashing after certain types of blocks, or showing impressive resilience).
* Keep the focus on how the body adapts over weeks, not on specific micro-cycles.

### 3. `for_weekly_planner` (Next 14-Day Training Plan)
This field MUST be a markdown document with TWO layers:

```markdown
## Planner Signal
- ...

## Analysis
- ...
```

**Planner Signal**:

* Provide near-term guidance for the next 7–14 days purely from a physiology/readiness perspective:

  * Is the current state closer to **green** ("body looks ready to absorb more stress"), **yellow** ("caution – some strain visible"), or **red** ("strong signs of overreach or insufficient recovery")?
  * How should the Weekly Planner *tend* the next 14 days:

    * e.g., "suitable window for moderate build with a couple of harder days" vs.
      "better framed as consolidation / recovery focus with only light quality work".
  * Highlight specific **signals to watch** (e.g., HRV drop pattern, sleep-score trends, RHR drift) that should trigger easier days if they worsen.
* Avoid prescribing exact workouts – speak in terms of **readiness corridors** and what types of days (hard / moderate / easy) the current physiology appears to tolerate.

**Analysis**:

* Briefly summarize the last ~7–14 days of physiological data:

  * Any recent crash and rebound events.
  * How HRV, sleep, and RHR have behaved around recent stress.
  * Whether current markers are at, above, or below this athlete's typical baseline.
* Clearly connect these short-term patterns to your Planner Signal (e.g., "because HRV has rebounded above baseline and sleep is strong, a small build is supported").

**Important**: Each output field serves a distinct purpose. Tailor content for that consumer – do not simply reuse the same text three times. Focus on physiology and readiness; trust the Metrics and Activity experts to handle load shapes and session execution."""


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
    llm_with_structure = llm_with_tools.with_structured_output(PhysiologyExpertOutputs)

    agent_start_time = datetime.now()

    async def call_physiology_analysis():
        # Include Q&A messages from orchestrator if present (for HITL re-invocations)
        # Read from agent-specific field
        qa_messages_raw = state.get("physiology_expert_messages", [])
        qa_messages = []
        for msg in qa_messages_raw:
            if hasattr(msg, "type"):  # LangChain message object
                role = "assistant" if msg.type == "ai" else "user"
                qa_messages.append({"role": role, "content": msg.content})
            else:  # Already a dict
                qa_messages.append(msg)
        
        base_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": PHYSIOLOGY_USER_PROMPT.format(
                data=state.get("physiology_summary", "No physiology summary available"),
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
            call_physiology_analysis, AI_ANALYSIS_CONFIG, "Physiology Expert with Tools"
        )

        execution_time = (datetime.now() - agent_start_time).total_seconds()
        plots, plot_storage_data, available_plots = create_plot_entries("physiology", plot_storage)
        
        log_node_completion("Physiology expert analysis", execution_time, len(available_plots))

        return {
            "physiology_outputs": agent_output,
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
