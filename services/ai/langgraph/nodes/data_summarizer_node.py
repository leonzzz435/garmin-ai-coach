import json
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from services.ai.ai_settings import AgentRole
from services.ai.model_config import ModelSelector
from services.ai.utils.retry_handler import AI_ANALYSIS_CONFIG, retry_with_backoff

from ..state.training_analysis_state import TrainingAnalysisState
from .tool_calling_helper import extract_text_content

logger = logging.getLogger(__name__)

GENERIC_SUMMARIZER_SYSTEM_PROMPT = """You are a meticulous data preservation specialist. Your job is to detect important metrics in raw data and organize them comprehensively - ensuring NO meaningful number is lost.

## Core Principles
- Preserve ALL important numeric values - measurements, metrics, counts, rates
- Detect what matters: actual measurements vs. structural noise (nulls, IDs)
- Use tables, lists, and sections to organize without reducing
- Show complete temporal sequences when time is a factor

## Critical Rule: No Hidden Aggregation
Never hide individual values behind aggregates alone. When showing averages or ranges, ALWAYS include the underlying numbers. For example:
- ✓ Show average + table of individual values
- ✗ Show only the average
- ✓ State range + show what creates it
- ✗ Replace data points with range alone

## Your Mandate
Organize for clarity, but never sacrifice completeness. When uncertain if a number matters, include it. Your output must be a trustworthy, complete data source."""

GENERIC_SUMMARIZER_USER_PROMPT = """Extract and organize ALL important metrics from this data:

```json
{data}
```

## Create a structured summary that:
1. Preserves every meaningful measurement and value
2. Uses tables extensively for multiple related data points
3. Maintains full temporal sequences (all dated entries)
4. Groups logically by category or time period
5. Highlights notable values (highs, lows, recent) within full context

## Format with:
- Markdown tables for side-by-side numeric data
- Clear section headers for logical grouping
- Bullet lists for single values or explanations
- Consistent units throughout

## Include:
- All numeric measurements and metrics
- Complete temporal sequences
- Individual values even when showing aggregates
- Notable values with their context

## Exclude only:
- Repeated nulls that add no information
- Structural IDs that aren't measurements
- Truly redundant duplicates

## Never:
- Skip numbers to be "concise"
- Aggregate without showing underlying values
- Interpret, advise, or speculate
- Use qualitative judgments (good/bad)

Deliver a complete, number-rich summary for expert analysis."""


def create_data_summarizer_node(
    node_name: str,
    agent_role: AgentRole,
    data_extractor: Callable[[TrainingAnalysisState], dict[str, Any]],
    state_output_key: str,
    system_prompt: str | None = None,
    user_prompt: str | None = None,
) -> Callable:
    
    effective_system_prompt = system_prompt or GENERIC_SUMMARIZER_SYSTEM_PROMPT
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
