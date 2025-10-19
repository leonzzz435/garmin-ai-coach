import json
import logging
from datetime import datetime

from services.ai.ai_settings import AgentRole
from services.ai.model_config import ModelSelector
from services.ai.tools.hitl import create_ask_human_tool
from services.ai.tools.plotting import PlotStorage, create_plotting_tools
from services.ai.utils.retry_handler import AI_ANALYSIS_CONFIG, retry_with_backoff

from ..state.training_analysis_state import TrainingAnalysisState
from .tool_calling_helper import handle_tool_calling_in_node

logger = logging.getLogger(__name__)

# Import GraphInterrupt exception class (not the interrupt function!)
try:
    from langgraph.errors import GraphInterrupt
except ImportError:
    try:
        from langgraph.errors import NodeInterrupt as GraphInterrupt
    except ImportError:
        class GraphInterrupt(BaseException):  # type: ignore
            """Placeholder exception for when LangGraph is not installed"""
            pass

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

PHYSIOLOGY_PLOTTING_INSTRUCTIONS = """

## 📊 SELECTIVE VISUALIZATION APPROACH

⚠️ **CRITICAL CONSTRAINT**: Create plots ONLY for insights that provide unique value beyond what's already available in the Garmin app.

**Before creating any plot, ask yourself:**
- Does this reveal physiological patterns NOT visible in Garmin's recovery or stress reports?
- Would this help coaches understand adaptation or recovery insights unavailable elsewhere?
- Is this analysis complex enough to warrant a custom visualization?

**LIMIT: Maximum 2 plots per agent.** Focus on truly unique physiological insights.

Use python_plotting_tool only when absolutely necessary for insights beyond standard Garmin reports.

## 🔗 CRITICAL: Plot Reference Usage - SINGLE REFERENCE RULE

**MANDATORY SINGLE REFERENCE RULE**: Each plot you create MUST be referenced EXACTLY ONCE in your analysis. Never repeat the same plot reference multiple times.

**Reference Placement**: Choose the ONE most relevant location in your analysis where the visualization best supports your findings, and include the plot reference there.

**Example workflow:**
1. Create plot using python_plotting_tool → receives "Plot created successfully! Reference as [PLOT:physiology_1234567890_001]"
2. Include in your analysis EXACTLY ONCE: "The HRV patterns reveal concerning recovery deficits [PLOT:physiology_1234567890_001] indicating the need for extended recovery periods."
3. DO NOT repeat this reference elsewhere in your analysis

**Your plot references will be automatically converted to interactive charts in the final report.**"""

PHYSIOLOGY_HITL_INSTRUCTIONS = """

## 🤝 HUMAN INTERACTION CAPABILITY

You have access to the `ask_human` tool to request clarification or additional information from the user.

**How to use ask_human:**
- Ask ONE clear, specific question at a time
- Provide brief context about why you're asking
- Keep questions focused and actionable
- Don't ask questions if the answer is already in the provided data

**Response handling:**
- Incorporate the human's answer into your analysis
- If the answer raises new questions, you can ask follow-up questions
- Acknowledge the information provided in your final analysis
"""

PHYSIOLOGY_USER_PROMPT = """Analyze the athlete's physiological data to assess recovery status and adaptation state.

## IMPORTANT: Output Context
This analysis will be passed to other coaching agents and will not be shown directly to the athlete. Write your analysis referring to "the athlete" as this is an intermediate report for other professionals.

## Input Data
```json
{data}
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
Analyze only the data that is actually present in the input. If analysis context is provided, use it to interpret the data more accurately.

1. Interpret heart rate variability patterns to assess the athlete's recovery status
2. Analyze available sleep data (duration, quality) if present
3. Evaluate stress scores and their trends
4. Track resting heart rate patterns as an indicator of fatigue and adaptation
5. Identify potential signs of overtraining based on these objective metrics
6. Suggest optimal recovery strategies based on the data available

## Output Requirements
- Include a Physiology Readiness Score (0-100) with clear explanation of calculation using only available data
- Format as structured markdown document with clear sections and bullet points
- Focus on factual analysis without speculation about unavailable data"""


