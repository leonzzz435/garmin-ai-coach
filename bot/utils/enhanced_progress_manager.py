"""Enhanced progress manager with detailed agent execution and plot generation updates."""

import asyncio
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime
from telegram import Message
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from .progress_manager import ProgressManager

logger = logging.getLogger(__name__)


class DetailedProgressManager(ProgressManager):
    """Enhanced progress manager with detailed agent execution and plot information."""
    
    def __init__(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
        super().__init__(context, chat_id)
        self.start_time = None
        self.current_agent = None
        self.agent_start_time = None
        self.plots_generated = []
        self.agent_history = []
        self.analysis_stats = {
            'agents_completed': 0,
            'total_agents': 10,  # analysis: metrics, activity_data, activity_interpreter, physiology, synthesis, formatter + planning: season, data_integration, weekly_planning, plan_formatter
            'plots_created': 0,
            'tool_calls': 0,
            'total_cost_usd': 0.0,
            'total_tokens': 0
        }
        
    def _format_duration(self, start_time: datetime) -> str:
        """Format duration since start time."""
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
        """Escape special characters for MarkdownV2."""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    def _format_cost(self, cost: float) -> str:
        """Format cost with proper markdown escaping."""
        return f"${cost:.4f}".replace('.', '\\.')
    
    def _create_progress_bar(self, current: int, total: int, width: int = 10) -> str:
        """Create a visual progress bar."""
        filled = int((current / total) * width) if total > 0 else 0
        bar = "█" * filled + "░" * (width - filled)
        percentage = int((current / total) * 100) if total > 0 else 0
        return f"{bar} {percentage}%"
    
    async def start_detailed_analysis(self) -> None:
        """Start detailed analysis progress tracking."""
        self.start_time = datetime.now()
        initial_message = f"""🚀 *Starting AI Analysis*

📊 *Progress Overview*
{self._create_progress_bar(0, self.analysis_stats['total_agents'])}
Agents: 0/{self.analysis_stats['total_agents']} \\| Plots: 0 \\| Duration: 0s

🎯 *Current Status*
Initializing analysis system\\.\\.\\."""
        
        await self.start(initial_message)
    
    async def agent_started(self, agent_name: str, description: str) -> None:
        """Update when an agent starts execution."""
        self.current_agent = agent_name
        self.agent_start_time = datetime.now()
        
        # Add to history
        self.agent_history.append({
            'name': agent_name,
            'start_time': self.agent_start_time,
            'status': 'running'
        })
        
        progress_message = f"""🚀 *AI Analysis in Progress*

📊 *Progress Overview*
{self._create_progress_bar(self.analysis_stats['agents_completed'], self.analysis_stats['total_agents'])}
Agents: {self.analysis_stats['agents_completed']}/{self.analysis_stats['total_agents']} \\| Plots: {self.analysis_stats['plots_created']} \\| Cost: {self._format_cost(self.analysis_stats['total_cost_usd'])} \\| Duration: {self._format_duration(self.start_time)}

🤖 *Current Agent: {self._escape_markdown(agent_name)}*
{self._escape_markdown(description)}
Status: ⚙️ Processing\\.\\.\\."""
        
        await self.update(progress_message)
    
    async def agent_completed(self, agent_name: str, plots_created: List[str] = None, tool_calls: int = 0, cost_usd: float = 0.0, tokens: int = 0) -> None:
        """Update when an agent completes execution."""
        self.analysis_stats['agents_completed'] += 1
        self.analysis_stats['tool_calls'] += tool_calls
        self.analysis_stats['total_cost_usd'] += cost_usd
        self.analysis_stats['total_tokens'] += tokens
        
        # Update agent history
        for agent in self.agent_history:
            if agent['name'] == agent_name and agent['status'] == 'running':
                agent['status'] = 'completed'
                agent['end_time'] = datetime.now()
                agent['duration'] = self._format_duration(agent['start_time'])
                agent['plots_created'] = plots_created or []
                agent['tool_calls'] = tool_calls
                agent['cost_usd'] = cost_usd
                agent['tokens'] = tokens
                break
        
        # Update plots
        if plots_created:
            self.plots_generated.extend(plots_created)
            self.analysis_stats['plots_created'] += len(plots_created)
        
        # Create plots summary
        plot_summary = ""
        if plots_created:
            plot_list = '\n'.join([f"  • {self._escape_markdown(plot)}" for plot in plots_created])
            plot_summary = f"\n📈 *Plots Generated:*\n{plot_list}"
        
        # Create cost summary
        cost_summary = ""
        if cost_usd > 0:
            cost_summary = f"\n💰 Cost: {self._format_cost(cost_usd)} \\({tokens:,} tokens\\)"

        progress_message = f"""🚀 *AI Analysis in Progress*

📊 *Progress Overview*
{self._create_progress_bar(self.analysis_stats['agents_completed'], self.analysis_stats['total_agents'])}
Agents: {self.analysis_stats['agents_completed']}/{self.analysis_stats['total_agents']} \\| Plots: {self.analysis_stats['plots_created']} \\| Cost: {self._format_cost(self.analysis_stats['total_cost_usd'])} \\| Duration: {self._format_duration(self.start_time)}

✅ *Agent Completed: {self._escape_markdown(agent_name)}*
Duration: {self._format_duration(self.agent_start_time)}
Tool calls: {tool_calls}{cost_summary}{plot_summary}

🎯 *Next*: {'Finalizing analysis' if self.analysis_stats['agents_completed'] >= self.analysis_stats['total_agents'] else 'Moving to next agent'}\\.\\.\\."""
        
        await self.update(progress_message)
    
    async def plot_generated(self, agent_name: str, plot_id: str, plot_description: str) -> None:
        """Update when a plot is generated during agent execution."""
        self.analysis_stats['plots_created'] += 1
        self.plots_generated.append(f"{plot_id}: {plot_description}")
        
        progress_message = f"""🚀 *AI Analysis in Progress*

📊 *Progress Overview*
{self._create_progress_bar(self.analysis_stats['agents_completed'], self.analysis_stats['total_agents'])}
Agents: {self.analysis_stats['agents_completed']}/{self.analysis_stats['total_agents']} \\| Plots: {self.analysis_stats['plots_created']} \\| Cost: {self._format_cost(self.analysis_stats['total_cost_usd'])} \\| Duration: {self._format_duration(self.start_time)}

🤖 *Current Agent: {self._escape_markdown(agent_name)}*
Status: ⚙️ Processing\\.\\.\\.

📈 *Plot Generated\\!*
ID: {self._escape_markdown(plot_id)}
Description: {self._escape_markdown(plot_description)}"""
        
        await self.update(progress_message, delay=1.0)  # Longer delay to show plot generation
    
    async def tool_call_made(self, agent_name: str, tool_name: str, attempt: int = 1) -> None:
        """Update when an agent makes a tool call."""
        self.analysis_stats['tool_calls'] += 1
        
        attempt_text = f" \\(attempt {attempt}\\)" if attempt > 1 else ""
        
        progress_message = f"""🚀 *AI Analysis in Progress*

📊 *Progress Overview*
{self._create_progress_bar(self.analysis_stats['agents_completed'], self.analysis_stats['total_agents'])}
Agents: {self.analysis_stats['agents_completed']}/{self.analysis_stats['total_agents']} \\| Plots: {self.analysis_stats['plots_created']} \\| Cost: {self._format_cost(self.analysis_stats['total_cost_usd'])} \\| Duration: {self._format_duration(self.start_time)}

🤖 *Current Agent: {self._escape_markdown(agent_name)}*
🔧 Using tool: {self._escape_markdown(tool_name)}{attempt_text}
Status: ⚙️ Processing\\.\\.\\."""
        
        await self.update(progress_message, delay=0.3)
    
    async def analysis_complete_detailed(self) -> None:
        """Complete analysis with detailed summary."""
        total_duration = self._format_duration(self.start_time)
        
        # Create agent summary
        agent_summary = ""
        for agent in self.agent_history:
            status_emoji = "✅" if agent['status'] == 'completed' else "⚙️"
            plots_info = f" \\({len(agent.get('plots_created', []))} plots\\)" if agent.get('plots_created') else ""
            tools_info = f" \\({agent.get('tool_calls', 0)} tools\\)" if agent.get('tool_calls', 0) > 0 else ""
            cost_info = f" \\({self._format_cost(agent.get('cost_usd', 0))[:-1]}\\)" if agent.get('cost_usd', 0) > 0 else ""
            agent_summary += f"\n{status_emoji} {self._escape_markdown(agent['name'])}: {agent.get('duration', 'N/A')}{plots_info}{tools_info}{cost_info}"
        
        # Create plots summary
        plots_summary = ""
        if self.plots_generated:
            plots_summary = f"\n\n📈 *Generated Plots \\({len(self.plots_generated)}\\):*"
            for plot in self.plots_generated[:5]:  # Show first 5 plots
                plots_summary += f"\n• {self._escape_markdown(plot)}"
            if len(self.plots_generated) > 5:
                plots_summary += f"\n• \\.\\.\\. and {len(self.plots_generated) - 5} more plots"
        
        final_message = f"""✅ *Analysis Complete\\!*

📊 *Final Summary*
{self._create_progress_bar(self.analysis_stats['total_agents'], self.analysis_stats['total_agents'])}
Total Duration: {total_duration}
Agents: {self.analysis_stats['agents_completed']}/{self.analysis_stats['total_agents']}
Plots Created: {self.analysis_stats['plots_created']}
Tool Calls: {self.analysis_stats['tool_calls']}
💰 Total Cost: {self._format_cost(self.analysis_stats['total_cost_usd'])} \\({self.analysis_stats['total_tokens']:,} tokens\\)

🤖 *Agent Execution Summary:*{agent_summary}{plots_summary}

📋 *Preparing reports and files\\.\\.\\.*"""
        
        await self.finish(final_message)


class AICoachDetailedProgressManager(DetailedProgressManager):
    """Specialized detailed progress manager for AI Coach analysis."""
    
    def __init__(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int):
        super().__init__(context, chat_id)
        # Keep the correct total of 10 agents for full analysis + planning flow
        # Analysis: metrics, activity_data, activity_interpreter, physiology, synthesis, formatter (6)
        # Planning: season, data_integration, weekly_planning, plan_formatter (4)
        # Total: 10 agents
    
    async def start_coach_analysis(self) -> None:
        """Start AI coach analysis with detailed tracking."""
        await self.start_detailed_analysis()
    
    async def extracting_data_detailed(self) -> None:
        """Enhanced data extraction update."""
        progress_message = f"""🚀 *AI Coach Analysis*

📊 *Progress Overview*
{self._create_progress_bar(0, self.analysis_stats['total_agents'])}
Agents: 0/{self.analysis_stats['total_agents']} \\| Cost: {self._format_cost(self.analysis_stats['total_cost_usd'])} \\| Duration: {self._format_duration(self.start_time)}

📥 *Data Extraction Phase*
• Connecting to Garmin Connect
• Downloading training data
• Processing metrics and activities
Status: ⚙️ Extracting\\.\\.\\."""
        
        await self.update(progress_message)
    
    async def planning_phase(self) -> None:
        """Update for planning phase."""
        progress_message = f"""🚀 *AI Coach Analysis*

📊 *Progress Overview*
{self._create_progress_bar(self.analysis_stats['agents_completed'], self.analysis_stats['total_agents'])}
Agents: {self.analysis_stats['agents_completed']}/{self.analysis_stats['total_agents']} \\| Plots: {self.analysis_stats['plots_created']} \\| Cost: {self._format_cost(self.analysis_stats['total_cost_usd'])} \\| Duration: {self._format_duration(self.start_time)}

📅 *Weekly Planning Phase*
• Generating personalized training plan
• Considering competition schedule
• Optimizing workout distribution
Status: ⚙️ Planning\\.\\.\\."""

        await self.update(progress_message)
    
    async def preparing_reports(self) -> None:
        """Update to report preparation phase with detailed information."""
        progress_message = f"""🚀 *AI Coach Analysis*

📊 *Progress Overview*
{self._create_progress_bar(self.analysis_stats['agents_completed'], self.analysis_stats['total_agents'])}
Agents: {self.analysis_stats['agents_completed']}/{self.analysis_stats['total_agents']} \\| Plots: {self.analysis_stats['plots_created']} \\| Cost: {self._format_cost(self.analysis_stats['total_cost_usd'])} \\| Duration: {self._format_duration(self.start_time)}

📋 *Report Preparation Phase*
• Formatting HTML reports
• Organizing visualizations
• Preparing file delivery
Status: ⚙️ Preparing\\.\\.\\."""
        
        await self.update(progress_message)