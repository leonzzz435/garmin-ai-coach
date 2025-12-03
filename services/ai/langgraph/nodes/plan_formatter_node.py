import logging
from datetime import datetime

from services.ai.ai_settings import AgentRole
from services.ai.model_config import ModelSelector
from services.ai.utils.retry_handler import AI_ANALYSIS_CONFIG, retry_with_backoff

from ..state.training_analysis_state import TrainingAnalysisState
from .tool_calling_helper import extract_text_content

logger = logging.getLogger(__name__)

PLAN_FORMATTER_SYSTEM_PROMPT = """You are a data visualization specialist.
## Goal
Transform training plans into beautiful, functional HTML documents.
## Principles
- Clarity: Make complex training information immediately accessible.
- Hierarchy: Use visual structure to guide attention.
- Usability: Design for both desktop planning and mobile execution.
- Aesthetics: Create a professional, athlete-focused visual experience.

## Interactive Checklists
- For each workout and sub-task, include a native HTML checkbox using <input type="checkbox"> so the user can tick/untick items directly in the browser.
- Wrap each checkbox in a <label> (or associate via for/id) for tap-friendly, accessible interaction.
- Use meaningful name/value attributes (e.g., name="wk-2025-09-18-run" value="done") to support optional form submission."""

PLAN_FORMATTER_USER_PROMPT = """Transform the training plan into a professional HTML document.

## Inputs
### Season Plan
```markdown
{season_plan}
```
### 4-Week Plan
```markdown
{weekly_plan}
```

## Task
Convert the markdown content into a single, self-contained HTML document.

## Constraints
- **Compactness**: The user must see the "big picture" easily. Avoid excessive scrolling.
- **Layout**: Use a dense, information-rich layout (e.g., grid or compact cards) for the 4-week plan.
- **Usability**: Include interactive checkboxes for every workout item.
- **Design**: Professional, athlete-focused aesthetic with clear visual hierarchy.

## Output Requirements
1. **Structure**:
   - Header: Athlete name and period.
   - Section 1: Season Plan Overview (High level).
   - Section 2: 4-Week Plan (Detailed but compact).
2. **Format**: Complete HTML5 document with embedded CSS.
3. **Content**: Preserve all workout details but format them densely.
4. **Return**: ONLY the HTML code.
"""


async def plan_formatter_node(state: TrainingAnalysisState) -> dict[str, list | str]:
    logger.info("Starting plan formatter node")

    try:
        agent_start_time = datetime.now()

        def get_content(field):
            value = state.get(field, "")
            if hasattr(value, "output"):
                output = value.output
                if isinstance(output, str):
                    return output
                raise ValueError("AgentOutput contains questions, not content. HITL interaction required.")
            if isinstance(value, dict):
                return value.get("output", value.get("content", value))
            return value
        
        async def call_plan_formatting():
            response = await ModelSelector.get_llm(AgentRole.FORMATTER).ainvoke([
                {"role": "system", "content": PLAN_FORMATTER_SYSTEM_PROMPT},
                {"role": "user", "content": PLAN_FORMATTER_USER_PROMPT.format(
                    season_plan=get_content("season_plan"),
                    weekly_plan=get_content("weekly_plan")
                )},
            ])
            return extract_text_content(response)

        planning_html = await retry_with_backoff(
            call_plan_formatting, AI_ANALYSIS_CONFIG, "Plan Formatter"
        )

        execution_time = (datetime.now() - agent_start_time).total_seconds()
        logger.info(f"Plan formatting completed in {execution_time:.2f}s")

        return {
            "planning_html": planning_html,
            "costs": [{
                "agent": "plan_formatter",
                "execution_time": execution_time,
                "timestamp": datetime.now().isoformat(),
            }],
        }

    except Exception as e:
        logger.error(f"Plan formatter node failed: {e}")
        return {"errors": [f"Plan formatting failed: {str(e)}"]}
