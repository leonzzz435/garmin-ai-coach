from services.ai.ai_settings import AgentRole

from ..state.training_analysis_state import TrainingAnalysisState
from .data_summarizer_node import create_data_summarizer_node

ACTIVITY_SUMMARIZER_SYSTEM_PROMPT = """You are a data organization specialist.
## Goal
Extract and structure training activity data with factual precision.
## Principles
- Be objective: Present data without interpretation.
- Be precise: Preserve exact metrics and units.
- Be structured: Use consistent formatting."""

ACTIVITY_SUMMARIZER_USER_PROMPT = """Objectively describe the athlete's recent training activities.

Input Data:
```json
{data}
```

## Task
1. Extract key metrics (date, type, duration, distance).
2. Describe lap efforts (pace/power/HR) in tables.
3. Summarize zone distributions.
4. STRICTLY NO interpretation or coaching advice.

## Format Template
# Activity: [Date - Type]

## Overview
* Duration: [time]
* Distance: [distance]
* Elevation: [elevation]
* Avg HR: [HR] | Avg Pace/Power: [pace/power] 

## Lap Details
| Lap | Dist | Time | Pace | Avg HR | Max HR | ... |
|-----|------|------|------|--------|--------|-----|
| 1   | ...  | ...  | ...  | ...    | ...    | ... |

Repeat for each activity, newest to oldest."""


def extract_activity_data(state: TrainingAnalysisState) -> dict:
    return state["garmin_data"].get("recent_activities", [])


activity_summarizer_node = create_data_summarizer_node(
    node_name="Activity Summarizer",
    agent_role=AgentRole.SUMMARIZER,
    data_extractor=extract_activity_data,
    state_output_key="activity_summary",
    agent_type="activity_summarizer",
    system_prompt=ACTIVITY_SUMMARIZER_SYSTEM_PROMPT,
    user_prompt=ACTIVITY_SUMMARIZER_USER_PROMPT,
)
