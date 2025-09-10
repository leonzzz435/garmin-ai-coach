import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .langsmith_cost_extractor import LangSmithCostExtractor, WorkflowCostSummary

logger = logging.getLogger(__name__)


@dataclass
class WorkflowExecution:
    trace_id: str
    root_run_id: str
    start_time: datetime
    end_time: datetime | None = None
    execution_time_seconds: float = 0.0
    cost_summary: WorkflowCostSummary | None = None


class WorkflowCostTracker:

    def __init__(self, project_name: str = "tele_garmin_analysis"):
        self.project_name = project_name
        self.cost_extractor = LangSmithCostExtractor()

    async def run_workflow_with_cost_tracking(
        self,
        workflow_app,
        initial_state: dict[str, Any],
        thread_id: str,
        user_id: str = None,
        progress_callback: Callable[[str, WorkflowCostSummary], Awaitable[None]] | None = None,
    ) -> tuple[dict[str, Any], WorkflowExecution]:

        root_run_id = uuid.uuid4()

        execution = WorkflowExecution(
            trace_id=str(root_run_id),  # For root runs, trace_id equals run_id
            root_run_id=str(root_run_id),
            start_time=datetime.now(),
        )

        final_state = dict(initial_state) if initial_state else {}

        try:
            logger.info(
                f"Starting workflow execution with deterministic root_run_id: {root_run_id}"
            )

            config = {
                "run_id": root_run_id,
                "run_name": "tele_garmin_workflow",
                "tags": [
                    f"user:{user_id}" if user_id else "user:unknown",
                    "app:tele_garmin",
                    f"thread:{thread_id}" if thread_id else "thread:none",
                ],
                "metadata": {
                    "user_id": user_id,
                    "thread_id": thread_id,
                    "project": self.project_name,
                },
            }

            if thread_id:
                config["configurable"] = {"thread_id": thread_id}

            prev_lengths = {'analysis_html': None, 'planning_html': None}

            async for chunk in workflow_app.astream(
                initial_state, config=config, stream_mode="values"
            ):
                logger.debug(f"Workflow step: {list(chunk.keys()) if chunk else 'None'}")
                if chunk:
                    final_state = chunk  # Take the latest complete state snapshot

                    for _key in ('analysis_html', 'planning_html'):
                        if _key in chunk and chunk[_key]:
                            curr_len = len(str(chunk[_key]))
                            if prev_lengths[_key] != curr_len:
                                logger.info(f"{_key} updated: {curr_len} chars")
                                prev_lengths[_key] = curr_len
                            else:
                                logger.debug(f"{_key} unchanged: {curr_len} chars")

            logger.info(
                f"Workflow execution complete with deterministic trace_id: {execution.trace_id}"
            )

            execution.end_time = datetime.now()
            execution.execution_time_seconds = (
                execution.end_time - execution.start_time
            ).total_seconds()

            try:
                logger.info(f"Extracting costs for deterministic trace: {execution.trace_id}")
                cost_summary = self.cost_extractor.extract_workflow_costs_by_trace(
                    execution.trace_id, execution.execution_time_seconds
                )
                cost_summary.root_run_id = execution.root_run_id
                execution.cost_summary = cost_summary

                if progress_callback and cost_summary.total_cost_usd > 0:
                    await progress_callback("workflow_complete", cost_summary)

                logger.info(
                    f"Workflow execution complete: ${cost_summary.total_cost_usd:.4f} ({cost_summary.total_tokens} tokens)"
                )

            except Exception as e:
                logger.error(f"Error extracting costs for trace {execution.trace_id}: {e}")
                execution.cost_summary = self.cost_extractor._zero_workflow_summary(
                    execution.trace_id
                )

        except Exception as e:
            logger.error(f"Error in workflow execution: {e}")
            execution.end_time = datetime.now()
            execution.execution_time_seconds = (
                execution.end_time - execution.start_time
            ).total_seconds()
            execution.cost_summary = self.cost_extractor._zero_workflow_summary(execution.trace_id)
            raise

        return final_state, execution

    def get_legacy_cost_summary(self, execution: WorkflowExecution) -> dict[str, Any]:
        if not execution.cost_summary:
            return {'total_cost_usd': 0.0, 'total_tokens': 0, 'agents': [], 'model_breakdown': {}}

        cost_summary = execution.cost_summary

        agents = []
        model_breakdown = {}

        for node in cost_summary.node_costs:
            agents.append(
                {
                    'name': node.name,
                    'cost_usd': node.cost_usd,
                    'tokens': node.tokens,
                    'execution_time_seconds': 0.0,  # Per-node time not available yet
                    'models': [
                        {
                            'name': node.model or 'unknown',
                            'cost_usd': node.cost_usd,
                            'input_tokens': node.input_tokens,
                            'output_tokens': node.output_tokens,
                            'total_tokens': node.tokens,
                            'web_search_requests': node.web_search_requests,
                        }
                    ],
                }
            )

            model_key = node.model or 'unknown'
            if model_key not in model_breakdown:
                model_breakdown[model_key] = {
                    'cost_usd': 0.0,
                    'tokens': 0,
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'web_search_requests': 0,
                }

            model_breakdown[model_key]['cost_usd'] += node.cost_usd
            model_breakdown[model_key]['tokens'] += node.tokens
            model_breakdown[model_key]['input_tokens'] += node.input_tokens
            model_breakdown[model_key]['output_tokens'] += node.output_tokens
            model_breakdown[model_key]['web_search_requests'] += node.web_search_requests

        return {
            'total_cost_usd': cost_summary.total_cost_usd,
            'total_tokens': cost_summary.total_tokens,
            'total_execution_time_seconds': cost_summary.execution_time_seconds,
            'agent_count': len(cost_summary.node_costs),
            'agents': agents,
            'model_breakdown': model_breakdown,
        }


class ProgressIntegratedCostTracker(WorkflowCostTracker):

    def __init__(self, project_name: str = "tele_garmin_analysis", progress_manager=None):
        super().__init__(project_name)
        self.progress_manager = progress_manager

    async def run_workflow_with_progress(
        self, workflow_app, initial_state: dict[str, Any], thread_id: str, user_id: str = None
    ) -> tuple[dict[str, Any], WorkflowExecution]:

        async def progress_callback(event: str, cost_summary: WorkflowCostSummary):
            if self.progress_manager and hasattr(self.progress_manager, 'analysis_stats'):
                self.progress_manager.analysis_stats['total_cost_usd'] = cost_summary.total_cost_usd
                self.progress_manager.analysis_stats['total_tokens'] = cost_summary.total_tokens

                if cost_summary.node_costs:
                    self.progress_manager.analysis_stats['agents_completed'] = len(
                        cost_summary.node_costs
                    )

                logger.info(
                    f"Updated progress manager with cost: ${cost_summary.total_cost_usd:.4f}"
                )

        return await self.run_workflow_with_cost_tracking(
            workflow_app, initial_state, thread_id, user_id, progress_callback
        )
