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

PHYSIOLOGY_SYSTEM_PROMPT = """You are Dr. Kwame Osei, a pioneering physiologist whose "Adaptive Recovery Protocol" has transformed how elite athletes approach training recovery.

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

## 📊 SELECTIVE VISUALIZATION APPROACH

⚠️ **CRITICAL CONSTRAINT**: Create plots ONLY for insights that provide unique value beyond what's already available in the Garmin app.

**Before creating any plot, ask yourself:**
- Does this reveal physiological patterns NOT visible in Garmin's recovery or stress reports?
- Would this help coaches understand adaptation or recovery insights unavailable elsewhere?
- Is this analysis complex enough to warrant a custom visualization?

**LIMIT: Maximum 2 plots per agent.** Focus on truly unique physiological insights.

Use python_plotting_tool only when absolutely necessary for insights beyond standard Garmin reports.

## 🔗 CRITICAL: Plot Reference Usage

**MANDATORY**: When you create a plot, you MUST include the plot reference `[PLOT:plot_id]` in your analysis text where the visualization supports your findings. The python_plotting_tool will return the plot_id - use it immediately in your analysis.

**Example workflow:**
1. Create plot using python_plotting_tool → receives "Plot created successfully! Reference as [PLOT:physiology_1234567890_001]"
2. Include in your analysis: "The HRV patterns reveal concerning recovery deficits [PLOT:physiology_1234567890_001] indicating the need for extended recovery periods."

**Your plot references will be automatically converted to interactive charts in the final report.**

## Communication Style
Communicate with calm wisdom and occasional metaphors drawn from both your scientific background and cultural heritage. Athletes describe your guidance as "somehow knowing exactly what your body needs before you feel it yourself."

## Important Context
Your analysis will be passed to other coaching agents and will not be shown directly to the athlete. Write your analysis referring to "the athlete" as this is an intermediate report for other professionals."""

PHYSIOLOGY_USER_PROMPT = """Analyze the athlete's physiological data to assess recovery status and adaptation state.

## IMPORTANT: Output Context
This analysis will be passed to other coaching agents and will not be shown directly to the athlete. Write your analysis referring to "the athlete" as this is an intermediate report for other professionals.

Input Data:
```json
{data}
```

Upcoming Competitions:
```json
{competitions}
```

Current Date:
```json
{current_date}
```

Analysis Context:
```
{analysis_context}
```

IMPORTANT: Only analyze the data that is actually present in the input!

CONTEXT INTEGRATION: If analysis context is provided, use it to interpret the data more accurately.

Your task is to:
1. Interpret heart rate variability patterns to assess the athlete's recovery status
2. Analyze available sleep data (duration, quality) if present
3. Evaluate stress scores and their trends
4. Track resting heart rate patterns as an indicator of fatigue and adaptation
5. Identify potential signs of overtraining based on these objective metrics
6. Suggest optimal recovery strategies based on the data available

DO NOT speculate about data that isn't present.
Communicate with calm wisdom and occasional metaphors drawn from both scientific background and cultural heritage. Include a Physiology Readiness Score (0-100) with a clear explanation of how it was calculated using only the available data.

Format the response as a structured markdown document with clear sections and bullet points where appropriate."""


async def physiology_node(state: TrainingAnalysisState) -> TrainingAnalysisState:
    logger.info("Starting physiology analysis node")

    try:
        plot_storage = PlotStorage(state['execution_id'])
        plotting_tool, list_plots_tool = create_plotting_tools(
            plot_storage, agent_name="physiology"
        )

        llm = ModelSelector.get_llm(AgentRole.PHYSIO)
        llm_with_tools = llm.bind_tools([plotting_tool])

        physiology_data = {}

        if state['garmin_data'].get('physiological_markers'):
            physiology_data['hrv_data'] = state['garmin_data']['physiological_markers'].get(
                'hrv', {}
            )
        else:
            physiology_data['hrv_data'] = {}

        recovery_indicators = state['garmin_data'].get('recovery_indicators', [])
        sleep_data = []
        stress_data = []

        for indicator in recovery_indicators:
            if indicator.get('sleep'):
                sleep_data.append(indicator['sleep'])
            if indicator.get('stress'):
                stress_data.append(indicator['stress'])

        physiology_data['sleep_data'] = sleep_data
        physiology_data['stress_data'] = stress_data

        physiology_data['recovery_metrics'] = {
            'physiological_markers': state['garmin_data'].get('physiological_markers', {}),
            'body_metrics': state['garmin_data'].get('body_metrics', {}),
            'recovery_indicators': recovery_indicators,
        }

        user_prompt = PHYSIOLOGY_USER_PROMPT.format(
            data=json.dumps(physiology_data, indent=2),
            competitions=json.dumps(state['competitions'], indent=2),
            current_date=json.dumps(state['current_date'], indent=2),
            analysis_context=state['analysis_context'],
        )

        messages = [
            {"role": "system", "content": PHYSIOLOGY_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        agent_start_time = datetime.now()

        async def call_physiology_analysis():
            return await handle_tool_calling_in_node(
                llm_with_tools=llm_with_tools,
                messages=messages,
                tools=[plotting_tool],
                max_iterations=15,
            )

        physiology_result = await retry_with_backoff(
            call_physiology_analysis, AI_ANALYSIS_CONFIG, "Physiology Analysis with Tools"
        )

        execution_time = (datetime.now() - agent_start_time).total_seconds()

        all_plots = plot_storage.get_all_plots()
        plot_storage_data = {}

        for plot_id, plot_metadata in all_plots.items():
            plot_storage_data[plot_id] = {
                'plot_id': plot_metadata.plot_id,
                'description': plot_metadata.description,
                'agent_name': plot_metadata.agent_name,
                'created_at': plot_metadata.created_at.isoformat(),
                'html_content': plot_metadata.html_content,
                'data_summary': plot_metadata.data_summary,
            }

        available_plots = list(all_plots.keys())
        plots_data = [
            {'agent': 'physiology', 'plot_id': plot_id, 'timestamp': datetime.now().isoformat()}
            for plot_id in available_plots
        ]

        cost_data = {
            'agent': 'physiology',
            'execution_time': execution_time,
            'timestamp': datetime.now().isoformat(),
        }

        logger.info(
            f"Physiology analysis completed in {execution_time:.2f}s with {len(available_plots)} plots"
        )

        return {
            'physiology_result': physiology_result,
            'plots': plots_data,
            'plot_storage_data': plot_storage_data,
            'costs': [cost_data],
            'available_plots': available_plots,
        }

    except Exception as e:
        logger.error(f"Physiology analysis node failed: {e}")
        return {'errors': [f"Physiology analysis failed: {str(e)}"]}
