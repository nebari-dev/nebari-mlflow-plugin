"""Utilities for timeout and retry operations."""

import asyncio
import functools
import logging
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def with_timeout_and_retry(
    timeout: int = 30,
    max_retries: int = 2,
    retry_delay: float = 2.0,
    operation_name: str | None = None
):
    """
    Decorator that adds timeout and retry logic to async or sync functions.

    For sync functions, they are executed in a thread pool with timeout.
    For async functions, they are executed with timeout directly.

    Args:
        timeout: Timeout in seconds for each attempt
        max_retries: Maximum number of retry attempts (total attempts = max_retries + 1)
        retry_delay: Delay in seconds between retry attempts
        operation_name: Optional name for logging (defaults to function name)

    Example:
        @with_timeout_and_retry(timeout=10, max_retries=3)
        async def my_async_function():
            ...

        @with_timeout_and_retry(timeout=5, max_retries=1)
        def my_sync_function():
            ...

    Raises:
        asyncio.TimeoutError: If all attempts timeout
        Exception: If all attempts fail with exceptions
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            op_name = operation_name or func.__name__

            for attempt in range(max_retries + 1):
                try:
                    logger.debug(
                        f"{op_name}: attempt {attempt + 1}/{max_retries + 1}"
                    )

                    # Check if function is async or sync
                    if asyncio.iscoroutinefunction(func):
                        # Async function - await with timeout
                        result = await asyncio.wait_for(
                            func(*args, **kwargs),
                            timeout=timeout
                        )
                    else:
                        # Sync function - run in thread pool with timeout
                        result = await asyncio.wait_for(
                            asyncio.to_thread(func, *args, **kwargs),
                            timeout=timeout
                        )

                    logger.debug(f"{op_name}: succeeded on attempt {attempt + 1}")
                    return result

                except asyncio.TimeoutError:
                    logger.warning(
                        f"{op_name}: timed out after {timeout}s "
                        f"(attempt {attempt + 1}/{max_retries + 1})"
                    )
                    if attempt < max_retries:
                        await asyncio.sleep(retry_delay)
                    else:
                        logger.error(f"{op_name}: all attempts timed out")
                        raise

                except Exception as e:
                    logger.warning(
                        f"{op_name}: failed with {type(e).__name__}: {e} "
                        f"(attempt {attempt + 1}/{max_retries + 1})"
                    )
                    if attempt < max_retries:
                        await asyncio.sleep(retry_delay)
                    else:
                        logger.error(f"{op_name}: all attempts failed")
                        raise

        return async_wrapper

    return decorator


def with_configurable_timeout_and_retry(
    timeout_setting: str = "webhook_startup_timeout",
    retries_setting: str = "webhook_startup_retries",
    operation_name: str | None = None
):
    """
    Decorator that reads timeout and retry settings from the config.

    This allows the timeout and retry values to be configured via environment
    variables instead of being hardcoded.

    Args:
        timeout_setting: Name of the config attribute for timeout
        retries_setting: Name of the config attribute for max retries
        operation_name: Optional name for logging

    Example:
        @with_configurable_timeout_and_retry(
            timeout_setting="webhook_startup_timeout",
            retries_setting="webhook_startup_retries"
        )
        def my_function(self):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            # Import here to avoid circular imports
            from src.config import settings

            timeout = getattr(settings, timeout_setting, 30)
            max_retries = getattr(settings, retries_setting, 2)
            op_name = operation_name or func.__name__

            # Use the base decorator with settings values
            decorated = with_timeout_and_retry(
                timeout=timeout,
                max_retries=max_retries,
                operation_name=op_name
            )(func)

            return await decorated(*args, **kwargs)

        return async_wrapper

    return decorator
