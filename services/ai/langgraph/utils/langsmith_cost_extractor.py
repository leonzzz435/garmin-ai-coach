import logging
import time
from decimal import Decimal
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from langsmith import Client
from requests import HTTPError
import os

logger = logging.getLogger(__name__)


@dataclass
class NodeCostSummary:
    name: str
    run_id: str
    model: Optional[str]
    cost_usd: float
    tokens: int
    input_tokens: int = 0
    output_tokens: int = 0
    web_search_requests: int = 0


@dataclass
class WorkflowCostSummary:
    trace_id: str
    root_run_id: str
    total_cost_usd: float
    total_tokens: int
    total_input_tokens: int
    total_output_tokens: int
    total_web_searches: int
    node_costs: List[NodeCostSummary]
    execution_time_seconds: float = 0.0


class LangSmithCostExtractor:
    
    def __init__(self):
        self.client = None
        if os.getenv("LANGSMITH_API_KEY"):
            try:
                self.client = Client()
                logger.info("LangSmith cost extractor initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize LangSmith client: {e}")
    
    def safe_read_run(self, run_id: str, retries: int = 3, backoff: float = 0.5, load_children: bool = True):
        if not self.client:
            return None
            
        for i in range(retries):
            try:
                return self.client.read_run(run_id, load_child_runs=load_children)
            except HTTPError as e:
                logger.warning(f"HTTP error reading run {run_id}, attempt {i+1}/{retries}: {e}")
                if i == retries - 1:
                    raise
                time.sleep(backoff * (2 ** i))
            except Exception as e:
                logger.error(f"Unexpected error reading run {run_id}: {e}")
                if i == retries - 1:
                    raise
                time.sleep(backoff)
        return None
    
    def extract_workflow_costs_by_trace(self, trace_id: str, execution_time: float = 0.0) -> WorkflowCostSummary:
        if not self.client:
            logger.warning("LangSmith client not available - returning zero costs")
            return self._zero_workflow_summary(trace_id)
        
        try:
            all_runs = list(self.client.list_runs(
                trace=trace_id,
                select=["id", "name", "run_type", "total_cost", "total_tokens"]
            ))
            logger.info(f"Found {len(all_runs)} total runs for trace {trace_id}")
            for run in all_runs[:5]:  # Log first 5 for debugging
                logger.info(f"  Run: {run.name} (type: {run.run_type}) - Cost: ${run.total_cost or 0:.4f}")
            
            llm_runs = list(self.client.list_runs(
                trace=trace_id,
                filter='eq(run_type, "llm")',
                select=["id", "name", "total_cost", "total_tokens", "prompt_tokens", "completion_tokens", "serialized"]
            ))
            logger.info(f"Found {len(llm_runs)} LLM runs for trace {trace_id}")
            
            total_cost = Decimal("0")
            total_tokens = 0
            total_input_tokens = 0
            total_output_tokens = 0
            total_web_searches = 0
            node_costs = []
            
            for run in llm_runs:
                cost = Decimal(str(run.total_cost or 0))
                tokens = run.total_tokens or 0
                input_tokens = run.prompt_tokens or 0
                output_tokens = run.completion_tokens or 0
                model = (run.serialized or {}).get("model", "unknown")
                
                web_searches = 0
                if "search" in run.name.lower() or "web" in run.name.lower():
                    web_searches = 1  # Approximate
                
                total_cost += cost
                total_tokens += tokens
                total_input_tokens += input_tokens
                total_output_tokens += output_tokens
                total_web_searches += web_searches
                
                node_costs.append(NodeCostSummary(
                    name=run.name,
                    run_id=str(run.id),
                    model=model,
                    cost_usd=float(cost),
                    tokens=tokens,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    web_search_requests=web_searches
                ))
            
            logger.info(f"Extracted costs for trace {trace_id}: ${float(total_cost):.4f} ({total_tokens} tokens)")
            
            return WorkflowCostSummary(
                trace_id=trace_id,
                root_run_id="",  # Will be filled by caller if needed
                total_cost_usd=float(total_cost),
                total_tokens=total_tokens,
                total_input_tokens=total_input_tokens,
                total_output_tokens=total_output_tokens,
                total_web_searches=total_web_searches,
                node_costs=node_costs,
                execution_time_seconds=execution_time
            )
            
        except Exception as e:
            logger.error(f"Failed to extract workflow costs for trace {trace_id}: {e}")
            return self._zero_workflow_summary(trace_id)
    
    def extract_run_costs(self, run_id: str, timeout_seconds: int = 30) -> Dict[str, Any]:
        try:
            root_run = self.safe_read_run(run_id, load_children=True)
            if not root_run:
                return self._zero_cost_summary(run_id)
            
            workflow_summary = self.extract_workflow_costs_by_trace(str(root_run.trace_id))
            workflow_summary.root_run_id = run_id
            
            model_breakdown = {}
            for node in workflow_summary.node_costs:
                model_key = node.model or "unknown"
                if model_key not in model_breakdown:
                    model_breakdown[model_key] = {
                        'cost_usd': 0.0,
                        'input_tokens': 0,
                        'output_tokens': 0,
                        'total_tokens': 0,
                        'web_search_requests': 0
                    }
                
                model_breakdown[model_key]['cost_usd'] += node.cost_usd
                model_breakdown[model_key]['input_tokens'] += node.input_tokens
                model_breakdown[model_key]['output_tokens'] += node.output_tokens
                model_breakdown[model_key]['total_tokens'] += node.tokens
                model_breakdown[model_key]['web_search_requests'] += node.web_search_requests
            
            return {
                'total_cost_usd': workflow_summary.total_cost_usd,
                'total_tokens': workflow_summary.total_tokens,
                'model_breakdown': model_breakdown,
                'run_id': run_id,
                'trace_id': workflow_summary.trace_id
            }
            
        except Exception as e:
            logger.error(f"Failed to extract costs from LangSmith run {run_id}: {e}")
            return self._zero_cost_summary(run_id)
    
    def _zero_cost_summary(self, run_id: str = None) -> Dict[str, Any]:
        """Legacy format zero cost summary"""
        return {
            'total_cost_usd': 0.0,
            'total_tokens': 0,
            'model_breakdown': {},
            'run_id': run_id,
            'trace_id': None
        }
    
    def _zero_workflow_summary(self, trace_id: str) -> WorkflowCostSummary:
        return WorkflowCostSummary(
            trace_id=trace_id,
            root_run_id="",
            total_cost_usd=0.0,
            total_tokens=0,
            total_input_tokens=0,
            total_output_tokens=0,
            total_web_searches=0,
            node_costs=[],
            execution_time_seconds=0.0
        )