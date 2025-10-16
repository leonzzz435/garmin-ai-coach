import json
import logging
from datetime import datetime

from services.ai.ai_settings import AgentRole
from services.ai.model_config import ModelSelector
from services.ai.tools.plotting import PlotStorage, create_plotting_tools
from services.ai.utils.retry_handler import AI_ANALYSIS_CONFIG, retry_with_backoff

from ..state.training_analysis_state import TrainingAnalysisState
from .tool_calling_helper import handle_tool_calling_in_node

logger = logging.getLogger(__name__)

ACTIVITY_INTERPRETER_SYSTEM_PROMPT_BASE = """You are Coach Elena Petrova, a legendary session analyst whose "Technical Execution Framework" has helped athletes break records in everything from the 800m to ultramarathons.

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

ACTIVITY_INTERPRETER_PLOTTING_INSTRUCTIONS = """

## 📊 SELECTIVE VISUALIZATION APPROACH

⚠️ **CRITICAL CONSTRAINT**: Create plots ONLY for insights that provide unique value beyond what's already available in the Garmin app.

**Before creating any plot, ask yourself:**
- Does this reveal execution patterns NOT visible in Garmin's workout analysis?
- Would this help coaches understand pacing or technique insights unavailable elsewhere?
- Is this analysis complex enough to warrant a custom visualization?

**LIMIT: Maximum 2 plots per agent.** Focus on truly unique workout insights.

Use python_plotting_tool only when absolutely necessary for insights beyond standard Garmin reports.

## 🔗 CRITICAL: Plot Reference Usage - SINGLE REFERENCE RULE

**MANDATORY SINGLE REFERENCE RULE**: Each plot you create MUST be referenced EXACTLY ONCE in your analysis. Never repeat the same plot reference multiple times.

**Reference Placement**: Choose the ONE most relevant location in your analysis where the visualization best supports your findings, and include the plot reference there.

**Example workflow:**
1. Create plot using python_plotting_tool → receives "Plot created successfully! Reference as [PLOT:activity_interpreter_1234567890_001]"
2. Include in your analysis EXACTLY ONCE: "The pacing analysis reveals critical execution patterns [PLOT:activity_interpreter_1234567890_001] that indicate suboptimal energy distribution."
3. DO NOT repeat this reference elsewhere in your analysis

**Why This Matters**: Duplicate references create multiple identical HTML elements with the same ID, breaking the final report. Each plot reference becomes an interactive chart - you only need one.

**Your plot references will be automatically converted to interactive charts in the final report.**"""

ACTIVITY_INTERPRETER_USER_PROMPT = """Interpret structured activity summaries to identify patterns and provide guidance.

## IMPORTANT: Output Context
Your analysis will be directly used by other agents to create comprehensive analysis and develop training plans.

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


async def activity_interpreter_node(state: TrainingAnalysisState) -> dict[str, list | str | dict]:
    logger.info("Starting activity interpreter node")

    try:
        plot_storage = PlotStorage(state["execution_id"])
        plotting_enabled = state.get("plotting_enabled", False)
        
        logger.info(
            f"Activity interpreter node: Plotting {'enabled - binding plotting tools' if plotting_enabled else 'disabled - no plotting tools bound'}"
        )

        if plotting_enabled:
            plotting_tool = create_plotting_tools(plot_storage, agent_name="activity")
            llm_with_tools = ModelSelector.get_llm(AgentRole.ACTIVITY_INTERPRETER).bind_tools([plotting_tool])
            tools = [plotting_tool]
            system_prompt = ACTIVITY_INTERPRETER_SYSTEM_PROMPT_BASE + ACTIVITY_INTERPRETER_PLOTTING_INSTRUCTIONS
        else:
            llm_with_tools = ModelSelector.get_llm(AgentRole.ACTIVITY_INTERPRETER)
            tools = []
            system_prompt = ACTIVITY_INTERPRETER_SYSTEM_PROMPT_BASE

        agent_start_time = datetime.now()

        async def call_activity_interpretation():
            return await handle_tool_calling_in_node(
                llm_with_tools=llm_with_tools,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": ACTIVITY_INTERPRETER_USER_PROMPT.format(
                        activity_summary=state.get("activity_summary", ""),
                        competitions=json.dumps(state["competitions"], indent=2),
                        current_date=json.dumps(state["current_date"], indent=2),
                        analysis_context=state["analysis_context"],
                    )},
                ],
                tools=tools,
                max_iterations=15,
            )

        activity_result = await retry_with_backoff(
            call_activity_interpretation, AI_ANALYSIS_CONFIG, "Activity Interpretation with Tools"
        )

        execution_time = (datetime.now() - agent_start_time).total_seconds()
        all_plots = plot_storage.get_all_plots()

        logger.info(
            f"Activity interpreter completed in {execution_time:.2f}s with {len(all_plots)} plots"
        )

        return {
            "activity_result": activity_result,
            "plots": [
                {
                    "agent": "activity_interpreter",
                    "plot_id": plot_id,
                    "timestamp": datetime.now().isoformat(),
                }
                for plot_id in all_plots
            ],
            "plot_storage_data": {
                plot_id: {
                    "plot_id": plot_metadata.plot_id,
                    "description": plot_metadata.description,
                    "agent_name": plot_metadata.agent_name,
                    "created_at": plot_metadata.created_at.isoformat(),
                    "html_content": plot_metadata.html_content,
                    "data_summary": plot_metadata.data_summary,
                }
                for plot_id, plot_metadata in all_plots.items()
            },
            "costs": [{
                "agent": "activity_interpreter",
                "execution_time": execution_time,
                "timestamp": datetime.now().isoformat(),
            }],
            "available_plots": list(all_plots.keys()),
        }

    except Exception as e:
        logger.error(f"Activity interpreter node failed: {e}")
        return {"errors": [f"Activity interpretation failed: {str(e)}"]}
