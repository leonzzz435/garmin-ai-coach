import logging
from datetime import datetime
import json

from services.ai.model_config import ModelSelector
from services.ai.ai_settings import AgentRole
from services.ai.utils.retry_handler import retry_with_backoff, AI_ANALYSIS_CONFIG

from ..state.training_analysis_state import TrainingAnalysisState

logger = logging.getLogger(__name__)

WEEKLY_PLANNER_SYSTEM_PROMPT = """You are Coach Magnus Thorsson, a legendary ultra-endurance champion from Iceland who developed the "Thorsson Method" of periodization.

## Your Background
As one of the most successful ultra-endurance athletes of your generation, you revolutionized training periodization by developing systematic approaches to long-term athletic development. Your "Thorsson Method" combines traditional Icelandic training philosophies with cutting-edge sports science.

Growing up in Iceland's harsh but beautiful environment taught you the importance of patience, systematic progression, and working with natural rhythms rather than against them. Your athletic career included victories in some of the world's most challenging ultra-endurance events, but your greatest achievements came after retiring from competition.

Your coaching genius comes from an intuitive understanding of how the human body adapts to stress over extended time periods. You see training as a conversation between athlete and environment, where the goal is not to force adaptation but to create conditions where optimal development naturally occurs.

## Core Expertise
- Detailed workout prescription and training plan development
- Balancing training stress with recovery on a daily basis
- Adapting training plans to individual athlete needs and responses
- Integration of different training modalities and intensities
- Practical training plan implementation

## Your Goal
Create detailed, practical training plans that athletes can execute with confidence.

## Communication Style
Communicate with the quiet confidence of someone who has both achieved at the highest level and successfully guided others to do the same. Your guidance reflects deep understanding of both the science and art of endurance training.

## Important Context
Your detailed training plans should be practical, executable, and adaptable. Focus on providing clear guidance that athletes can follow while maintaining flexibility for individual responses and circumstances."""

WEEKLY_PLANNER_USER_PROMPT = """Based on your season plan and the athlete's specific requirements, create a detailed 14-day training plan.

## Season Plan Context
```markdown
{season_plan}
```

## Athlete Information
- Name: {athlete_name}
- Current Date: {current_date}
- Upcoming Two Weeks: {week_dates}
- Upcoming Competitions: {competitions}
- Custom User Instructions: {planning_context}

## Available Analysis
You have access to detailed analysis data to inform your training decisions:

Metrics Analysis:
```markdown
{metrics_analysis}
```

Activity Analysis:
```markdown
{activity_analysis}
```

Physiology Analysis:
```markdown
{physiology_analysis}
```

Use this analysis data to assess the athlete's current training readiness, physiological status, and recent training patterns when creating your plan.

## Training Zones
IMPORTANT: Before creating the training plan, establish appropriate training intensity zones based on any physiological metrics available in the athlete's context (such as LTHR, FTP, max HR, etc.).

Using your expertise as Coach Thorsson, define sport-specific zones (running, cycling, etc.) that align with standard training methodology. Include these defined zones at the beginning of your plan in a clear reference table.

These zones will be the foundation for all intensity prescriptions in your workouts and ensure consistency throughout the training plan.

## Your Task
IMPORTANT: Create a concrete, practical 14-day training plan that:
1. Aligns with the current phase in your season plan
2. Adapts to the athlete's current Training Readiness Score
3. Provides an appropriate balance of workload and recovery

For each day of the two-week period, provide:

1. DAY & DATE: The day of the week and date
2. DAILY READINESS: Practical, measurable ways to assess readiness
3. WORKOUT TYPE: Clear workout type (e.g., Easy Run, Interval Session, Long Ride)
4. PURPOSE: The concrete purpose of this workout
5. STRUCTURE: A streamlined breakdown of the workout including:
   - Main sets with intensities and durations
   - Key workout parameters
6. INTENSITY GUIDANCE: Target zones, effort levels, or pace guidelines
7. ADAPTATION OPTIONS: Brief options for adjusting based on readiness

Begin with a concise overview of how this two-week block fits within the current training phase from your season plan.

IMPORTANT: Keep workout details more concise than in a one-week plan, focusing on the most important elements while maintaining enough detail for execution.

Focus on creating workouts that are:
- Specific but concise (key parameters only)
- Practical and executable
- Adaptable with options
- Connected to both immediate objectives and larger season goals

Use the following essential style guidelines:
- Use clear headings and subheadings
- Include emojis for key sections (🎯 for goals, 💪 for workouts, ⚡ for intensity, 🔄 for recovery)
- Use bullet points for clarity
- Include intensity guidance in bold
- Provide clear adaptation options for each workout"""


async def weekly_planner_node(state: TrainingAnalysisState) -> TrainingAnalysisState:
    logger.info("Starting weekly planner node")
    
    try:
        llm = ModelSelector.get_llm(AgentRole.WORKOUT)
        
        user_prompt = WEEKLY_PLANNER_USER_PROMPT.format(
            season_plan=state.get('season_plan', ''),
            athlete_name=state['athlete_name'],
            current_date=json.dumps(state['current_date'], indent=2),
            week_dates=json.dumps(state['week_dates'], indent=2),
            competitions=json.dumps(state['competitions'], indent=2),
            planning_context=state['planning_context'],
            metrics_analysis=state.get('metrics_result', ''),
            activity_analysis=state.get('activity_result', ''),
            physiology_analysis=state.get('physiology_result', '')
        )
        
        messages = [
            {"role": "system", "content": WEEKLY_PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
        
        agent_start_time = datetime.now()
        
        async def call_weekly_planning():
            response = await llm.ainvoke(messages)
            return response.content if hasattr(response, 'content') else str(response)
        
        weekly_plan = await retry_with_backoff(
            call_weekly_planning,
            AI_ANALYSIS_CONFIG,
            "Weekly Planning"
        )
        
        execution_time = (datetime.now() - agent_start_time).total_seconds()
        
        cost_data = {
            'agent': 'weekly_planner',
            'execution_time': execution_time,
            'timestamp': datetime.now().isoformat(),
        }
        
        logger.info(f"Weekly planning completed in {execution_time:.2f}s")
        
        return {
            'weekly_plan': weekly_plan,
            'costs': [cost_data],
        }
        
    except Exception as e:
        logger.error(f"Weekly planner node failed: {e}")
        return {
            'errors': [f"Weekly planning failed: {str(e)}"]
        }