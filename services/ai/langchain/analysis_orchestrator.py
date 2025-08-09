"""LangChain orchestrator for comprehensive training analysis."""

import logging
from dataclasses import asdict
from datetime import datetime
from typing import Any

from langchain_core.callbacks import get_usage_metadata_callback

from core.security.competitions import SecureCompetitionManager
from services.ai.tools.plotting import PlotReferenceResolver, PlotStorage
from services.ai.utils.cost_tracker import CostTracker
from services.ai.utils.intermediate_storage import IntermediateResultStorage
from services.garmin import GarminData

from .analysis_chains import AnalysisChains

logger = logging.getLogger(__name__)


class LangChainAnalysisOrchestrator:
    """Orchestrates analysis using LangChain chains with plotting capabilities."""

    def __init__(
        self,
        garmin_data: GarminData,
        user_id: str,
        athlete_name: str,
        analysis_context: str = "",
        max_plots_per_agent: int = 2,
        tool_limiter=None,
        progress_manager: Any | None = None,
    ):
        """Initialize orchestrator for a single analysis execution.

        Args:
            garmin_data: Garmin data for analysis
            user_id: User identifier
            athlete_name: Name of the athlete
            analysis_context: Context for data analysis interpretation (health, stress, etc.)
            max_plots_per_agent: Maximum plots each agent can create (default: 2)
            tool_limiter: Custom tool limiter instance. If None, creates default PlottingLimiter
            progress_manager: Optional detailed progress manager for live updates
        """
        self.user_id = user_id
        self.athlete_name = athlete_name
        self.analysis_context = analysis_context
        self.data = asdict(garmin_data)
        self.progress_manager = progress_manager

        # Initialize cost tracking
        self.cost_tracker = CostTracker()

        # Create execution-scoped plot storage
        execution_id = f"{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.plot_storage = PlotStorage(execution_id)

        # Create execution-scoped chains with plotting and tool limiting
        self.chains = AnalysisChains(
            user_id=user_id,
            plot_storage=self.plot_storage,
            tool_limiter=tool_limiter,
            max_plots_per_agent=max_plots_per_agent,
            progress_manager=progress_manager,
        )

        # Get competition data and current date
        competition_manager = SecureCompetitionManager(user_id)
        self.competitions = [
            {
                'name': comp.name,
                'date': comp.date.isoformat(),
                'race_type': comp.race_type,
                'priority': comp.priority.value,
                'target_time': comp.target_time,
                'location': comp.location,
                'notes': comp.notes,
            }
            for comp in competition_manager.get_upcoming_competitions()
        ]

        current_date = datetime.now()
        self.current_date = {
            'current_date': current_date.isoformat(),
            'date_formatted': current_date.strftime('%Y-%m-%d'),
        }

        # Load style guide
        try:
            with open('styleGuide.md') as f:
                self.style_guide = f.read()
        except Exception as e:
            logger.error(f"Failed to load style guide: {e}")
            self.style_guide = ""

        logger.info(f"Initialized LangChain orchestrator for user {user_id}")

    def _extract_agent_output(self, agent_response):
        """Extract string output from AgentExecutor response.

        Args:
            agent_response: Response from AgentExecutor

        Returns:
            String output or fallback representation
        """
        if isinstance(agent_response, dict):
            # AgentExecutor returns dict with 'output' key
            output = agent_response.get('output', agent_response)
        else:
            output = agent_response

        # Handle case where output is a list (e.g., from intermediate steps)
        if isinstance(output, list):
            if len(output) > 0 and isinstance(output[0], dict) and 'text' in output[0]:
                # Extract text from ChatML format
                return output[0]['text']
            else:
                # Convert list to string representation
                return '\n'.join(str(item) for item in output)

        # Ensure we always return a string
        return str(output) if output is not None else ""

    async def run_analysis(self, store_intermediate: bool = True) -> tuple[str, dict[str, str]]:
        """Execute the complete analysis flow and return HTML result with intermediate results.

        Args:
            store_intermediate: Whether to store intermediate results to files (default: True)

        Returns:
            Tuple of (HTML formatted analysis report, dict of intermediate results)
        """
        try:
            # Step 1: Metrics Analysis
            logger.info("Starting metrics analysis")
            if self.progress_manager:
                await self.progress_manager.agent_started(
                    "Metrics Agent",
                    "Analyzing training load, VO2 Max trends, and performance metrics",
                )

            metrics_chain = self.chains.create_metrics_chain()

            # Track cost and execution time for this agent
            agent_start_time = datetime.now()
            with get_usage_metadata_callback() as cb:
                metrics_response = await metrics_chain.ainvoke(
                    {
                        'data': {
                            'training_load_history': self.data.get('training_load_history', []),
                            'vo2_max_history': self.data.get('vo2_max_history', []),
                            'training_status': self.data.get('training_status', {}),
                        },
                        'competitions': self.competitions,
                        'current_date': self.current_date,
                        'analysis_context': self.analysis_context,
                    }
                )

            # Calculate execution time and costs
            execution_time = (datetime.now() - agent_start_time).total_seconds()
            agent_cost_summary = self.cost_tracker.add_agent_cost(
                "Metrics Agent", cb.usage_metadata, execution_time
            )

            # Log web search usage if any
            total_searches = sum(
                usage.web_search_requests for usage in agent_cost_summary.model_usage
            )
            if total_searches > 0:
                logger.info(f"🔍 Metrics Agent performed {total_searches} web searches")

            # Extract output from AgentExecutor response
            metrics_result = self._extract_agent_output(metrics_response)

            # Get tool usage
            tool_usage = (
                self.chains.get_tool_usage_stats().get('metrics_agent', {}).get('total_calls', 0)
            )

            if self.progress_manager:
                await self.progress_manager.agent_completed(
                    "Metrics Agent",
                    plots_created=[],  # Plots already reported during creation
                    tool_calls=tool_usage,
                    cost_usd=agent_cost_summary.total_cost_usd,
                    tokens=agent_cost_summary.total_tokens,
                )
            logger.info("Metrics analysis completed")

            # Step 2: Activity Data Extraction
            logger.info("Starting activity data extraction")
            if self.progress_manager:
                await self.progress_manager.agent_started(
                    "Activity Data Agent",
                    "Processing recent training activities and workout patterns",
                )

            activity_data_chain = self.chains.create_activity_data_chain()

            # Track cost and execution time for this agent
            agent_start_time = datetime.now()
            with get_usage_metadata_callback() as cb:
                activity_summary = await activity_data_chain.ainvoke(
                    {
                        'data': {
                            'recent_activities': self.data.get('recent_activities', []),
                            'training_status': self.data.get('training_status', {}),
                        }
                    }
                )

            # Calculate execution time and costs
            execution_time = (datetime.now() - agent_start_time).total_seconds()
            agent_cost_summary = self.cost_tracker.add_agent_cost(
                "Activity Data Agent", cb.usage_metadata, execution_time
            )

            # Log web search usage if any
            total_searches = sum(
                usage.web_search_requests for usage in agent_cost_summary.model_usage
            )
            if total_searches > 0:
                logger.info(f"🔍 Activity Data Agent performed {total_searches} web searches")

            if self.progress_manager:
                await self.progress_manager.agent_completed(
                    "Activity Data Agent",
                    plots_created=[],
                    tool_calls=0,
                    cost_usd=agent_cost_summary.total_cost_usd,
                    tokens=agent_cost_summary.total_tokens,
                )
            logger.info("Activity data extraction completed")

            # Step 3: Activity Interpretation
            logger.info("Starting activity interpretation")
            if self.progress_manager:
                await self.progress_manager.agent_started(
                    "Activity Interpreter Agent",
                    "Interpreting training patterns and workout effectiveness",
                )

            activity_interpreter_chain = self.chains.create_activity_interpreter_chain()

            # Track cost and execution time for this agent
            agent_start_time = datetime.now()
            with get_usage_metadata_callback() as cb:
                activity_response = await activity_interpreter_chain.ainvoke(
                    {
                        'activity_summary': activity_summary,
                        'competitions': self.competitions,
                        'current_date': self.current_date,
                        'analysis_context': self.analysis_context,
                    }
                )

            # Calculate execution time and costs
            execution_time = (datetime.now() - agent_start_time).total_seconds()
            agent_cost_summary = self.cost_tracker.add_agent_cost(
                "Activity Interpreter Agent", cb.usage_metadata, execution_time
            )

            # Log web search usage if any
            total_searches = sum(
                usage.web_search_requests for usage in agent_cost_summary.model_usage
            )
            if total_searches > 0:
                logger.info(
                    f"🔍 Activity Interpreter Agent performed {total_searches} web searches"
                )

            # Extract output from AgentExecutor response
            activity_result = self._extract_agent_output(activity_response)

            # Get tool usage
            tool_usage = (
                self.chains.get_tool_usage_stats()
                .get('activity_interpreter_agent', {})
                .get('total_calls', 0)
            )

            if self.progress_manager:
                await self.progress_manager.agent_completed(
                    "Activity Interpreter Agent",
                    plots_created=[],  # Plots already reported during creation
                    tool_calls=tool_usage,
                    cost_usd=agent_cost_summary.total_cost_usd,
                    tokens=agent_cost_summary.total_tokens,
                )
            logger.info("Activity interpretation completed")

            # Step 4: Physiology Analysis
            logger.info("Starting physiology analysis")
            if self.progress_manager:
                await self.progress_manager.agent_started(
                    "Physiology Agent",
                    "Analyzing recovery, stress markers, and physiological adaptations",
                )

            physiology_chain = self.chains.create_physiology_chain()

            # Track cost and execution time for this agent
            agent_start_time = datetime.now()
            with get_usage_metadata_callback() as cb:
                physiology_response = await physiology_chain.ainvoke(
                    {
                        'data': {
                            'recovery_indicators': self.data.get('recovery_indicators', []),
                            'daily_stats': self.data.get('daily_stats', {}),
                            'physiological_markers': self.data.get('physiological_markers', {}),
                        },
                        'competitions': self.competitions,
                        'current_date': self.current_date,
                        'analysis_context': self.analysis_context,
                    }
                )

            # Calculate execution time and costs
            execution_time = (datetime.now() - agent_start_time).total_seconds()
            agent_cost_summary = self.cost_tracker.add_agent_cost(
                "Physiology Agent", cb.usage_metadata, execution_time
            )

            # Log web search usage if any
            total_searches = sum(
                usage.web_search_requests for usage in agent_cost_summary.model_usage
            )
            if total_searches > 0:
                logger.info(f"🔍 Physiology Agent performed {total_searches} web searches")

            # Extract output from AgentExecutor response
            physiology_result = self._extract_agent_output(physiology_response)

            # Get tool usage
            tool_usage = (
                self.chains.get_tool_usage_stats().get('physiology_agent', {}).get('total_calls', 0)
            )

            if self.progress_manager:
                await self.progress_manager.agent_completed(
                    "Physiology Agent",
                    plots_created=[],  # Plots already reported during creation
                    tool_calls=tool_usage,
                    cost_usd=agent_cost_summary.total_cost_usd,
                    tokens=agent_cost_summary.total_tokens,
                )
            logger.info("Physiology analysis completed")

            # Step 5: Synthesis
            logger.info("Starting synthesis")
            if self.progress_manager:
                await self.progress_manager.agent_started(
                    "Synthesis Agent",
                    "Synthesizing insights and creating comprehensive analysis report",
                )

            synthesis_chain = self.chains.create_synthesis_chain()

            # Track cost and execution time for this agent
            agent_start_time = datetime.now()
            with get_usage_metadata_callback() as cb:
                synthesis_response = await synthesis_chain.ainvoke(
                    {
                        'athlete_name': self.athlete_name,
                        'metrics_result': metrics_result,
                        'activity_result': activity_result,
                        'physiology_result': physiology_result,
                        'competitions': self.competitions,
                        'current_date': self.current_date,
                        'style_guide': self.style_guide,
                        'available_plots': self.plot_storage.list_available_plots(),
                    }
                )

            # Calculate execution time and costs
            execution_time = (datetime.now() - agent_start_time).total_seconds()
            agent_cost_summary = self.cost_tracker.add_agent_cost(
                "Synthesis Agent", cb.usage_metadata, execution_time
            )

            # Log web search usage if any
            total_searches = sum(
                usage.web_search_requests for usage in agent_cost_summary.model_usage
            )
            if total_searches > 0:
                logger.info(f"🔍 Synthesis Agent performed {total_searches} web searches")

            # Extract output from AgentExecutor response
            synthesis_result = self._extract_agent_output(synthesis_response)

            # Get tool usage
            tool_usage = (
                self.chains.get_tool_usage_stats().get('synthesis_agent', {}).get('total_calls', 0)
            )

            if self.progress_manager:
                await self.progress_manager.agent_completed(
                    "Synthesis Agent",
                    plots_created=[],  # Plots already reported during creation
                    tool_calls=tool_usage,
                    cost_usd=agent_cost_summary.total_cost_usd,
                    tokens=agent_cost_summary.total_tokens,
                )
            logger.info("Synthesis completed")

            # Step 6: HTML Formatting with Plot Resolution
            logger.info("Starting HTML formatting")
            if self.progress_manager:
                await self.progress_manager.agent_started(
                    "HTML Formatter Agent",
                    "Formatting analysis into HTML report and embedding visualizations",
                )

            formatter_chain = self.chains.create_formatter_chain()

            # Track cost and execution time for this agent
            agent_start_time = datetime.now()
            with get_usage_metadata_callback() as cb:
                html_result = await formatter_chain.ainvoke({'synthesis_result': synthesis_result})

            # Calculate execution time and costs
            execution_time = (datetime.now() - agent_start_time).total_seconds()
            agent_cost_summary = self.cost_tracker.add_agent_cost(
                "HTML Formatter Agent", cb.usage_metadata, execution_time
            )

            # Resolve plot references in the HTML
            plot_resolver = PlotReferenceResolver(self.plot_storage)
            html_result = plot_resolver.resolve_plot_references(html_result)

            if self.progress_manager:
                await self.progress_manager.agent_completed(
                    "HTML Formatter Agent",
                    plots_created=[],
                    tool_calls=0,
                    cost_usd=agent_cost_summary.total_cost_usd,
                    tokens=agent_cost_summary.total_tokens,
                )
            logger.info("HTML formatting and plot resolution completed")

            # Get final cost summary
            cost_summary = self.cost_tracker.get_session_summary()

            # Package intermediate results with plots, tool usage stats, and cost tracking
            intermediate_results = {
                'metrics_result': metrics_result,
                'activity_result': activity_result,
                'physiology_result': physiology_result,
                'synthesis_result': synthesis_result,
                'plots': self.plot_storage.get_all_plots(),
                'plot_stats': self.plot_storage.get_storage_stats(),
                'tool_usage_stats': self.chains.get_tool_usage_stats(),
                'cost_summary': cost_summary,
            }

            # Store intermediate results if requested
            if store_intermediate:
                try:
                    storage = IntermediateResultStorage(self.athlete_name)
                    stored_files = storage.store_analysis_results(intermediate_results)
                    logger.info(
                        f"Stored {len(stored_files)} intermediate result files for {self.athlete_name}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to store intermediate results for {self.athlete_name}: {e}"
                    )

            plot_stats = self.plot_storage.get_storage_stats()
            logger.info(
                f"Analysis orchestration completed successfully for user {self.user_id}. "
                f"Generated {plot_stats['total_plots']} plots from {plot_stats['unique_agents']} agents. "
                f"Total cost: ${cost_summary['total_cost_usd']:.4f} ({cost_summary['total_tokens']:,} tokens)"
            )

            # Note: Plot storage cleanup is handled automatically when object goes out of scope
            return html_result, intermediate_results

        except Exception as e:
            logger.error(f"Analysis orchestration failed for user {self.user_id}: {str(e)}")
            # Clean up plots on error
            self.plot_storage.clear_plots()
            raise


