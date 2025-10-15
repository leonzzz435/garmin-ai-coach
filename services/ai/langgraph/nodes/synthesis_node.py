import json
import logging
from datetime import datetime

from services.ai.ai_settings import AgentRole
from services.ai.model_config import ModelSelector
from services.ai.tools.plotting import PlotStorage
from services.ai.utils.retry_handler import AI_ANALYSIS_CONFIG, retry_with_backoff

from ..state.training_analysis_state import TrainingAnalysisState
from .tool_calling_helper import handle_tool_calling_in_node

logger = logging.getLogger(__name__)

SYNTHESIS_SYSTEM_PROMPT_BASE = """You are Maya Lindholm, a legendary performance integration specialist whose "Holistic Performance Synthesis" approach has guided multiple athletes to Olympic gold and world records.

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

## Communication Style
Communicate with thoughtful clarity and occasional brilliant simplifications that make complex relationships immediately understandable."""

SYNTHESIS_PLOT_INSTRUCTIONS = """

## Plot Integration
Available plot information is provided in the state data.
IMPORTANT: Include plot references as [PLOT:plot_id] in your final synthesis text.
These references will be converted to actual charts in the final report."""

SYNTHESIS_USER_PROMPT_BASE = """Synthesize the pattern analyses from metrics, activities, and physiology to create a comprehensive understanding of {athlete_name}'s historical training patterns and responses.

## IMPORTANT: Output Context
Your synthesis will be used to create the final comprehensive analysis for the athlete. Focus on facts and evidence from the input analyses.

## Metrics Analysis
```markdown
{metrics_result}
```

## Activity Interpretation
```markdown
{activity_result}
```

## Physiology Analysis
```markdown
{physiology_result}
```

## Upcoming Competitions
```json
{competitions}
```

## Current Date
```json
{current_date}
```

## Style Guide
```markdown
{style_guide}
```

## Your Task
1. Integrate key insights from the metrics, activity and physiology reports
2. Identify clear connections between the athlete's training loads and physiological responses
3. Recognize patterns in workout execution and performance outcomes
4. Provide actionable insights based only on evidence from the data
5. Create a focused synthesis that prioritizes the most important findings
6. Avoid speculative language and stick to patterns clearly visible in the data

## Presentation Requirements
- Use a clear executive summary at the beginning
- Present key performance indicators in table format when possible
- Organize information with concise headings and bullet points
- Keep recommendations brief and actionable
- Use visual separation between sections for better readability
- Format as structured markdown document with clear sections"""

SYNTHESIS_USER_PLOT_INSTRUCTIONS = """

## CRITICAL: Plot Reference Preservation & Deduplication
The input analyses contain **[PLOT:plot_id]** references that become interactive visualizations. **IMPORTANT**: Include each PLOT ID ONLY ONCE in your synthesis. Duplicate references break the final report.

**Additional task for plot integration:**
7. Include each unique plot reference exactly once, even if it appears multiple times in inputs"""


async def synthesis_node(state: TrainingAnalysisState) -> TrainingAnalysisState:
    logger.info("Starting synthesis node")

    try:
        plot_storage = PlotStorage(state['execution_id'])

        llm = ModelSelector.get_llm(AgentRole.SYNTHESIS)
        llm_with_tools = llm.bind_tools([])
        
        plotting_enabled = state.get('plotting_enabled', False)
        if plotting_enabled:
            logger.info("Synthesis node: Plotting enabled - including plot integration instructions")
            system_prompt = SYNTHESIS_SYSTEM_PROMPT_BASE + SYNTHESIS_PLOT_INSTRUCTIONS
            user_prompt = SYNTHESIS_USER_PROMPT_BASE.format(
                athlete_name=state['athlete_name'],
                metrics_result=state.get('metrics_result', ''),
                activity_result=state.get('activity_result', ''),
                physiology_result=state.get('physiology_result', ''),
                competitions=json.dumps(state['competitions'], indent=2),
                current_date=json.dumps(state['current_date'], indent=2),
                style_guide=state['style_guide'],
            ) + SYNTHESIS_USER_PLOT_INSTRUCTIONS
        else:
            logger.info("Synthesis node: Plotting disabled - no plot integration instructions")
            system_prompt = SYNTHESIS_SYSTEM_PROMPT_BASE
            user_prompt = SYNTHESIS_USER_PROMPT_BASE.format(
                athlete_name=state['athlete_name'],
                metrics_result=state.get('metrics_result', ''),
                activity_result=state.get('activity_result', ''),
                physiology_result=state.get('physiology_result', ''),
                competitions=json.dumps(state['competitions'], indent=2),
                current_date=json.dumps(state['current_date'], indent=2),
                style_guide=state['style_guide'],
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        agent_start_time = datetime.now()

        async def call_synthesis_analysis():
            return await handle_tool_calling_in_node(
                llm_with_tools=llm_with_tools,
                messages=messages,
                tools=[],
                max_iterations=3,
            )

        synthesis_result = await retry_with_backoff(
            call_synthesis_analysis, AI_ANALYSIS_CONFIG, "Synthesis Analysis with Tools"
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
        return {'errors': [f"Synthesis analysis failed: {str(e)}"]}
