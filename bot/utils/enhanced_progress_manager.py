import logging
from datetime import datetime

from telegram.ext import ContextTypes

from .progress_manager import ProgressManager

logger = logging.getLogger(__name__)


class DetailedProgressManager(ProgressManager):

    def __init__(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
        super().__init__(context, chat_id)
        self.start_time = None
        self.analysis_stats = {
            'agents_completed': 0,
            'total_agents': 10,  # Required by ProgressIntegratedCostTracker
            'plots_created': 0,
            'tool_calls': 0,
            'total_cost_usd': 0.0,
            'total_tokens': 0,
        }

    def _format_duration(self, start_time: datetime) -> str:
        if not start_time:
            return "0s"
        duration = datetime.now() - start_time
        if duration.seconds < 60:
            return f"{duration.seconds}s"
        else:
            minutes = duration.seconds // 60
            seconds = duration.seconds % 60
            return f"{minutes}m {seconds}s"

    def _escape_markdown(self, text: str) -> str:
        special_chars = [
            '_',
            '*',
            '[',
            ']',
            '(',
            ')',
            '~',
            '`',
            '>',
            '#',
            '+',
            '-',
            '=',
            '|',
            '{',
            '}',
            '.',
            '!',
        ]
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text

    def _format_cost(self, cost: float) -> str:
        return f"${cost:.4f}".replace('.', '\\.')

    async def start_detailed_analysis(self) -> None:
        self.start_time = datetime.now()
        initial_message = "🚀 *Starting AI coach analysis\\.\\.\\.*"
        await self.start(initial_message)

    async def update_cost_tracking(
        self, cost_usd: float, tokens: int, agents_completed: int = None
    ) -> None:
        """Only method still used by ProgressIntegratedCostTracker for LangSmith integration"""
        self.analysis_stats['total_cost_usd'] = cost_usd
        self.analysis_stats['total_tokens'] = tokens
        if agents_completed is not None:
            self.analysis_stats['agents_completed'] = min(
                agents_completed, self.analysis_stats['total_agents']
            )

    async def analysis_complete_detailed(self) -> None:
        total_duration = self._format_duration(self.start_time)

        final_message = f"""✅ *Analysis Complete\\!*

Total Duration: {total_duration}
Agents: {self.analysis_stats['agents_completed']}
Plots Created: {self.analysis_stats['plots_created']}
💰 Total Cost: {self._format_cost(self.analysis_stats['total_cost_usd'])} \\({self.analysis_stats['total_tokens']:,} tokens\\)

📋 *Preparing reports and files\\.\\.\\.*"""

        await self.finish(final_message)


class AICoachDetailedProgressManager(DetailedProgressManager):

    def __init__(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
        super().__init__(context, chat_id)

    async def start_coach_analysis(self) -> None:
        await self.start_detailed_analysis()
