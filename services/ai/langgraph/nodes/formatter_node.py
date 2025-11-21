import logging
from datetime import datetime

from services.ai.ai_settings import AgentRole
from services.ai.model_config import ModelSelector
from services.ai.utils.retry_handler import AI_ANALYSIS_CONFIG, retry_with_backoff

from ..state.training_analysis_state import TrainingAnalysisState
from .tool_calling_helper import extract_text_content

logger = logging.getLogger(__name__)

FORMATTER_SYSTEM_PROMPT = """You are a design technologist.
## Goal
Create beautiful, functional HTML documents for athletic performance data.
## Principles
- Clarity: Design for instant understanding.
- Hierarchy: Use visual structure to guide attention.
- Aesthetics: Balance beauty with function."""

FORMATTER_USER_PROMPT_BASE = """Transform this content into a beautiful HTML document.

## Content
```markdown
{synthesis_result}
```

## Task
Create a complete HTML document with:
1. **Structure**: Logical organization with clear headings.
2. **Design**: Clean CSS, responsive layout, professional typography.
3. **Visuals**: Use emojis and color to enhance data (e.g., 🎯 goals, 📊 metrics).
4. **Completeness**: Include ALL content, metrics, and scores.

## Output
Return ONLY the complete HTML document."""

FORMATTER_PLOT_INSTRUCTIONS = """
## Plot Integration
- **Preserve**: Keep `[PLOT:plot_id]` references EXACTLY as written.
- **Layout**: Treat them as major visual blocks (full-width).
- **Spacing**: Ensure CSS provides vertical space (~500px) for the interactive charts that will replace them."""


async def formatter_node(state: TrainingAnalysisState) -> dict[str, list | str]:
    logger.info("Starting HTML formatter node")

    try:
        plotting_enabled = state.get("plotting_enabled", False)
        logger.info(
            f"Formatter node: Plotting {'enabled' if plotting_enabled else 'disabled'} - "
            f"{'including' if plotting_enabled else 'no'} plot integration instructions"
        )

        agent_start_time = datetime.now()

        async def call_html_formatting():
            synthesis_result = extract_text_content(state.get("synthesis_result", ""))
            
            response = await ModelSelector.get_llm(AgentRole.FORMATTER).ainvoke([
                {"role": "system", "content": FORMATTER_SYSTEM_PROMPT},
                {"role": "user", "content": (
                    FORMATTER_USER_PROMPT_BASE.format(synthesis_result=synthesis_result)
                    + (FORMATTER_PLOT_INSTRUCTIONS if plotting_enabled else "")
                )},
            ])
            return extract_text_content(response)

        analysis_html = await retry_with_backoff(
            call_html_formatting, AI_ANALYSIS_CONFIG, "HTML Formatting"
        )

        execution_time = (datetime.now() - agent_start_time).total_seconds()
        logger.info(f"HTML formatting completed in {execution_time:.2f}s")

        return {
            "analysis_html": analysis_html,
            "costs": [{
                "agent": "formatter",
                "execution_time": execution_time,
                "timestamp": datetime.now().isoformat(),
            }],
        }

    except Exception as e:
        logger.error(f"Formatter node failed: {e}")
        return {"errors": [f"HTML formatting failed: {str(e)}"]}