async def physiology_node(state: TrainingAnalysisState) -> dict[str, list | str | dict]:
    logger.info("Starting physiology analysis node")

    try:
        plot_storage = PlotStorage(state["execution_id"])
        plotting_enabled = state.get("plotting_enabled", False)
        hitl_enabled = state.get("hitl_enabled", True)
        
        logger.info(
            f"Physiology node: Plotting {'enabled' if plotting_enabled else 'disabled'}, "
            f"HITL {'enabled' if hitl_enabled else 'disabled'}"
        )

        tools = []
        system_prompt = PHYSIOLOGY_SYSTEM_PROMPT_BASE
        
        if plotting_enabled:
            plotting_tool = create_plotting_tools(plot_storage, agent_name="physiology")
            tools.append(plotting_tool)
            system_prompt += PHYSIOLOGY_PLOTTING_INSTRUCTIONS
        
        if hitl_enabled:
            tools.append(create_ask_human_tool("Physiology"))
            system_prompt += PHYSIOLOGY_HITL_INSTRUCTIONS
        
        if tools:
            llm_with_tools = ModelSelector.get_llm(AgentRole.PHYSIO).bind_tools(tools)
        else:
            llm_with_tools = ModelSelector.get_llm(AgentRole.PHYSIO)

        recovery_indicators = state["garmin_data"].get("recovery_indicators", [])
        agent_start_time = datetime.now()

        async def call_physiology_analysis():
            return await handle_tool_calling_in_node(
                llm_with_tools=llm_with_tools,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": PHYSIOLOGY_USER_PROMPT.format(
                        data=json.dumps({
                            "hrv_data": state["garmin_data"].get("physiological_markers", {}).get("hrv", {}),
                            "sleep_data": [ind["sleep"] for ind in recovery_indicators if ind.get("sleep")],
                            "stress_data": [ind["stress"] for ind in recovery_indicators if ind.get("stress")],
                            "recovery_metrics": {
                                "physiological_markers": state["garmin_data"].get("physiological_markers", {}),
                                "body_metrics": state["garmin_data"].get("body_metrics", {}),
                                "recovery_indicators": recovery_indicators,
                            },
                        }, indent=2),
                        competitions=json.dumps(state["competitions"], indent=2),
                        current_date=json.dumps(state["current_date"], indent=2),
                        analysis_context=state["analysis_context"],
                    )},
                ],
                tools=tools,
                max_iterations=15,
            )

        physiology_result = await retry_with_backoff(
            call_physiology_analysis, AI_ANALYSIS_CONFIG, "Physiology Analysis with Tools"
        )

        execution_time = (datetime.now() - agent_start_time).total_seconds()
        all_plots = plot_storage.get_all_plots()
        timestamp_iso = datetime.now().isoformat()

        logger.info(
            f"Physiology analysis completed in {execution_time:.2f}s with {len(all_plots)} plots"
        )

        return {
            "physiology_result": physiology_result,
            "plots": [
                {"agent": "physiology", "plot_id": plot_id, "timestamp": timestamp_iso}
                for plot_id in all_plots
            ],
            "plot_storage_data": {
                plot_id: {
                    "plot_id": metadata.plot_id,
                    "description": metadata.description,
                    "agent_name": metadata.agent_name,
                    "created_at": metadata.created_at.isoformat(),
                    "html_content": metadata.html_content,
                    "data_summary": metadata.data_summary,
                }
                for plot_id, metadata in all_plots.items()
            },
            "costs": [{
                "agent": "physiology",
                "execution_time": execution_time,
                "timestamp": timestamp_iso,
            }],
            "available_plots": list(all_plots.keys()),
        }

    except GraphInterrupt:
        # CRITICAL: Let LangGraph handle the pause/resume - do not wrap or catch
        raise
    
    except Exception as e:
        logger.error(f"Physiology analysis node failed: {e}")
        return {"errors": [f"Physiology analysis failed: {str(e)}"]}
