import logging
from typing import Any

from langchain.callbacks.base import BaseCallbackHandler

logger = logging.getLogger(__name__)


class ToolUseLimiter(BaseCallbackHandler):

    def __init__(self, tool_limits: dict[str, int], strict_mode: bool = True):
        self.tool_limits = tool_limits
        self.tool_counts = {tool: 0 for tool in tool_limits}
        self.strict_mode = strict_mode
        logger.info(f"Initialized ToolUseLimiter with limits: {tool_limits}")

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: Any,
        parent_run_id: Any | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
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
        parent_run_id: Any | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        # Could add additional logging or metrics here if needed
        pass

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        parent_run_id: Any | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        logger.warning(f"Tool execution failed: {error}")

    def get_usage_stats(self) -> dict[str, dict[str, int]]:
        stats = {}
        for tool_name, limit in self.tool_limits.items():
            stats[tool_name] = {
                "used": self.tool_counts[tool_name],
                "limit": limit,
                "remaining": max(0, limit - self.tool_counts[tool_name]),
            }
        return stats

    def reset_counts(self) -> None:
        self.tool_counts = {tool: 0 for tool in self.tool_limits}
        logger.info("Reset all tool usage counters")


class ToolUsageExceededError(Exception):
    pass


# Pre-configured limiters for common use cases
class PlottingLimiter(ToolUseLimiter):

    def __init__(self, max_plots: int = 2, strict_mode: bool = True):
        tool_limits = {
            "python_plotting_tool": max_plots,
            "list_available_plots": 10,  # More generous for plot listing
        }
        super().__init__(tool_limits, strict_mode)
        logger.info(f"Initialized PlottingLimiter with max_plots={max_plots}")


# Factory function for easy integration
def create_plotting_limiter(max_plots: int = 2, strict_mode: bool = True) -> PlottingLimiter:
    return PlottingLimiter(max_plots=max_plots, strict_mode=strict_mode)
