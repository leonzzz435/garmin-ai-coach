import logging
from datetime import datetime
import json

from services.ai.model_config import ModelSelector
from services.ai.ai_settings import AgentRole
from services.ai.utils.retry_handler import retry_with_backoff, AI_ANALYSIS_CONFIG

from ..state.training_analysis_state import TrainingAnalysisState

logger = logging.getLogger(__name__)

SEASON_PLANNER_SYSTEM_PROMPT = """You are Coach Magnus Thorsson, a legendary ultra-endurance champion from Iceland who developed the "Thorsson Method" of periodization.

## Your Background
As one of the most successful ultra-endurance athletes of your generation, you revolutionized training periodization by developing systematic approaches to long-term athletic development. Your "Thorsson Method" combines traditional Icelandic training philosophies with cutting-edge sports science.

Growing up in Iceland's harsh but beautiful environment taught you the importance of patience, systematic progression, and working with natural rhythms rather than against them. Your athletic career included victories in some of the world's most challenging ultra-endurance events, but your greatest achievements came after retiring from competition.

Your coaching genius comes from an intuitive understanding of how the human body adapts to stress over extended time periods. You see training as a conversation between athlete and environment, where the goal is not to force adaptation but to create conditions where optimal development naturally occurs.

## Core Expertise
- Long-term periodization and season planning
- Balancing training stress with recovery across extended time periods
- Competition preparation and peak timing
- Environmental and seasonal training adaptations
- Systematic progression methodologies

## Your Goal
Create high-level season plans that provide frameworks for long-term athletic development.

## Communication Style
Communicate with the quiet confidence of someone who has both achieved at the highest level and successfully guided others to do the same. Your guidance reflects deep understanding of both the science and art of endurance training.

## Important Context
Your season plans will be used to contextualize detailed weekly training plans. Focus on providing clear frameworks and high-level guidance that can be adapted to specific training situations."""

SEASON_PLANNER_USER_PROMPT = """Based on the athlete's competition schedule, create a high-level season plan covering the next 12-24 weeks.

## IMPORTANT: Output Context
This plan will be passed to a weekly planning agent and will not be shown directly to the athlete. Write your analysis referring to "the athlete" as this is an intermediate report for other coaching professionals.

## Athlete Information
- Name: {athlete_name}
- Current Date: {current_date}
- Upcoming Competitions: {competitions}

## Your Task
Create a high-level season plan that provides a framework for the next 12-24 weeks of training, leading up to key competitions. This should be concise yet informative, focusing on:

1. PLAN OVERVIEW: A brief summary of the season plan structure and progression
2. TRAINING PHASES: Define key training phases with approximate date ranges
3. PHASE DETAILS: For each phase, provide:
   - Primary focus and goals
   - Weekly volume targets (approximate)
   - Intensity distribution
   - Key workout types

KEEP THIS CONCISE! This is a high-level plan that will contextualize a more detailed two-week plan.

Format the response as a structured markdown document with clear headings and bullet points."""


async def season_planner_node(state: TrainingAnalysisState) -> TrainingAnalysisState:
    logger.info("Starting season planner node")
    
    try:
        llm = ModelSelector.get_llm(AgentRole.SEASON_PLANNER)
        
        user_prompt = SEASON_PLANNER_USER_PROMPT.format(
            athlete_name=state['athlete_name'],
            current_date=json.dumps(state['current_date'], indent=2),
            competitions=json.dumps(state['competitions'], indent=2)
        )
        
        messages = [
            {"role": "system", "content": SEASON_PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
        
        agent_start_time = datetime.now()
        
        async def call_season_planning():
            response = await llm.ainvoke(messages)
            return response.content if hasattr(response, 'content') else str(response)
        
        season_plan = await retry_with_backoff(
            call_season_planning,
            AI_ANALYSIS_CONFIG,
            "Season Planning"
        )
        
        execution_time = (datetime.now() - agent_start_time).total_seconds()
        
        cost_data = {
            'agent': 'season_planner',
            'execution_time': execution_time,
            'timestamp': datetime.now().isoformat(),
        }
        
        logger.info(f"Season planning completed in {execution_time:.2f}s")
        
        return {
            'season_plan': season_plan,
            'costs': [cost_data],
        }
        
    except Exception as e:
        logger.error(f"Season planner node failed: {e}")
        return {
            'errors': [f"Season planning failed: {str(e)}"]
        }