"""Tests for timeout and retry utilities."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from src.timeout_utils import with_timeout_and_retry, with_configurable_timeout_and_retry


@pytest.mark.asyncio
async def test_decorator_with_async_function_success():
    """Test decorator with async function that succeeds on first try."""
    call_count = 0

    @with_timeout_and_retry(timeout=5, max_retries=2)
    async def async_func():
        nonlocal call_count
        call_count += 1
        return "success"

    result = await async_func()

    assert result == "success"
    assert call_count == 1  # Should succeed on first try


@pytest.mark.asyncio
async def test_decorator_with_sync_function_success():
    """Test decorator with sync function that succeeds on first try."""
    call_count = 0

    @with_timeout_and_retry(timeout=5, max_retries=2)
    def sync_func():
        nonlocal call_count
        call_count += 1
        return "success"

    result = await sync_func()

    assert result == "success"
    assert call_count == 1  # Should succeed on first try


@pytest.mark.asyncio
async def test_decorator_retry_on_exception():
    """Test decorator retries on exception and eventually succeeds."""
    call_count = 0

    @with_timeout_and_retry(timeout=5, max_retries=2, retry_delay=0.1)
    async def flaky_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("Temporary error")
        return "success"

    result = await flaky_func()

    assert result == "success"
    assert call_count == 3  # Failed twice, succeeded on third attempt


@pytest.mark.asyncio
async def test_decorator_retry_on_timeout():
    """Test decorator retries on timeout and eventually succeeds."""
    call_count = 0

    @with_timeout_and_retry(timeout=0.5, max_retries=2, retry_delay=0.1)
    async def slow_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            await asyncio.sleep(2)  # Exceeds timeout
        return "success"

    result = await slow_func()

    assert result == "success"
    assert call_count == 3  # Timed out twice, succeeded on third attempt


@pytest.mark.asyncio
async def test_decorator_max_retries_exceeded():
    """Test decorator fails after max retries exceeded."""
    call_count = 0

    @with_timeout_and_retry(timeout=5, max_retries=2, retry_delay=0.1)
    async def always_fails():
        nonlocal call_count
        call_count += 1
        raise ValueError("Always fails")

    with pytest.raises(ValueError, match="Always fails"):
        await always_fails()

    assert call_count == 3  # Initial attempt + 2 retries


@pytest.mark.asyncio
async def test_decorator_timeout_exceeded():
    """Test decorator fails after all timeouts exceeded."""
    call_count = 0

    @with_timeout_and_retry(timeout=0.5, max_retries=2, retry_delay=0.1)
    async def always_slow():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(2)  # Always exceeds timeout
        return "success"

    with pytest.raises(asyncio.TimeoutError):
        await always_slow()

    assert call_count == 3  # Initial attempt + 2 retries


@pytest.mark.asyncio
async def test_decorator_with_function_arguments():
    """Test decorator works with function arguments."""
    @with_timeout_and_retry(timeout=5, max_retries=1)
    async def func_with_args(a, b, c=None):
        return f"a={a}, b={b}, c={c}"

    result = await func_with_args(1, 2, c=3)

    assert result == "a=1, b=2, c=3"


@pytest.mark.asyncio
async def test_decorator_with_custom_operation_name(caplog):
    """Test decorator uses custom operation name in logs."""
    @with_timeout_and_retry(timeout=5, max_retries=0, operation_name="my_custom_operation")
    async def test_func():
        return "success"

    with caplog.at_level("DEBUG"):
        await test_func()

    assert "my_custom_operation" in caplog.text


@pytest.mark.asyncio
async def test_decorator_retry_delay():
    """Test decorator waits between retries."""
    call_times = []

    @with_timeout_and_retry(timeout=5, max_retries=2, retry_delay=0.5)
    async def func():
        call_times.append(asyncio.get_event_loop().time())
        if len(call_times) < 3:
            raise ValueError("Retry")
        return "success"

    await func()

    # Check that there's approximately 0.5s delay between calls
    assert len(call_times) == 3
    delay1 = call_times[1] - call_times[0]
    delay2 = call_times[2] - call_times[1]
    assert 0.4 < delay1 < 0.7  # Allow some tolerance
    assert 0.4 < delay2 < 0.7


@pytest.mark.asyncio
async def test_decorator_with_sync_function_timeout():
    """Test decorator properly times out sync functions."""
    import time

    @with_timeout_and_retry(timeout=0.5, max_retries=1, retry_delay=0.1)
    def slow_sync_func():
        time.sleep(2)  # Exceeds timeout
        return "success"

    with pytest.raises(asyncio.TimeoutError):
        await slow_sync_func()


@pytest.mark.asyncio
async def test_configurable_decorator_reads_settings():
    """Test configurable decorator reads from settings."""
    # Patch settings at the config module level
    with patch("src.config.settings") as mock_settings:
        mock_settings.webhook_startup_timeout = 10
        mock_settings.webhook_startup_retries = 5

        call_count = 0

        @with_configurable_timeout_and_retry(
            timeout_setting="webhook_startup_timeout",
            retries_setting="webhook_startup_retries"
        )
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                raise ValueError("Retry")
            return "success"

        result = await test_func()

        assert result == "success"
        assert call_count == 4  # Should have used the configured retry count


@pytest.mark.asyncio
async def test_configurable_decorator_default_values():
    """Test configurable decorator uses defaults when settings don't exist."""
    # Create a settings object without the specific attributes
    mock_settings = MagicMock(spec=[])  # Empty spec means no attributes

    with patch("src.config.settings", mock_settings):
        # The decorator should handle missing attributes by using defaults
        @with_configurable_timeout_and_retry()
        async def test_func():
            return "success"

        result = await test_func()
        assert result == "success"


