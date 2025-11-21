import json
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from services.ai.ai_settings import AgentRole
from services.ai.model_config import ModelSelector
from services.ai.utils.retry_handler import AI_ANALYSIS_CONFIG, retry_with_backoff

from ..state.training_analysis_state import TrainingAnalysisState
from .prompt_components import AgentType, get_workflow_context
from .tool_calling_helper import extract_text_content

logger = logging.getLogger(__name__)

GENERIC_SUMMARIZER_SYSTEM_PROMPT = """You are a data preservation specialist.
## Goal
Detect and preserve ALL important metrics in raw data.
## Principles
- Preserve: Keep all meaningful numbers (measurements, counts, rates).
- Detect: Distinguish signal (measurements) from noise (IDs, nulls).
- Organize: Use tables and lists.
- No Hidden Aggregation: Always show individual values behind averages."""

GENERIC_SUMMARIZER_USER_PROMPT = """Extract and organize ALL important metrics from this data:

```json
{data}
```

## Task
1. Preserve every meaningful measurement.
2. Use tables for related data points.
3. Maintain full temporal sequences.
4. Highlight notable values (highs/lows) with context.

## Format
- Markdown tables for numeric data.
- Clear section headers.
- Consistent units.

## Rules
- Include all numeric measurements.
- Exclude repeated nulls and structural IDs.
- NEVER skip numbers for conciseness.
- NEVER interpret or speculate.

Deliver a complete, number-rich summary."""


def create_data_summarizer_node(
    node_name: str,
    agent_role: AgentRole,
    data_extractor: Callable[[TrainingAnalysisState], dict[str, Any]],
    state_output_key: str,
    agent_type: AgentType,
    system_prompt: str | None = None,
    user_prompt: str | None = None,
) -> Callable:
    
    workflow_context = get_workflow_context(agent_type)
    base_system_prompt = system_prompt or GENERIC_SUMMARIZER_SYSTEM_PROMPT
    effective_system_prompt = base_system_prompt + workflow_context
    effective_user_prompt = user_prompt or GENERIC_SUMMARIZER_USER_PROMPT
    
    async def summarizer_node(state: TrainingAnalysisState) -> dict[str, list | str]:
        logger.info(f"Starting {node_name} node")
        
        try:
            agent_start_time = datetime.now()
            
            data_to_summarize = data_extractor(state)
            
            async def call_llm():
                response = await ModelSelector.get_llm(agent_role).ainvoke([
                    {"role": "system", "content": effective_system_prompt},
                    {"role": "user", "content": effective_user_prompt.format(
                        data=json.dumps(data_to_summarize, indent=2)
                    )},
                ])
                return extract_text_content(response)
            
            summary = await retry_with_backoff(
                call_llm, AI_ANALYSIS_CONFIG, f"{node_name}"
            )
            
            execution_time = (datetime.now() - agent_start_time).total_seconds()
            logger.info(f"{node_name} completed in {execution_time:.2f}s")
            
            return {
                state_output_key: summary,
                "costs": [{
                    "agent": state_output_key.replace("_summary", "_summarizer"),
                    "execution_time": execution_time,
                    "timestamp": datetime.now().isoformat(),
                }],
            }
        
        except Exception as e:
            logger.error(f"{node_name} node failed: {e}")
            return {"errors": [f"{node_name} failed: {str(e)}"]}
    
    return summarizer_node
