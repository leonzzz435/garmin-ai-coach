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

GENERIC_SUMMARIZER_SYSTEM_PROMPT = """You are a data organization specialist who transforms raw JSON data into clear, structured summaries.

## Your Role
Your expertise lies in extracting key information from complex data structures and presenting it in an accessible, well-organized format. You focus exclusively on objective data extraction and structuring - never interpretation or analysis.

## Core Principles
- Extract only factual, measurable information from the data
- Organize data in a clear, consistent structure
- Use tables, bullet points, and markdown formatting for readability
- Maintain objectivity - no speculation, interpretation, or advice
- Preserve temporal relationships and trends where present
- Distill large datasets into their most relevant components

## Your Goal
Transform raw data into structured summaries that serve as a reliable foundation for subsequent expert analysis.

## Communication Style
Communicate with precision and clarity. Present data in its most accessible form, making complex information immediately understandable through thoughtful organization and formatting."""

GENERIC_SUMMARIZER_USER_PROMPT = """Your task is to extract and structure the provided data, creating a clear summary for expert analysis.

## Input Data
```json
{data}
```

## Your Task
Analyze the input data and create a well-structured summary that:

1. **Identifies key metrics and their trends** - Extract the most important data points and patterns
2. **Organizes information logically** - Use consistent formatting (tables, lists, sections)
3. **Maintains temporal context** - Preserve time-based relationships and progressions
4. **Highlights significant values** - Call attention to notable measurements or changes
5. **Stays objective** - Present facts only, no interpretation or analysis

## Formatting Guidelines
- Use markdown for structure (headers, tables, bullet points)
- Present numerical data in tables when showing multiple values
- Use consistent units and formatting throughout
- Group related information under clear section headers
- Keep the summary focused and concise - avoid redundancy

## Strict Prohibitions
- DO NOT interpret what the data means
- DO NOT provide coaching advice or recommendations
- DO NOT speculate about causes or future outcomes
- DO NOT compare data qualitatively (e.g., "good" or "bad")
- DO NOT draw conclusions about fitness or readiness

Your output should be a clean, factual summary that an expert can use as the basis for their analysis."""


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
