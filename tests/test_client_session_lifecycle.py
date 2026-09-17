from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from ace_skyspark_lib.auth.token_manager import TokenManager
from ace_skyspark_lib.client import SkysparkClient


class StubAuthenticator:
    async def authenticate(self) -> str:
        return "unused-token"


@pytest.mark.asyncio
async def test_context_exit_closes_server_session_before_http_clients() -> None:
    client = SkysparkClient(
        base_url="https://skyspark.example/api",
        project="demo",
        username="user",
        password="password",  # noqa: S106
    )
    auth_session = AsyncMock()
    api_session = AsyncMock()
    api_session.post.return_value = httpx.Response(
        200,
        request=httpx.Request("POST", "https://skyspark.example/api/demo/close"),
    )
    token_manager = TokenManager(StubAuthenticator())  # type: ignore[arg-type]
    token_manager._token = "session-token"  # noqa: S105
    client._auth_session = auth_session
    client._api_session = api_session
    client._token_manager = token_manager

    await client.__aexit__(None, None, None)

    api_session.post.assert_awaited_once_with(
        "https://skyspark.example/api/demo/close",
        content='ver:"3.0"\nempty\n',
        headers={
            "Authorization": "Bearer authToken=session-token",
            "Content-Type": "text/zinc",
            "Accept": "application/json",
        },
        follow_redirects=False,
    )
    assert token_manager.get_cached_token() is None
    auth_session.aclose.assert_awaited_once()
    api_session.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_context_exit_still_closes_http_clients_when_server_close_fails() -> None:
    client = SkysparkClient(
        base_url="https://skyspark.example/api",
        project="demo",
        username="user",
        password="password",  # noqa: S106
    )
    auth_session = AsyncMock()
    api_session = AsyncMock()
    api_session.post.return_value = httpx.Response(
        500,
        request=httpx.Request("POST", "https://skyspark.example/api/demo/close"),
    )
    token_manager = TokenManager(StubAuthenticator())  # type: ignore[arg-type]
    token_manager._token = "session-token"  # noqa: S105
    client._auth_session = auth_session
    client._api_session = api_session
    client._token_manager = token_manager

    await client.__aexit__(None, None, None)

    assert token_manager.get_cached_token() is None
    auth_session.aclose.assert_awaited_once()
    api_session.aclose.assert_awaited_once()
