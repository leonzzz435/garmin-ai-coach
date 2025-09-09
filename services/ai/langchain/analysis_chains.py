import logging
from datetime import datetime
from typing import Any

from langchain_core.output_parsers import StrOutputParser

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.callbacks.manager import CallbackManager

from ..ai_settings import AgentRole
from ..model_config import ModelSelector
from ..tools.plotting import PlotListTool, PlotStorage, PythonPlottingTool
from .prompts.prompt_templates import PromptTemplateManager
from .tool_usage_limiter import PlottingLimiter, create_plotting_limiter

logger = logging.getLogger(__name__)


class AnalysisChains:

    def __init__(
        self,
        user_id: str,
        plot_storage: PlotStorage = None,
        tool_limiter: PlottingLimiter | None = None,
        max_plots_per_agent: int = 2,
        progress_manager: Any | None = None,
    ):
        self.user_id = user_id
        self.execution_id = f"{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.plot_storage = plot_storage or PlotStorage(self.execution_id)
        self.progress_manager = progress_manager
        self.tool_limiter = tool_limiter or create_plotting_limiter(
            max_plots=max_plots_per_agent, strict_mode=True
        )
        logger.info(
            f"Initialized analysis chains with plotting and tool limiting for execution {self.execution_id}"
        )
        logger.info(f"Tool limits: {self.tool_limiter.tool_limits}")

    def _create_agent_executor(self, prompt, llm, tools, agent_name: str):
        try:
            agent = create_tool_calling_agent(llm, tools, prompt)

            callback_manager = CallbackManager([self.tool_limiter])

            agent_executor = AgentExecutor(
                agent=agent,
                tools=tools,
                max_iterations=20,  # Allow for tool use + analysis completion
                max_execution_time=600,  # 60 second timeout
                handle_parsing_errors=True,  # Built-in error handling
                handle_tool_error=True,  # Enable graceful tool failure handling
                verbose=True,  # Enhanced logging
                return_intermediate_steps=True,  # For debugging
                early_stopping_method="force",
                callback_manager=callback_manager,
            )

            logger.info(
                f"Created AgentExecutor for {agent_name} agent with {len(tools)} tools and usage limits"
            )
            return agent_executor

        except Exception as e:
            logger.error(f"Failed to create AgentExecutor for {agent_name}: {e}")
            return prompt | llm | StrOutputParser()

    def create_metrics_chain(self):
        metrics_prompt = PromptTemplateManager.create_metrics_template()
        llm = ModelSelector.get_llm(AgentRole.METRICS)

        plotting_tool = PythonPlottingTool(
            plot_storage=self.plot_storage, progress_manager=self.progress_manager
        )
        plotting_tool.agent_name = "metrics"
        tools = [plotting_tool]

        return self._create_agent_executor(metrics_prompt, llm, tools, "metrics").with_config(
            {"run_name": f"metrics_analysis_{self.execution_id}"}
        )

    def create_activity_data_chain(self):
        activity_data_prompt = PromptTemplateManager.create_activity_data_template()
        llm = ModelSelector.get_llm(AgentRole.ACTIVITY_DATA)

        return (activity_data_prompt | llm | StrOutputParser()).with_config(
            {"run_name": f"activity_data_{self.execution_id}"}
        )

    def create_activity_interpreter_chain(self):
        activity_interpreter_prompt = PromptTemplateManager.create_activity_interpreter_template()
        llm = ModelSelector.get_llm(AgentRole.ACTIVITY_INTERPRETER)

        plotting_tool = PythonPlottingTool(
            plot_storage=self.plot_storage, progress_manager=self.progress_manager
        )
        plotting_tool.agent_name = "activity"
        tools = [plotting_tool]

        return self._create_agent_executor(
            activity_interpreter_prompt, llm, tools, "activity"
        ).with_config({"run_name": f"activity_interpreter_{self.execution_id}"})

    def create_physiology_chain(self):
        physiology_prompt = PromptTemplateManager.create_physiology_template()
        llm = ModelSelector.get_llm(AgentRole.PHYSIO)

        # Add plotting tools for the physiology agent
        plotting_tool = PythonPlottingTool(
            plot_storage=self.plot_storage, progress_manager=self.progress_manager
        )
        plotting_tool.agent_name = "physiology"
        tools = [plotting_tool]

        return self._create_agent_executor(physiology_prompt, llm, tools, "physiology").with_config(
            {"run_name": f"physiology_{self.execution_id}"}
        )

    def create_synthesis_chain(self):
        synthesis_prompt = PromptTemplateManager.create_synthesis_template()
        llm = ModelSelector.get_llm(AgentRole.SYNTHESIS)

        # Add plot listing tool for synthesis agent to reference available plots
        plot_list_tool = PlotListTool(plot_storage=self.plot_storage)
        tools = [plot_list_tool]

        return self._create_agent_executor(synthesis_prompt, llm, tools, "synthesis").with_config(
            {"run_name": f"synthesis_{self.execution_id}"}
        )

    def create_formatter_chain(self):
        formatter_prompt = PromptTemplateManager.create_formatter_template()
        llm = ModelSelector.get_llm(AgentRole.FORMATTER)

        return (formatter_prompt | llm | StrOutputParser()).with_config(
            {"run_name": f"formatter_{self.execution_id}"}
        )

    def get_plot_storage(self) -> PlotStorage:
        return self.plot_storage

    def get_tool_usage_stats(self) -> dict[str, dict[str, int]]:
        return self.tool_limiter.get_usage_stats()

    def reset_tool_usage(self) -> None:
        self.tool_limiter.reset_counts()
        logger.info(f"Reset tool usage counters for execution {self.execution_id}")
