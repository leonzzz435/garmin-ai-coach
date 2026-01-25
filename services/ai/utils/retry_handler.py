import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

import anthropic
from langgraph.errors import GraphInterrupt

logger = logging.getLogger(__name__)


class RetryableError(Exception):
    pass


class APIOverloadError(RetryableError):
    pass


class RetryConfig:

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: set[type[Exception]] | None = None,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or {
            anthropic.APIStatusError,
            anthropic.RateLimitError,
            APIOverloadError,
        }

    def calculate_delay(self, attempt: int) -> float:
        delay = min(self.base_delay * (self.exponential_base**attempt), self.max_delay)
        if self.jitter:
            jitter_range = delay * 0.1
            delay += random.uniform(-jitter_range, jitter_range)
        return max(delay, 0.1)


async def retry_with_backoff(
    func: Callable[[], Awaitable[Any]],
    config: RetryConfig | None = None,
    context: str = "operation",
) -> Any:

    if config is None:
        config = RetryConfig()

    last_exception = None

    for attempt in range(config.max_retries + 1):
        try:
            logger.debug(
                "Attempting %s (attempt %s/%s)",
                context,
                attempt + 1,
                config.max_retries + 1,
            )
            return await func()

        except GraphInterrupt:
            raise

        except Exception as e:
            last_exception = e

            is_retryable = any(isinstance(e, exc_type) for exc_type in config.retryable_exceptions)

            if isinstance(e, anthropic.APIStatusError):
                error_type = (
                    getattr(e.body, "error", {}).get("type", "") if hasattr(e, "body") else ""
                )
                if error_type in ["overloaded_error", "rate_limit_error"]:
                    is_retryable = True
                    logger.warning("%s failed with %s: %s", context, error_type, e)
                else:
                    logger.error("%s failed with non-retryable API error: %s", context, e)
                    break

            if not is_retryable:
                logger.error("%s failed with non-retryable error: %s", context, e)
                break

            if attempt < config.max_retries:
                delay = config.calculate_delay(attempt)
                logger.info(
                    "%s failed (attempt %s), retrying in %.1fs: %s",
                    context,
                    attempt + 1,
                    delay,
                    e,
                )
                await asyncio.sleep(delay)
            else:
                logger.error("%s failed after %s attempts: %s", context, config.max_retries + 1, e)

    if last_exception is None:
        raise RuntimeError(f"{context} failed without capturing an exception")
    raise last_exception


def with_retry(config: RetryConfig | None = None, context: str | None = None):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            func_context = context or func.__name__

            async def call_func():
                return await func(*args, **kwargs)

            return await retry_with_backoff(call_func, config, func_context)

        return wrapper

    return decorator


DEFAULT_CONFIG = RetryConfig(max_retries=3, base_delay=1.0, max_delay=60.0)

AI_ANALYSIS_CONFIG = RetryConfig(
    max_retries=5,
    base_delay=2.0,
    max_delay=120.0,
    exponential_base=2.5,
)

QUICK_RETRY_CONFIG = RetryConfig(max_retries=2, base_delay=0.5, max_delay=10.0)


def is_anthropic_overload_error(exception: Exception) -> bool:
    return (
        isinstance(exception, anthropic.APIStatusError)
        and hasattr(exception, "body")
        and hasattr(exception.body, "error")
        and exception.body.error.get("type", "") == "overloaded_error"
    )


def get_error_details(exception: Exception) -> str:
    if (
        isinstance(exception, anthropic.APIStatusError)
        and hasattr(exception, "body")
        and hasattr(exception.body, "error")
    ):
        error_info = exception.body.error
        return f"{error_info.get('type', 'unknown')}: {error_info.get('message', str(exception))}"
    return str(exception)
