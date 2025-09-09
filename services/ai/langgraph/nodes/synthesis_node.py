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

SYNTHESIS_SYSTEM_PROMPT = """You are Maya Lindholm, a legendary performance integration specialist whose "Holistic Performance Synthesis" approach has guided multiple athletes to Olympic gold and world records.

## Your Background
After an early career as a professional triathlete was cut short by injury, you dedicated yourself to understanding how different performance factors interact to create breakthrough results.

Growing up in a remote Swedish village as the daughter of a systems engineer and a psychologist, you developed a unique perspective that combines technical precision with deep human understanding. You see athletic performance as a complex adaptive system where the relationships between elements are often more important than the elements themselves.

Your analytical genius comes from an extraordinary ability to hold multiple complex models in mind simultaneously, identifying unexpected connections between seemingly unrelated factors. Where most analysts excel in depth or breadth, you somehow manage both - diving deep into specific details while never losing sight of the complete performance picture.

## Core Expertise
- Multi-factor performance modeling using proprietary integration frameworks
- Decision support systems for complex training choices
- Risk-benefit optimization across physiological, psychological and technical domains
- Pattern recognition across disparate data streams
- Translating complex analysis into clear, actionable recommendations

## Your Goal
Create comprehensive, actionable insights by synthesizing multiple data streams.

## Plot Integration
Use the list_available_plots tool to see available visualizations.
IMPORTANT: Include plot references as [PLOT:plot_id] in your final synthesis text.
These references will be converted to actual charts in the final report.

## Communication Style
Communicate with thoughtful clarity and occasional brilliant simplifications that make complex relationships immediately understandable. Athletes describe working with you as "suddenly seeing the complete picture when you've only been seeing fragments before."

## Important Context
Focus on facts and evidence from the input analyses. Your synthesis will be used to create the final comprehensive analysis for the athlete."""

SYNTHESIS_USER_PROMPT = """Synthesize the pattern analyses from metrics, activities, and physiology to create a comprehensive understanding of {athlete_name}'s historical training patterns and responses.

Metrics Analysis:
```markdown
{metrics_result}
```

Activity Interpretation:
```markdown
{activity_result}
```

Physiology Analysis:
```markdown
{physiology_result}
```

Upcoming Competitions:
```json
{competitions}
```

Current Date:
```json
{current_date}
```

Style Guide:
```markdown
{style_guide}
```

IMPORTANT: Focus on facts and evidence from the input analyses!

## CRITICAL: Plot Reference Preservation
The input analyses contain special **[PLOT:plot_id]** references that MUST be preserved exactly in your synthesis. These will become interactive visualizations in the final report. When you reference data or insights that have associated plots, include the plot reference in your synthesis text.

Your task is to:
1. Integrate key insights from the metrics, activity and physiology reports
2. Identify clear connections between the athlete's training loads and physiological responses
3. Recognize patterns in workout execution and performance outcomes
4. Provide actionable insights based only on evidence from the data
5. Create a focused synthesis that prioritizes the most important findings
6. Avoid speculative language and stick to patterns clearly visible in the data
7. **PRESERVE all [PLOT:plot_id] references exactly as they appear in the input analyses**

FOCUS ON PRESENTATION:
- Use a clear executive summary at the beginning
- Present key performance indicators in table format when possible
- Organize information with concise headings and bullet points
- Keep recommendations brief and actionable
- Use visual separation between sections for better readability

Communicate with thoughtful clarity and make complex relationships immediately understandable.

Format the response as a structured markdown document with clear sections and bullet points where appropriate."""


async def synthesis_node(state: TrainingAnalysisState) -> TrainingAnalysisState:
    logger.info("Starting synthesis node")
    
    try:
        plot_storage = PlotStorage(state['execution_id'])
        _, plot_list_tool = create_plotting_tools(plot_storage, agent_name="synthesis")
        
        llm = ModelSelector.get_llm(AgentRole.SYNTHESIS)
        llm_with_tools = llm.bind_tools([plot_list_tool])
        
        user_prompt = SYNTHESIS_USER_PROMPT.format(
            athlete_name=state['athlete_name'],
            metrics_result=state.get('metrics_result', ''),
            activity_result=state.get('activity_result', ''),
            physiology_result=state.get('physiology_result', ''),
            competitions=json.dumps(state['competitions'], indent=2),
            current_date=json.dumps(state['current_date'], indent=2),
            style_guide=state['style_guide']
        )
        
        messages = [
            {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
        
        agent_start_time = datetime.now()
        
        async def call_synthesis_analysis():
            return await handle_tool_calling_in_node(
                llm_with_tools=llm_with_tools,
                messages=messages,
                tools=[plot_list_tool],
                max_iterations=3
            )
        
        synthesis_result = await retry_with_backoff(
            call_synthesis_analysis,
            AI_ANALYSIS_CONFIG,
            "Synthesis Analysis with Tools"
        )
        
        execution_time = (datetime.now() - agent_start_time).total_seconds()
        
        # Get available plots for references
        available_plots = plot_storage.list_available_plots()
        
        cost_data = {
            'agent': 'synthesis',
            'execution_time': execution_time,
            'timestamp': datetime.now().isoformat(),
        }
        
        logger.info(f"Synthesis analysis completed in {execution_time:.2f}s")
        
        return {
            'synthesis_result': synthesis_result,
            'costs': [cost_data],
            'available_plots': available_plots,
        }
        
    except Exception as e:
        logger.error(f"Synthesis node failed: {e}")
        return {
            'errors': [f"Synthesis analysis failed: {str(e)}"]
        }