class LangChainAnalysisFlow:
    """LangChain-based analysis flow for comprehensive training insights."""

    @staticmethod
    async def run_analysis(
        garmin_data: GarminData,
        user_id: str,
        athlete_name: str,
        analysis_context: str = "",
        max_plots_per_agent: int = 2,
        tool_limiter=None,
        progress_manager: Any | None = None,
    ) -> tuple[str, dict[str, str]]:
        """Run complete analysis and return HTML result with intermediate results.

        Args:
            garmin_data: Garmin data for analysis
            user_id: User identifier
            athlete_name: Name of the athlete
            analysis_context: Context for data analysis interpretation (health, stress, etc.)
            max_plots_per_agent: Maximum plots each agent can create (default: 2)
            tool_limiter: Custom tool limiter instance. If None, creates default PlottingLimiter
            progress_manager: Optional detailed progress manager for live updates

        Returns:
            Tuple of (HTML formatted analysis report, dict of intermediate results)
        """
        orchestrator = LangChainAnalysisOrchestrator(
            garmin_data=garmin_data,
            user_id=user_id,
            athlete_name=athlete_name,
            analysis_context=analysis_context,
            max_plots_per_agent=max_plots_per_agent,
            tool_limiter=tool_limiter,
            progress_manager=progress_manager,
        )
        return await orchestrator.run_analysis()
