"""Token management with caching and refresh."""

import asyncio
from datetime import UTC, datetime, timedelta

import structlog

from ace_skyspark_lib.auth.authenticator import ScramAuthenticator
from ace_skyspark_lib.exceptions import AuthenticationError

logger = structlog.get_logger()


class TokenManager:
    """Manages auth token caching and refresh."""

    def __init__(
        self,
        authenticator: ScramAuthenticator,
        cache_duration: int = 3600,
        max_retries: int = 3,
        initial_retry_delay: float = 1.0,
        max_retry_delay: float = 30.0,
    ) -> None:
        """Initialize token manager.

        Args:
            authenticator: SCRAM authenticator instance
            cache_duration: Token cache duration in seconds (default 1 hour)
            max_retries: Authentication retries after the initial attempt
            initial_retry_delay: Delay before the first retry in seconds
            max_retry_delay: Maximum delay between retries in seconds
        """
        self.authenticator = authenticator
        self.cache_duration = cache_duration
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        self.max_retry_delay = max_retry_delay
        self._token: str | None = None
        self._token_expiry: datetime | None = None
        self._refresh_lock = asyncio.Lock()
        self._last_refresh_error: AuthenticationError | None = None
        self._next_refresh_at = 0.0

    async def get_token(self) -> str:
        """Get valid token (cached or refresh).

        Returns:
            Valid authentication token

        Raises:
            AuthenticationError: If token acquisition fails
        """
        # Check if cached token is still valid
        if self._token and self._token_expiry and datetime.now(UTC) < self._token_expiry:
            logger.debug("using_cached_token")
            return self._token

        # Token expired or doesn't exist, refresh
        return await self.refresh_token()

    async def refresh_token(self) -> str:
        """Force token refresh.

        Returns:
            New authentication token

        Raises:
            AuthenticationError: If authentication fails
        """
        async with self._refresh_lock:
            # Double-check after acquiring lock
            if self._token and self._token_expiry and datetime.now(UTC) < self._token_expiry:
                return self._token

            loop = asyncio.get_running_loop()
            retry_after = self._next_refresh_at - loop.time()
            if self._last_refresh_error and retry_after > 0:
                logger.warning(
                    "auth_token_refresh_backoff_active",
                    retry_after_seconds=round(retry_after, 3),
                )
                msg = (
                    f"Authentication refresh is in backoff for {retry_after:.3f} seconds "
                    f"after: {self._last_refresh_error}"
                )
                raise AuthenticationError(msg) from self._last_refresh_error

            for attempt in range(self.max_retries + 1):
                logger.info(
                    "refreshing_auth_token",
                    attempt=attempt + 1,
                    max_attempts=self.max_retries + 1,
                )
                try:
                    self._token = await self.authenticator.authenticate()
                    break
                except AuthenticationError as exc:
                    self._last_refresh_error = exc
                    delay = self._retry_delay(attempt)
                    self._next_refresh_at = loop.time() + delay
                    if attempt >= self.max_retries:
                        logger.error(
                            "auth_token_refresh_exhausted",
                            attempts=attempt + 1,
                            retry_after_seconds=delay,
                        )
                        raise
                    logger.warning(
                        "auth_token_refresh_retry",
                        attempt=attempt + 1,
                        retry_in_seconds=delay,
                        error=str(exc),
                    )
                    await asyncio.sleep(delay)

            self._token_expiry = datetime.now(UTC) + timedelta(seconds=self.cache_duration)
            self._last_refresh_error = None
            self._next_refresh_at = 0.0

            logger.info("token_refreshed", expires_at=self._token_expiry.isoformat())
            assert self._token is not None
            return self._token

    def _retry_delay(self, attempt: int) -> float:
        """Calculate the bounded exponential delay after a failed attempt."""
        return min(self.initial_retry_delay * (2**attempt), self.max_retry_delay)

    def get_cached_token(self) -> str | None:
        """Get cached token without refresh (for headers).

        Returns:
            Cached token or None if not available
        """
        return self._token

    def invalidate(self) -> None:
        """Invalidate cached token."""
        logger.info("token_invalidated")
        self._token = None
        self._token_expiry = None
