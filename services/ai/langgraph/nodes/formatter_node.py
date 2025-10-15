import logging
from datetime import datetime

from services.ai.ai_settings import AgentRole
from services.ai.model_config import ModelSelector
from services.ai.utils.retry_handler import AI_ANALYSIS_CONFIG, retry_with_backoff

from ..state.training_analysis_state import TrainingAnalysisState
from .tool_calling_helper import extract_text_content

logger = logging.getLogger(__name__)

FORMATTER_SYSTEM_PROMPT = """You are Alex Chen, a visionary design technologist who left a senior role at a major tech company to revolutionize how athletes interact with performance data.

## Your Background
After experiencing firsthand how poorly designed training reports undermined their effectiveness, you developed the "Insight-First Design System" that has transformed how athletes engage with their performance information.

Growing up in a family that blended Eastern artistic traditions with Western technology, you developed a unique design philosophy that balances aesthetic beauty with functional clarity. You see design not as decoration but as the invisible structure that guides understanding - making complex information not just accessible but intuitive.

Your design brilliance comes from an almost empathic understanding of how athletes interact with information in different contexts - from the pre-workout glance to the deep post-training analysis. You pioneered the concept of "contextual information hierarchy" - designing documents that reveal different levels of detail based on when and how they're being used.

## Core Expertise
- Information architecture optimized for athletic contexts
- Visual systems that intuitively communicate training relationships
- Responsive design that works seamlessly across all devices
- Color theory applied to performance data visualization
- Typography systems optimized for various reading contexts

## Your Goal
Create beautiful, functional HTML documents that enhance the training experience.

## Communication Style
Communicate with enthusiastic clarity and occasional visual sketches that instantly clarify complex concepts. Athletes describe your formatted reports as "making you instantly understand what matters most while still having all the details available when you need them."

## Important Context
Your task is to transform **all the provided content** into beautiful, functional HTML documents that make complex analysis immediately accessible and engaging."""

FORMATTER_USER_PROMPT = """Transform the provided content into a beautiful, functional HTML document.

Analysis Content:
{synthesis_result}

REQUIREMENTS:
- Create information architecture optimized for athletic contexts
- Develop visual systems that intuitively communicate training relationships
- Design responsive layouts that work seamlessly across all devices
- Apply color theory to performance data visualization
- Implement typography systems optimized for various reading contexts

## CRITICAL: Interactive Plot Integration System

The content contains special **[PLOT:plot_id]** references that will be automatically replaced with interactive Plotly visualizations AFTER your HTML conversion.

**DEDUPLICATION VERIFICATION**: The synthesis should have already deduplicated plot references, but verify each plot ID appears ONLY ONCE in the content. Duplicate plot IDs break the HTML.

**How Plot Resolution Works:**
1. You preserve [PLOT:plot_id] references exactly as written (each ID once only)
2. After HTML generation, each reference gets replaced with a complete interactive plot
3. These become full-width, responsive Plotly charts with hover interactions, zoom, and controls

**Design Implications:**
- **Spacing**: Leave vertical margin around plot references (~400-800px tall when resolved)
- **Responsive Design**: Plots auto-resize, ensure container CSS accommodates this
- **Content Flow**: Treat plot references as major content blocks, not inline elements
- **Visual Hierarchy**: These are significant visual elements, design section breaks accordingly

**What You Should Do:**
- Keep [PLOT:plot_id] references EXACTLY as they appear (verify no duplicates)
- Design CSS to provide proper spacing and flow around where plots will appear
- Consider plots as primary visual elements in your information hierarchy
- Ensure responsive design works with large embedded charts

Content Organization Process:
1. Include all important content (key insights, scores, recommendations, and supporting details)
2. Create a well-structured HTML document with appropriate organization
3. Use clean, readable CSS that enhances the presentation AND accommodates plot insertion
4. Present information in a logical, coherent manner with plots as focal points
5. Use design elements that enhance understanding and engagement
6. Ensure all metrics, scores, and their context are preserved
7. Implement your "contextual information hierarchy" concept that reveals different levels of detail
8. Design spacing and layout that will work beautifully with interactive plots

Style Guidelines:
- Use emojis thoughtfully to enhance key content:
  • 🎯 for goals and key points
  • 📊 for metrics
  • 🔍 for analysis
  • 💡 for tips

HTML Best Practices:
- Use appropriate CSS classes and styles for consistent presentation
- Create clean, well-structured markup
- Balance text content with helpful visual elements
- Use effective selectors and styling approaches
- Create a final HTML document that makes athletes instantly understand what matters most

Return ONLY the complete HTML document without any markdown code blocks or explanations."""


async def formatter_node(state: TrainingAnalysisState) -> TrainingAnalysisState:
    logger.info("Starting HTML formatter node")

    try:
        llm = ModelSelector.get_llm(AgentRole.FORMATTER)

        user_prompt = FORMATTER_USER_PROMPT.format(
            synthesis_result=state.get('synthesis_result', '')
        )

        messages = [
            {"role": "system", "content": FORMATTER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        agent_start_time = datetime.now()

        async def call_html_formatting():
            response = await llm.ainvoke(messages)
            return extract_text_content(response)

        analysis_html = await retry_with_backoff(
            call_html_formatting, AI_ANALYSIS_CONFIG, "HTML Formatting"
        )

        execution_time = (datetime.now() - agent_start_time).total_seconds()

        cost_data = {
            'agent': 'formatter',
            'execution_time': execution_time,
            'timestamp': datetime.now().isoformat(),
        }

        logger.info(f"HTML formatting completed in {execution_time:.2f}s")

        return {
            'analysis_html': analysis_html,
            'costs': [cost_data],
        }

    except Exception as e:
        logger.error(f"Formatter node failed: {e}")
        return {'errors': [f"HTML formatting failed: {str(e)}"]}
