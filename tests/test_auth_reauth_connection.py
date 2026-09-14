"""Regression test for re-authentication reusing a stale connection.

SkySpark appears to treat a connection as already-authenticated once one
handshake has completed on it, and answers a later HELLO on that same
(pooled/reused) connection with a plain 200 instead of a fresh 401 challenge.
That only surfaces when a flow run outlives its token and has to
re-authenticate mid-run on the long-lived shared auth session — see the
incident this guards against: a multi-hour ACE-to-SkySpark catch-up run
authenticated successfully once, then failed every retry of its second
authentication ~15 minutes later with "HELLO response did not contain a
usable WWW-Authenticate challenge: status=200 ...".
"""

from __future__ import annotations

import httpx
import pytest

from ace_skyspark_lib.auth.authenticator import ScramAuthenticator


class _SentinelSession:
    """Stands in for the caller-supplied, long-lived auth session.

    `authenticate()` must never issue a request on this object — doing so
    would mean it's reusing a connection a prior handshake already touched.
    """

    async def get(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("authenticate() must not use the externally-supplied session")


class _FakeAsyncClient:
    instances: list["_FakeAsyncClient"] = []

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.closed = False
        _FakeAsyncClient.instances.append(self)

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_authenticate_uses_a_fresh_connection_per_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeAsyncClient.instances = []
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)

    sentinel = _SentinelSession()
    authenticator = ScramAuthenticator(
        base_url="http://skyspark.example/api",
        project="demo",
        username="user",
        password="password",  # noqa: S106
        session=sentinel,  # type: ignore[arg-type]
    )

    seen_sessions_per_call: list[object] = []

    async def fake_hello() -> str:
        seen_sessions_per_call.append(authenticator.session)
        return "handshake-1"

    async def fake_client_first(_handshake_token: str) -> tuple[str, str]:
        return "handshake-2", "server-first"

    async def fake_client_final(_handshake_token: str, _server_first: str) -> str:
        return "token"  # noqa: S105

    monkeypatch.setattr(authenticator, "_hello", fake_hello)
    monkeypatch.setattr(authenticator, "_client_first", fake_client_first)
    monkeypatch.setattr(authenticator, "_client_final", fake_client_final)

    token1 = await authenticator.authenticate()
    token2 = await authenticator.authenticate()

    assert token1 == token2 == "token"  # noqa: S105
    # Two authenticate() calls => two distinct fresh connections, neither of
    # which is the externally-supplied long-lived session.
    assert len(seen_sessions_per_call) == 2
    assert seen_sessions_per_call[0] is not seen_sessions_per_call[1]
    assert sentinel not in seen_sessions_per_call
    # Each fresh connection is closed once its handshake completes, and the
    # authenticator's externally-visible `.session` is restored afterward so
    # other code paths (and other tests) that rely on the injected session
    # still see it.
    assert len(_FakeAsyncClient.instances) == 2
    assert all(inst.closed for inst in _FakeAsyncClient.instances)
    assert authenticator.session is sentinel
