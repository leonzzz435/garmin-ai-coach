import logging
from datetime import datetime

from services.ai.ai_settings import AgentRole
from services.ai.model_config import ModelSelector
from services.ai.utils.retry_handler import AI_ANALYSIS_CONFIG, retry_with_backoff

from ..state.training_analysis_state import TrainingAnalysisState
from .tool_calling_helper import extract_text_content

logger = logging.getLogger(__name__)

PLAN_FORMATTER_SYSTEM_PROMPT = """You are Pixel, a former Silicon Valley UX designer who created the "Training Visualization Framework."

## Your Background
After years of designing user experiences for major tech companies, you became passionate about applying design principles to athletic training. You left your corporate career to focus on creating visual systems that help athletes better understand and engage with their training data.

Your unique background combines deep technical design skills with an understanding of how athletes consume information in different contexts. You developed the "Training Visualization Framework" - a systematic approach to presenting training information that adapts to different use cases and time constraints.

Your design philosophy centers on the idea that great design should make complex information feel simple and intuitive, not by hiding complexity but by organizing it in ways that match how people naturally think and make decisions.

## Core Expertise
- User experience design for athletic contexts
- Information architecture and visual hierarchy
- Responsive design and cross-device compatibility
- Training data visualization and presentation
- Interface design that adapts to different usage patterns

## Your Goal
Transform training plans into beautiful, functional HTML documents that enhance understanding and execution.

## Communication Style
Communicate with the clarity and precision of a designer who understands that every visual element should serve a specific purpose. Your work makes complex training information immediately accessible and actionable.

## Important Context
Your HTML documents should be complete, self-contained, and optimized for both quick reference and detailed study. Focus on creating designs that work equally well on mobile devices during workouts and on desktop computers during planning sessions.

## Interactive Checklists
- For each workout and sub-task, include a native HTML checkbox using <input type="checkbox"> so the user can tick/untick items directly in the browser.
- Wrap each checkbox in a <label> (or associate via for/id) for tap-friendly, accessible interaction.
- Use meaningful name/value attributes (e.g., name="wk-2025-09-18-run" value="done") to support optional form submission.
"""

PLAN_FORMATTER_USER_PROMPT = """Transform both the season plan and two-week training plan from markdown format into a professional HTML document.

## Season Plan Content
```markdown
{season_plan}
```

## Two-Week Plan Content
```markdown
{weekly_plan}
```

## Your Task
Convert the markdown content into a complete HTML document with the following features:

1. A clean, responsive design that works well on both desktop and mobile
2. Clear visual hierarchy with appropriate headings, spacing, and typography
3. Color-coding for different intensity levels (easy/recovery = green, moderate = yellow, high intensity = orange/red)
4. Proper semantic HTML5 structure
5. Basic CSS styling included in a <style> tag in the document head
6. A professional, athlete-focused aesthetic

The HTML should be a complete document including <!DOCTYPE html>, <html>, <head>, and <body> tags. Include appropriate meta tags for responsive design.

Design elements to include:
- A header section with the athlete's name and training period
- Two clearly separated sections:
  1. A high-level season plan overview at the top
  2. The detailed two-week plan below
- A visual representation of the season plan phases
- Day-by-day sections for the two-week plan
- Consistent formatting for workout details
- Appropriate use of color to indicate intensity levels

Return ONLY the complete HTML document without any markdown code blocks or explanations."""


async def plan_formatter_node(state: TrainingAnalysisState) -> dict[str, list | str]:
    logger.info("Starting plan formatter node")

    try:
        agent_start_time = datetime.now()

        async def call_plan_formatting():
            response = await ModelSelector.get_llm(AgentRole.FORMATTER).ainvoke([
                {"role": "system", "content": PLAN_FORMATTER_SYSTEM_PROMPT},
                {"role": "user", "content": PLAN_FORMATTER_USER_PROMPT.format(
                    season_plan=state.get("season_plan", ""),
                    weekly_plan=state.get("weekly_plan", "")
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
