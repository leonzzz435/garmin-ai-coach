"""LangChain-native tool usage limiter using CallbackHandler."""

import logging
from typing import Dict, Any, Optional, List
from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.agents import AgentAction

logger = logging.getLogger(__name__)

class ToolUseLimiter(BaseCallbackHandler):
    """LangChain CallbackHandler that tracks and limits tool usage per tool type.
    
    This is the LangChain-native way to implement tool usage limits without
    custom agent logic. It integrates seamlessly with AgentExecutor.
    """
    
    def __init__(self, tool_limits: Dict[str, int], strict_mode: bool = True):
        """Initialize tool usage limiter.
        
        Args:
            tool_limits: Dictionary mapping tool names to maximum allowed calls
                        e.g., {"python_plotting_tool": 2, "list_available_plots": 5}
            strict_mode: If True, raises exception when limit exceeded.
                        If False, just logs warnings.
        """
        self.tool_limits = tool_limits
        self.tool_counts = {tool: 0 for tool in tool_limits}
        self.strict_mode = strict_mode
        logger.info(f"Initialized ToolUseLimiter with limits: {tool_limits}")
    
    def on_tool_start(
        self, 
        serialized: Dict[str, Any], 
        input_str: str, 
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a tool starts executing.
        
        This is where we track and potentially block tool usage.
        """
        tool_name = serialized.get("name", "unknown_tool")
        
        if tool_name in self.tool_limits:
            self.tool_counts[tool_name] += 1
            current_count = self.tool_counts[tool_name]
            limit = self.tool_limits[tool_name]
            
            logger.info(f"Tool '{tool_name}' usage: {current_count}/{limit}")
            
            if current_count > limit:
                error_msg = (
                    f"Tool '{tool_name}' exceeded maximum allowed calls. "
                    f"Used: {current_count}, Limit: {limit}. "
                    f"Consider creating fewer, more comprehensive visualizations."
                )
                
                if self.strict_mode:
                    logger.error(error_msg)
                    raise ToolUsageExceededError(error_msg)
                else:
                    logger.warning(f"WARNING: {error_msg}")
            elif current_count == limit:
                logger.warning(
                    f"Tool '{tool_name}' has reached its limit ({limit}). "
                    f"Next usage will be blocked."
                )
    
    def on_tool_end(
        self,
        output: str,
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a tool execution completes successfully."""
        # Could add additional logging or metrics here if needed
        pass
    
    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        tags: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a tool execution fails.
        
        Note: We don't decrement counters on error to prevent
        agents from exploiting failed calls to bypass limits.
        """
        logger.warning(f"Tool execution failed: {error}")
    
    def get_usage_stats(self) -> Dict[str, Dict[str, int]]:
        """Get current usage statistics.
        
        Returns:
            Dictionary with usage stats for each limited tool
        """
        stats = {}
        for tool_name, limit in self.tool_limits.items():
            stats[tool_name] = {
                "used": self.tool_counts[tool_name],
                "limit": limit,
                "remaining": max(0, limit - self.tool_counts[tool_name])
            }
        return stats
    
    def reset_counts(self) -> None:
        """Reset all tool usage counters.
        
        Useful for starting a new analysis session.
        """
        self.tool_counts = {tool: 0 for tool in self.tool_limits}
        logger.info("Reset all tool usage counters")

class ToolUsageExceededError(Exception):
    """Exception raised when a tool usage limit is exceeded."""
    pass

# Pre-configured limiters for common use cases
class PlottingLimiter(ToolUseLimiter):
    """Pre-configured limiter for plotting tools with sensible defaults."""
    
    def __init__(self, max_plots: int = 2, strict_mode: bool = True):
        """Initialize plotting limiter.
        
        Args:
            max_plots: Maximum number of plots each agent can create (default: 2)
            strict_mode: Whether to strictly enforce limits
        """
        tool_limits = {
            "python_plotting_tool": max_plots,
            "list_available_plots": 10  # More generous for plot listing
        }
        super().__init__(tool_limits, strict_mode)
        logger.info(f"Initialized PlottingLimiter with max_plots={max_plots}")

# Factory function for easy integration
def create_plotting_limiter(max_plots: int = 2, strict_mode: bool = True) -> PlottingLimiter:
    """Factory function to create a plotting limiter.
    
    Args:
        max_plots: Maximum number of plots per agent (default: 2)
        strict_mode: Whether to enforce limits strictly
        
    Returns:
        Configured PlottingLimiter instance
    """
    return PlottingLimiter(max_plots=max_plots, strict_mode=strict_mode)