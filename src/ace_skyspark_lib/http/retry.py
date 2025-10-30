"""Retry logic with exponential backoff."""

import asyncio
from collections.abc import Callable
from typing import Any, TypeVar

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from ace_skyspark_lib.exceptions import SkysparkConnectionError

T = TypeVar("T")


class RetryPolicy:
    """Configurable retry policy with exponential backoff."""

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 30.0,
        jitter: bool = True,
    ) -> None:
        """Initialize retry policy.

        Args:
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            jitter: Add random jitter to delays
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.jitter = jitter

    async def execute(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute function with retry logic.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of successful function execution

        Raises:
            Last exception if all retries exhausted
        """
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.max_retries + 1),
            wait=wait_exponential_jitter(
                initial=self.initial_delay,
                max=self.max_delay,
                jitter=self.max_delay if self.jitter else 0,
            ),
            retry=retry_if_exception(self._is_retryable_exception),
            reraise=True,
        ):
            with attempt:
                return await func(*args, **kwargs)

        msg = "Retry logic failed"
        raise SkysparkConnectionError(msg)

    @staticmethod
    def _is_retryable_exception(exception: BaseException) -> bool:
        """Determine if exception is retryable.

        Args:
            exception: Exception to check

        Returns:
            True if exception should trigger retry
        """
        # Network errors and timeouts
        if isinstance(exception, (httpx.RequestError, httpx.TimeoutException, asyncio.TimeoutError)):
            return True

        # Server errors (5xx)
        if isinstance(exception, httpx.HTTPStatusError) and 500 <= exception.response.status_code < 600:
            return True

        return False
