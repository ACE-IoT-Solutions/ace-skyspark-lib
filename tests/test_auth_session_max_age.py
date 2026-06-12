from __future__ import annotations

from dataclasses import dataclass

import pytest

from ace_skyspark_lib.auth.authenticator import ScramAuthenticator
from ace_skyspark_lib.client import SkysparkClient


@dataclass
class FakeResponse:
    status_code: int
    headers: dict[str, str]


class FakeSession:
    def __init__(self) -> None:
        self.auth_headers: list[str] = []

    async def get(self, _url: str, headers: dict[str, str]) -> FakeResponse:
        auth_header = headers["Authorization"]
        self.auth_headers.append(auth_header)
        if auth_header.startswith("SCRAM "):
            return FakeResponse(
                200,
                {
                    "authentication-info": (
                        "authToken=test-token, data=dmVyaWZpZWQ"
                    )
                },
            )
        raise AssertionError(f"unexpected auth header: {auth_header}")


class FakeScramClient:
    def get_client_final(self) -> str:
        return "client-final"

    def set_server_final(self, _server_final: str) -> None:
        return None


@pytest.mark.asyncio
async def test_client_final_requests_default_15_minute_session() -> None:
    session = FakeSession()
    authenticator = ScramAuthenticator(
        base_url="http://skyspark.example/api",
        project="demo",
        username="user",
        password="password",  # noqa: S106
        session=session,  # type: ignore[arg-type]
    )
    authenticator._scram_client = FakeScramClient()

    token = await authenticator._client_final("handshake-token", "server-first")

    assert token == "test-token"  # noqa: S105
    assert "maxAge=900" in session.auth_headers[-1]


def test_client_token_cache_defaults_to_session_max_age() -> None:
    client = SkysparkClient(
        base_url="http://skyspark.example/api",
        project="demo",
        username="user",
        password="password",  # noqa: S106
    )

    assert client.session_max_age_seconds == 900
