"""Real-time cost tracking for Claude and other LLM models using LangChain's usage metadata."""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class ModelUsage:
    """Container for model usage statistics."""
    model_name: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class AgentCostSummary:
    """Cost summary for a specific agent."""
    agent_name: str
    model_usage: List[ModelUsage] = field(default_factory=list)
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    execution_time_seconds: float = 0.0

class CostTracker:
    """Real-time cost tracking for LLM usage with LangChain integration."""
    
    def __init__(self):
        """Initialize cost tracker with pricing data."""
        self.pricing_data = self._load_pricing_data()
        self.session_costs: List[AgentCostSummary] = []
        self.total_session_cost = 0.0
        
    def _load_pricing_data(self) -> Dict[str, Dict[str, Any]]:
        """Load model pricing data from config file."""
        try:
            config_path = Path(__file__).parent.parent.parent.parent / "config" / "model_pricing.json"
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load pricing data: {e}")
            return {}
    
    def _normalize_model_name(self, model_name: str) -> str:
        """Normalize model name to match pricing keys."""
        # Handle common model name variations
        name_mappings = {
            "claude-3-7-sonnet-20250224": "claude-3-7-sonnet",
            "claude-4-opus-20250522": "claude-4-opus", 
            "claude-4-sonnet-20250514": "claude-4-sonnet",
            "anthropic:claude-3-7-sonnet": "claude-3-7-sonnet",
            "anthropic:claude-4-opus": "claude-4-opus",
            "anthropic:claude-4-sonnet": "claude-4-sonnet"
        }
        return name_mappings.get(model_name, model_name)
    
    def calculate_cost_from_usage_metadata(self, usage_metadata: Dict[str, Any]) -> List[ModelUsage]:
        """
        Calculate costs from LangChain's usage metadata callback.
        
        Args:
            usage_metadata: Dictionary from get_usage_metadata_callback()
            
        Returns:
            List of ModelUsage objects with cost calculations
        """
        model_usages = []
        
        if not usage_metadata:
            logger.warning("No usage metadata provided")
            return model_usages
            
        for model_key, usage in usage_metadata.items():
            try:
                # Normalize model name for pricing lookup
                normalized_name = self._normalize_model_name(model_key)
                
                # Get pricing data
                if normalized_name not in self.pricing_data:
                    logger.warning(f"No pricing data for model: {normalized_name}")
                    continue
                    
                rates = self.pricing_data[normalized_name]
                input_cost_per_million = rates.get("input_cost", 0)
                output_cost_per_million = rates.get("output_cost", 0)
                
                # Extract token counts from usage
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                total_tokens = usage.get("total_tokens", input_tokens + output_tokens)
                
                # Calculate cost in USD
                input_cost = (input_tokens * input_cost_per_million) / 1_000_000
                output_cost = (output_tokens * output_cost_per_million) / 1_000_000
                total_cost = input_cost + output_cost
                
                model_usage = ModelUsage(
                    model_name=normalized_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cost_usd=total_cost
                )
                
                model_usages.append(model_usage)
                
                logger.debug(f"Cost calculated for {normalized_name}: "
                           f"${total_cost:.4f} ({input_tokens} input + {output_tokens} output tokens)")
                
            except Exception as e:
                logger.error(f"Error calculating cost for model {model_key}: {e}")
                continue
                
        return model_usages
    
    def add_agent_cost(self, agent_name: str, usage_metadata: Dict[str, Any], 
                      execution_time: float = 0.0) -> AgentCostSummary:
        """
        Add cost information for a specific agent execution.
        
        Args:
            agent_name: Name of the agent
            usage_metadata: Usage metadata from LangChain callback
            execution_time: Agent execution time in seconds
            
        Returns:
            AgentCostSummary with calculated costs
        """
        model_usages = self.calculate_cost_from_usage_metadata(usage_metadata)
        total_cost = sum(usage.cost_usd for usage in model_usages)
        total_tokens = sum(usage.total_tokens for usage in model_usages)
        
        agent_summary = AgentCostSummary(
            agent_name=agent_name,
            model_usage=model_usages,
            total_cost_usd=total_cost,
            total_tokens=total_tokens,
            execution_time_seconds=execution_time
        )
        
        self.session_costs.append(agent_summary)
        self.total_session_cost += total_cost
        
        logger.info(f"Agent {agent_name} cost: ${total_cost:.4f} "
                   f"({total_tokens} tokens, {execution_time:.1f}s)")
        
        return agent_summary
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get comprehensive cost summary for the current session."""
        if not self.session_costs:
            return {
                "total_cost_usd": 0.0,
                "total_tokens": 0,
                "agent_count": 0,
                "agents": []
            }
        
        total_tokens = sum(agent.total_tokens for agent in self.session_costs)
        total_execution_time = sum(agent.execution_time_seconds for agent in self.session_costs)
        
        # Model breakdown
        model_costs = {}
        for agent in self.session_costs:
            for usage in agent.model_usage:
                if usage.model_name not in model_costs:
                    model_costs[usage.model_name] = {
                        "cost_usd": 0.0,
                        "tokens": 0,
                        "input_tokens": 0,
                        "output_tokens": 0
                    }
                model_costs[usage.model_name]["cost_usd"] += usage.cost_usd
                model_costs[usage.model_name]["tokens"] += usage.total_tokens
                model_costs[usage.model_name]["input_tokens"] += usage.input_tokens
                model_costs[usage.model_name]["output_tokens"] += usage.output_tokens
        
        return {
            "total_cost_usd": self.total_session_cost,
            "total_tokens": total_tokens,
            "total_execution_time_seconds": total_execution_time,
            "agent_count": len(self.session_costs),
            "agents": [
                {
                    "name": agent.agent_name,
                    "cost_usd": agent.total_cost_usd,
                    "tokens": agent.total_tokens,
                    "execution_time_seconds": agent.execution_time_seconds,
                    "models": [
                        {
                            "name": usage.model_name,
                            "cost_usd": usage.cost_usd,
                            "input_tokens": usage.input_tokens,
                            "output_tokens": usage.output_tokens,
                            "total_tokens": usage.total_tokens
                        }
                        for usage in agent.model_usage
                    ]
                }
                for agent in self.session_costs
            ],
            "model_breakdown": model_costs
        }
    
    def format_cost_summary(self, include_model_breakdown: bool = True) -> str:
        """Format cost summary as human-readable string."""
        summary = self.get_session_summary()
        
        if summary["total_cost_usd"] == 0:
            return "No cost data available"
        
        lines = [
            f"💰 Session Cost Summary",
            f"Total Cost: ${summary['total_cost_usd']:.4f}",
            f"Total Tokens: {summary['total_tokens']:,}",
            f"Agents: {summary['agent_count']}"
        ]
        
        if summary["total_execution_time_seconds"] > 0:
            lines.append(f"Total Time: {summary['total_execution_time_seconds']:.1f}s")
        
        if include_model_breakdown and summary["model_breakdown"]:
            lines.append("\n📊 Model Breakdown:")
            for model_name, data in summary["model_breakdown"].items():
                lines.append(f"• {model_name}: ${data['cost_usd']:.4f} ({data['tokens']:,} tokens)")
        
        return "\n".join(lines)
    
    def reset_session(self):
        """Reset session cost tracking."""
        self.session_costs.clear()
        self.total_session_cost = 0.0
        logger.info("Cost tracking session reset")