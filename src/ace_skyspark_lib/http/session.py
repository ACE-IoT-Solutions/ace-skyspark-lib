"""Async HTTP session management with connection pooling."""

from typing import Any

import httpx
import structlog

from ace_skyspark_lib.exceptions import ServerError
from ace_skyspark_lib.http.retry import RetryPolicy

logger = structlog.get_logger()


class SessionManager:
    """Manages async HTTP session with connection pooling and retry logic."""

    def __init__(
        self,
        session: httpx.AsyncClient,
        base_url: str,
        project: str,
        token_provider: Any,
        max_retries: int = 3,
    ) -> None:
        """Initialize session manager.

        Args:
            session: httpx AsyncClient to use
            base_url: Base URL for SkySpark server (e.g., http://server:8080/api)
            project: Project name in SkySpark
            token_provider: Object providing auth tokens (TokenManager)
            max_retries: Maximum retry attempts
        """
        self.session = session
        self.base_url = base_url.rstrip("/")
        self.project = project
        self.token_provider = token_provider
        self.retry_policy = RetryPolicy(max_retries=max_retries)

    async def post_zinc(
        self,
        endpoint: str,
        zinc_data: str,
    ) -> dict[str, Any]:
        """POST Zinc grid with automatic retry.

        Args:
            endpoint: API endpoint (e.g., "commit", "evalAll")
            zinc_data: Zinc-formatted grid string

        Returns:
            JSON response

        Raises:
            ServerError: If server returns error
            SkysparkConnectionError: If connection fails
        """

        async def _post() -> dict[str, Any]:
            url = self._build_url(endpoint)
            headers = self._get_headers("text/zinc")

            logger.debug(
                "post_zinc",
                url=url,
                zinc_size=len(zinc_data),
                has_auth=bool(headers.get("Authorization")),
                auth_header=headers.get("Authorization", "")[:30],
                all_headers=str(headers),
            )

            response = await self.session.post(
                url,
                content=zinc_data,
                headers=headers,
                follow_redirects=False,
            )

            response_text = response.text

            if response.status_code != 200:
                logger.error(
                    "post_zinc_failed",
                    status=response.status_code,
                    response=response_text[:500],
                    response_headers=str(dict(response.headers)),
                )
                msg = f"Request failed with status {response.status_code}"
                raise ServerError(msg)

            # Try to parse as JSON
            try:
                return response.json()
            except Exception:
                # If response is not JSON, return text wrapped in dict
                return {"text": response_text}

        return await self.retry_policy.execute(_post)

    async def get_json(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """GET JSON response with automatic retry.

        Args:
            endpoint: API endpoint
            params: Query parameters

        Returns:
            JSON response

        Raises:
            ServerError: If server returns error
            SkysparkConnectionError: If connection fails
        """

        async def _get() -> dict[str, Any]:
            url = self._build_url(endpoint)
            headers = self._get_headers("application/json")

            logger.debug("get_json", url=url, params=params)

            response = await self.session.get(url, params=params, headers=headers)
            if response.status_code != 200:
                response_text = response.text
                logger.error(
                    "get_json_failed",
                    status=response.status_code,
                    response=response_text[:500],
                )
                msg = f"Request failed with status {response.status_code}"
                raise ServerError(msg)

            return response.json()

        return await self.retry_policy.execute(_get)

    async def post_json(
        self,
        endpoint: str,
        json_data: dict[str, Any],
    ) -> dict[str, Any]:
        """POST JSON with automatic retry.

        Args:
            endpoint: API endpoint
            json_data: JSON payload

        Returns:
            JSON response

        Raises:
            ServerError: If server returns error
            SkysparkConnectionError: If connection fails
        """

        async def _post() -> dict[str, Any]:
            url = self._build_url(endpoint)
            headers = self._get_headers("application/json")

            logger.debug("post_json", url=url)

            response = await self.session.post(url, json=json_data, headers=headers)
            if response.status_code != 200:
                response_text = response.text
                logger.error(
                    "post_json_failed",
                    status=response.status_code,
                    response=response_text[:500],
                )
                msg = f"Request failed with status {response.status_code}"
                raise ServerError(msg)

            return response.json()

        return await self.retry_policy.execute(_post)

    def _build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint.

        Args:
            endpoint: API endpoint path

        Returns:
            Full URL
        """
        endpoint = endpoint.lstrip("/")
        return f"{self.base_url}/{self.project}/{endpoint}"

    def _get_headers(self, content_type: str) -> dict[str, str]:
        """Get headers with auth token.

        Args:
            content_type: Content-Type header value

        Returns:
            Headers dictionary
        """
        token = self.token_provider.get_cached_token()
        logger.debug("get_headers", has_token=bool(token), token_len=len(token) if token else 0)
        headers = {
            "Content-Type": content_type,
            "Accept": "application/json",
        }
        if token:
            # SkySpark authentication uses Bearer authToken format (from original library)
            headers["Authorization"] = f"Bearer authToken={token}"
        return headers
