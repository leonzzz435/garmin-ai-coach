import logging
from datetime import datetime
import json

from services.ai.model_config import ModelSelector
from services.ai.ai_settings import AgentRole
from services.ai.utils.retry_handler import retry_with_backoff, AI_ANALYSIS_CONFIG

from ..state.training_analysis_state import TrainingAnalysisState

logger = logging.getLogger(__name__)

ACTIVITY_DATA_SYSTEM_PROMPT = """You are Dr. Marcus Chen, a data organization specialist who revolutionized how athletic data is processed and structured.

## Your Background
With a PhD in Computer Science specializing in data representation and a background as a competitive cyclist, you bridged the gap between raw sports data and meaningful, structured information.

Growing up in Singapore with a mathematician father and librarian mother, you developed an extraordinary ability to organize complex information systematically. Your education at MIT and subsequent work with sports technology companies led you to develop the "Objective Activity Framework" - a methodology that transforms complex activity data into clear, structured summaries.

Your professional approach is characterized by meticulous attention to detail and absolute objectivity. You never speculate or interpret - you simply present the data in its most accessible and structurally sound format. Your work focuses exclusively on what can be directly observed and measured in the data.

## Core Expertise
- Structured data extraction from complex activity files
- Consistent taxonomic organization of workout components
- Development of standardized templates for activity representation
- Objective quantification of training session parameters
- Precise distillation of complex data into structured formats

## Your Goal
Extract and structure training activity data with factual precision.

## Communication Style
Communicate with calculated precision and complete objectivity. Athletes and coaches appreciate your ability to transform overwhelming data into clear, factual summaries that serve as a reliable foundation for subsequent analysis and interpretation."""

ACTIVITY_DATA_USER_PROMPT = """Your task is to objectively describe the athlete's recent training activities, transforming raw data into structured, factual summaries.

Input Data:
```json
{data}
```

Your task is to:
1. Extract key metrics from each activity (date, type, duration, distance)
2. Describe each lap's effort (pace/power/HR) objectively using tables
3. Summarize zone distribution with percentages in a consistent format
4. Present data in a structured, accessible format
5. STRICTLY AVOID any interpretation, coaching advice, or speculation

FORMATTING REQUIREMENTS:
- Use consistent formatting for all activities
- Present lap data in tables with columns for distance, duration, pace/power, heart rate
- Use bullet points for key metrics
- Include zone distribution tables for each activity
- Maintain consistent units (km/miles, min/km, watts, etc.)

STRICT PROHIBITION AGAINST INTERPRETATION:
- Do NOT evaluate if workouts were "good" or "bad"
- Do NOT speculate about athlete's feelings or sensations
- Do NOT suggest improvements or modifications
- Do NOT draw conclusions about fitness or readiness
- Do NOT compare workouts to each other qualitatively

Format each activity using this template:

# Activity: [Date - Type]

## Overview
* Duration: [time]
* Distance: [distance]
* Elevation Gain: [elevation]
* Average Heart Rate: [HR]
* Average Pace/Power: [pace/power]

## Lap Details
| Lap | Distance | Duration | Avg Pace | Avg HR | Max HR |
|-----|----------|----------|----------|--------|--------|
| 1   | x.x km   | mm:ss    | x:xx/km  | xxx    | xxx    |
| 2   | x.x km   | mm:ss    | x:xx/km  | xxx    | xxx    |

Repeat this format for each activity, organizing them chronologically from newest to oldest."""


async def activity_data_node(state: TrainingAnalysisState) -> TrainingAnalysisState:
    logger.info("Starting activity data extraction node")
    
    try:
        llm = ModelSelector.get_llm(AgentRole.ACTIVITY_DATA)
        
        user_prompt = ACTIVITY_DATA_USER_PROMPT.format(
            data=json.dumps(state['garmin_data'].get('activities', []), indent=2)
        )
        
        messages = [
            {"role": "system", "content": ACTIVITY_DATA_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
        
        agent_start_time = datetime.now()
        
        async def call_activity_data_extraction():
            response = await llm.ainvoke(messages)
            return response.content if hasattr(response, 'content') else str(response)
        
        activity_summary = await retry_with_backoff(
            call_activity_data_extraction,
            AI_ANALYSIS_CONFIG,
            "Activity Data Extraction"
        )
        
        execution_time = (datetime.now() - agent_start_time).total_seconds()
        
        cost_data = {
            'agent': 'activity_data',
            'execution_time': execution_time,
            'timestamp': datetime.now().isoformat(),
        }
        
        logger.info(f"Activity data extraction completed in {execution_time:.2f}s")
        
        return {
            'activity_summary': activity_summary,
            'costs': [cost_data],
        }
        
    except Exception as e:
        logger.error(f"Activity data node failed: {e}")
        return {
            'errors': [f"Activity data extraction failed: {str(e)}"]
        }