@pytest.mark.asyncio
async def test_decorator_preserves_function_metadata():
    """Test decorator preserves original function name and docstring."""
    @with_timeout_and_retry(timeout=5, max_retries=1)
    async def original_func():
        """Original docstring."""
        return "success"

    assert original_func.__name__ == "original_func"
    assert original_func.__doc__ == "Original docstring."


@pytest.mark.asyncio
async def test_decorator_with_multiple_exceptions():
    """Test decorator handles different exception types."""
    call_count = 0
    exceptions = [ValueError("Error 1"), TypeError("Error 2"), KeyError("Error 3")]

    @with_timeout_and_retry(timeout=5, max_retries=3, retry_delay=0.1)
    async def func_with_different_errors():
        nonlocal call_count
        if call_count < len(exceptions):
            exc = exceptions[call_count]
            call_count += 1
            raise exc
        call_count += 1
        return "success"

    result = await func_with_different_errors()

    assert result == "success"
    assert call_count == 4  # 3 failures + 1 success


@pytest.mark.asyncio
async def test_decorator_logs_attempts(caplog):
    """Test decorator logs each attempt."""
    call_count = 0

    @with_timeout_and_retry(timeout=5, max_retries=2, retry_delay=0.1)
    async def func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("Retry")
        return "success"

    with caplog.at_level("DEBUG"):
        await func()

    # Check that attempts are logged
    assert "attempt 1/3" in caplog.text
    assert "attempt 2/3" in caplog.text
    assert "attempt 3/3" in caplog.text


@pytest.mark.asyncio
async def test_decorator_logs_success(caplog):
    """Test decorator logs successful completion."""
    @with_timeout_and_retry(timeout=5, max_retries=2, operation_name="test_op")
    async def func():
        return "success"

    with caplog.at_level("DEBUG"):
        await func()

    assert "test_op: succeeded on attempt 1" in caplog.text


@pytest.mark.asyncio
async def test_decorator_logs_final_failure(caplog):
    """Test decorator logs when all attempts fail."""
    @with_timeout_and_retry(timeout=5, max_retries=1, retry_delay=0.1, operation_name="test_op")
    async def func():
        raise ValueError("Always fails")

    with caplog.at_level("ERROR"):
        with pytest.raises(ValueError):
            await func()

    assert "test_op: all attempts failed" in caplog.text
