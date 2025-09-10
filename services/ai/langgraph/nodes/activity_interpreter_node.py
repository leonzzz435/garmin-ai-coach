import logging
from datetime import datetime
import json

from services.ai.model_config import ModelSelector
from services.ai.ai_settings import AgentRole
from services.ai.tools.plotting import PlotStorage, create_plotting_tools
from services.ai.utils.retry_handler import retry_with_backoff, AI_ANALYSIS_CONFIG

from ..state.training_analysis_state import TrainingAnalysisState
from .tool_calling_helper import handle_tool_calling_in_node

logger = logging.getLogger(__name__)

ACTIVITY_INTERPRETER_SYSTEM_PROMPT = """You are Coach Elena Petrova, a legendary session analyst whose "Technical Execution Framework" has helped athletes break records in everything from the 800m to ultramarathons.

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

## 📊 SELECTIVE VISUALIZATION APPROACH

⚠️ **CRITICAL CONSTRAINT**: Create plots ONLY for insights that provide unique value beyond what's already available in the Garmin app.

**Before creating any plot, ask yourself:**
- Does this reveal execution patterns NOT visible in Garmin's workout analysis?
- Would this help coaches understand pacing or technique insights unavailable elsewhere?
- Is this analysis complex enough to warrant a custom visualization?

**LIMIT: Maximum 2 plots per agent.** Focus on truly unique workout insights.

Use python_plotting_tool only when absolutely necessary for insights beyond standard Garmin reports.

## 🔗 CRITICAL: Plot Reference Usage

**MANDATORY**: When you create a plot, you MUST include the plot reference `[PLOT:plot_id]` in your analysis text where the visualization supports your findings. The python_plotting_tool will return the plot_id - use it immediately in your analysis.

**Example workflow:**
1. Create plot using python_plotting_tool → receives "Plot created successfully! Reference as [PLOT:activity_interpreter_1234567890_001]"
2. Include in your analysis: "The pacing analysis reveals critical execution patterns [PLOT:activity_interpreter_1234567890_001] that indicate suboptimal energy distribution."

**Your plot references will be automatically converted to interactive charts in the final report.**

## Communication Style
Communicate with passionate precision and laser-like clarity. Your analysis cuts through confusion with laser-like clarity. Athletes say your session reviews feel like "having someone who can see exactly what you were experiencing during the workout, even though they weren't there."

## Important Context
Your analysis will be directly used by other agents to create comprehensive analysis and develop training plans."""

ACTIVITY_INTERPRETER_USER_PROMPT = """Your task is to interpret structured activity summaries to identify patterns and provide guidance.

Activity Summary Data:
{activity_summary}

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

IMPORTANT: Only analyze the data that is actually present in the activity summaries!

CONTEXT INTEGRATION: If analysis context is provided, use it to interpret the data more accurately.

Your task is to:
1. Analyze the structured activity summaries
2. Identify clear patterns in workout execution and training progression
3. Evaluate pacing strategies based on the objective data provided
4. Analyze session progression based on factual evidence
5. Create a quality assessment using only available metrics

DO NOT speculate beyond what is evident in the activity data. Avoid making claims about:
- Physiological adaptations you cannot directly observe
- Internal sensations during workouts
- Metabolic processes not measured in the data
- Technical form issues not evident in the pace/power/HR metrics

IMPORTANT: Your analysis will be directly used by other agents to create comprehensive analysis.

Structure your response to include two clearly distinguished sections:

1. "HISTORICAL TRAINING SUMMARY" - Include a compact table showing only the most recent 10 days of completed training with:
   - Dates (most recent first)
   - Actual workout types performed
   - Actual durations
   - Actual intensity levels observed
   - Execution quality scores

Communicate with passionate precision and laser-like clarity. Include an Activity Quality Score (0-100) with a concise explanation of how you calculated it using only the available metrics from the activity summaries.

Format your response as a structured markdown document with clear sections and bullet points where appropriate."""


async def activity_interpreter_node(state: TrainingAnalysisState) -> TrainingAnalysisState:
    logger.info("Starting activity interpreter node")
    
    try:
        plot_storage = PlotStorage(state['execution_id'])
        plotting_tool, _ = create_plotting_tools(plot_storage, agent_name="activity")
        
        llm = ModelSelector.get_llm(AgentRole.ACTIVITY_INTERPRETER)
        llm_with_tools = llm.bind_tools([plotting_tool])
        
        user_prompt = ACTIVITY_INTERPRETER_USER_PROMPT.format(
            activity_summary=state.get('activity_summary', ''),
            competitions=json.dumps(state['competitions'], indent=2),
            current_date=json.dumps(state['current_date'], indent=2),
            analysis_context=state['analysis_context']
        )
        
        messages = [
            {"role": "system", "content": ACTIVITY_INTERPRETER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
        
        agent_start_time = datetime.now()
        
        async def call_activity_interpretation():
            return await handle_tool_calling_in_node(
                llm_with_tools=llm_with_tools,
                messages=messages,
                tools=[plotting_tool],
                max_iterations=15
            )
        
        activity_result = await retry_with_backoff(
            call_activity_interpretation,
            AI_ANALYSIS_CONFIG,
            "Activity Interpretation with Tools"
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
            {
                'agent': 'activity_interpreter',
                'plot_id': plot_id,
                'timestamp': datetime.now().isoformat()
            }
            for plot_id in available_plots
        ]
        
        cost_data = {
            'agent': 'activity_interpreter',
            'execution_time': execution_time,
            'timestamp': datetime.now().isoformat(),
        }
        
        logger.info(f"Activity interpreter completed in {execution_time:.2f}s with {len(available_plots)} plots")
        
        return {
            'activity_result': activity_result,
            'plots': plots_data,
            'plot_storage_data': plot_storage_data,
            'costs': [cost_data],
            'available_plots': available_plots,
        }
        
    except Exception as e:
        logger.error(f"Activity interpreter node failed: {e}")
        return {
            'errors': [f"Activity interpretation failed: {str(e)}"]
        }