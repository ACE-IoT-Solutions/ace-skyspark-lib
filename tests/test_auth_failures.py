from __future__ import annotations

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock

import httpx
import pytest

from ace_skyspark_lib.auth.authenticator import ScramAuthenticator
from ace_skyspark_lib.auth.token_manager import TokenManager
from ace_skyspark_lib.exceptions import AuthenticationError


@dataclass
class StubAuthenticator:
    failures_remaining: int
    calls: int = 0

    async def authenticate(self) -> str:
        self.calls += 1
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise AuthenticationError("temporary auth failure")
        return "test-token"


@pytest.mark.asyncio
async def test_hello_missing_challenge_includes_response_diagnostics() -> None:
    request = httpx.Request("GET", "https://skyspark.example/api/demo/about")
    response = httpx.Response(
        200,
        headers={"content-type": "text/html", "server": "proxy"},
        text="<html>Login required</html>",
        request=request,
    )
    session = AsyncMock()
    session.get.return_value = response
    authenticator = ScramAuthenticator(
        base_url="https://skyspark.example/api",
        project="demo",
        username="user",
        password="password",  # noqa: S106
        session=session,
    )

    with pytest.raises(AuthenticationError) as exc_info:
        await authenticator._hello()

    message = str(exc_info.value)
    assert "usable WWW-Authenticate challenge" in message
    assert "status=200" in message
    assert "content_type='text/html'" in message
    assert "server='proxy'" in message
    assert "Login required" in message


@pytest.mark.asyncio
async def test_token_refresh_retries_with_exponential_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authenticator = StubAuthenticator(failures_remaining=2)
    sleep = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep)
    manager = TokenManager(
        authenticator,  # type: ignore[arg-type]
        max_retries=2,
        initial_retry_delay=0.25,
        max_retry_delay=1.0,
    )

    token = await manager.get_token()

    assert token == "test-token"  # noqa: S105
    assert authenticator.calls == 3
    assert [call.args[0] for call in sleep.await_args_list] == [0.25, 0.5]


@pytest.mark.asyncio
async def test_failed_refresh_is_shared_with_queued_callers() -> None:
    authenticator = StubAuthenticator(failures_remaining=10)
    manager = TokenManager(
        authenticator,  # type: ignore[arg-type]
        max_retries=0,
        initial_retry_delay=1.0,
        max_retry_delay=2.0,
    )

    results = await asyncio.gather(
        manager.get_token(),
        manager.get_token(),
        return_exceptions=True,
    )

    assert authenticator.calls == 1
    assert all(isinstance(result, AuthenticationError) for result in results)
    assert any("refresh is in backoff" in str(result) for result in results)
