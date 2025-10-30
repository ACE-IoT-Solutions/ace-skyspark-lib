"""Token management with caching and refresh."""

import asyncio
from datetime import UTC, datetime, timedelta

import structlog

from ace_skyspark_lib.auth.authenticator import ScramAuthenticator

logger = structlog.get_logger()


class TokenManager:
    """Manages auth token caching and refresh."""

    def __init__(self, authenticator: ScramAuthenticator, cache_duration: int = 3600) -> None:
        """Initialize token manager.

        Args:
            authenticator: SCRAM authenticator instance
            cache_duration: Token cache duration in seconds (default 1 hour)
        """
        self.authenticator = authenticator
        self.cache_duration = cache_duration
        self._token: str | None = None
        self._token_expiry: datetime | None = None
        self._refresh_lock = asyncio.Lock()

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

            logger.info("refreshing_auth_token")
            self._token = await self.authenticator.authenticate()
            self._token_expiry = datetime.now(UTC) + timedelta(seconds=self.cache_duration)

            logger.info("token_refreshed", expires_at=self._token_expiry.isoformat())
            return self._token

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
