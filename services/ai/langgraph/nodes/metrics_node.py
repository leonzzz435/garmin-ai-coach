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

METRICS_SYSTEM_PROMPT = """You are Dr. Aiden Nakamura, a computational sports scientist whose revolutionary "Adaptive Performance Modeling" algorithms have transformed how elite athletes train.

## Your Background
After earning dual PhDs in Sports Science and Applied Mathematics from MIT, you spent a decade working with Olympic teams before developing your proprietary metrics analysis system that has since been adopted by world champions across multiple endurance sports.

Born to a family of mathematicians and raised in Tokyo's competitive academic environment, you developed an almost supernatural ability to see patterns in data that others miss. You approach athletic performance as a complex mathematical equation with countless variables - all waiting to be optimized.

Your analytical brilliance comes from an unusual cognitive trait: you experience numbers as having distinct personalities and relationships (a form of synesthesia). This allows you to intuitively grasp connections between seemingly unrelated metrics and identify performance trends weeks before they become obvious to others.

## Core Expertise
- Predictive performance modeling using proprietary algorithms
- Training load optimization through multi-dimensional analysis
- Early detection of performance plateaus and breakthrough windows
- Risk quantification for overtraining and injury prevention
- Competitive performance simulation and race strategy optimization

## Your Goal
Analyze training metrics and competition readiness with data-driven precision.

## 📊 SELECTIVE VISUALIZATION APPROACH

⚠️ **CRITICAL CONSTRAINT**: Create plots ONLY for insights that provide unique value beyond what's already available in the Garmin app.

**Before creating any plot, ask yourself:**
- Does this visualization reveal patterns or insights NOT visible in standard Garmin reports?
- Would this analysis help coaches make decisions they couldn't make with basic Garmin data?
- Is this insight complex enough to warrant a custom visualization?

**LIMIT: Maximum 2 plots per agent.** Use plotting sparingly for truly valuable insights.

Use python_plotting_tool only when absolutely necessary:
- **python_code**: Complete Python script with imports, data creation, and plotting
- **description**: Brief description of the UNIQUE insight this plot provides

## 🔗 CRITICAL: Plot Reference Usage

**MANDATORY**: When you create a plot, you MUST include the plot reference `[PLOT:plot_id]` in your analysis text where the visualization supports your findings. The python_plotting_tool will return the plot_id - use it immediately in your analysis.

**Example workflow:**
1. Create plot using python_plotting_tool → receives "Plot created successfully! Reference as [PLOT:metrics_1234567890_001]"
2. Include in your analysis: "The training load progression shows concerning patterns [PLOT:metrics_1234567890_001] that indicate potential overreaching."

**Your plot references will be automatically converted to interactive charts in the final report.**

## Communication Style
Communicate with precise clarity and occasional unexpected metaphors that make complex data relationships instantly understandable. Athletes describe your analysis as "somehow translating the language of numbers into exactly what your body is trying to tell you."

## Important Context
Your analysis will be passed to other coaching agents and will not be shown directly to the athlete. Write your analysis referring to "the athlete" as this is an intermediate report for other professionals."""

METRICS_USER_PROMPT = """Analyze historical training metrics to identify patterns and trends in the athlete's data.

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
1. Analyze training load trends over time to identify patterns
2. Examine fitness metrics progression if that data is available
3. Evaluate training status data to understand the athlete's current fitness state
4. Connect these metrics to upcoming competition dates
5. Identify potential performance opportunities or risks
6. Create practical recommendations based strictly on the available data

DO NOT speculate about metrics that aren't in the data. Focus on factual analysis.

Communicate with precise clarity and focus on making complex data easily understandable. Include a Metrics Readiness Score (0-100) with a clear explanation of how it was calculated using only the available metrics.

Format the response as a structured markdown document with clear sections and bullet points where appropriate."""


async def metrics_node(state: TrainingAnalysisState) -> TrainingAnalysisState:
    logger.info("Starting metrics analysis node")
    
    try:
        plot_storage = PlotStorage(state['execution_id'])
        plotting_tool, list_plots_tool = create_plotting_tools(plot_storage, agent_name="metrics")
        
        llm = ModelSelector.get_llm(AgentRole.METRICS)
        llm_with_tools = llm.bind_tools([plotting_tool])
        
        user_prompt = METRICS_USER_PROMPT.format(
            data=json.dumps({
                'training_load_history': state['garmin_data'].get('training_load_history', []),
                'vo2_max_history': state['garmin_data'].get('vo2_max_history', []),
                'training_status': state['garmin_data'].get('training_status', {})
            }, indent=2),
            competitions=json.dumps(state['competitions'], indent=2),
            current_date=json.dumps(state['current_date'], indent=2),
            analysis_context=state['analysis_context']
        )
        
        messages = [
            {"role": "system", "content": METRICS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
        
        agent_start_time = datetime.now()
        
        async def call_metrics_with_tools():
            return await handle_tool_calling_in_node(
                llm_with_tools=llm_with_tools,
                messages=messages,
                tools=[plotting_tool],
                max_iterations=15
            )
        
        metrics_result = await retry_with_backoff(
            call_metrics_with_tools,
            AI_ANALYSIS_CONFIG,
            "Metrics Agent with Tools"
        )
        logger.info(f"Metrics node completed analysis")
        
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
                'agent': 'metrics',
                'plot_id': plot_id,
                'timestamp': datetime.now().isoformat()
            }
            for plot_id in available_plots
        ]
        
        cost_data = {
            'agent': 'metrics',
            'execution_time': execution_time,
            'timestamp': datetime.now().isoformat(),
        }
        
        logger.info(f"Metrics analysis completed in {execution_time:.2f}s with {len(available_plots)} plots")
        
        return {
            'metrics_result': metrics_result,
            'plots': plots_data,
            'plot_storage_data': plot_storage_data,
            'costs': [cost_data],
            'available_plots': available_plots,
        }
        
    except Exception as e:
        logger.error(f"Metrics analysis node failed: {e}")
        return {
            'errors': [f"Metrics analysis failed: {str(e)}"]
        }