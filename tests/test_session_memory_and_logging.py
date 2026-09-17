"""Regression tests for bounded response parsing and auth-safe logging."""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from ace_skyspark_lib.http.session import SessionManager


class _TokenProvider:
    async def get_token(self) -> str:
        return "secret-token"

    def invalidate(self) -> None:
        pass


@pytest.mark.asyncio
async def test_post_zinc_does_not_decode_text_before_json() -> None:
    response = Mock(spec=httpx.Response)
    response.raise_for_status.return_value = None
    response.json.return_value = {"rows": [{"id": "point-a"}]}
    type(response).text = property(
        lambda _response: (_ for _ in ()).throw(
            AssertionError("response.text must not be decoded for JSON")
        )
    )
    session = AsyncMock()
    session.post.return_value = response
    manager = SessionManager(
        session=session,
        base_url="https://sky.example/api",
        project="demo",
        token_provider=_TokenProvider(),
    )

    result = await manager.post_zinc("read", 'ver:"3.0"\nfilter\n"point"\n')

    assert result == {"rows": [{"id": "point-a"}]}


@pytest.mark.asyncio
async def test_post_zinc_preserves_text_fallback_for_non_json_response() -> None:
    response = httpx.Response(
        200,
        text='ver:"3.0"\nempty\n',
        request=httpx.Request("POST", "https://sky.example/api/demo/hisWrite"),
    )
    session = AsyncMock()
    session.post.return_value = response
    manager = SessionManager(
        session=session,
        base_url="https://sky.example/api",
        project="demo",
        token_provider=_TokenProvider(),
    )

    result = await manager.post_zinc("hisWrite", 'ver:"3.0"\nempty\n')

    assert result == {"text": 'ver:"3.0"\nempty\n'}


@pytest.mark.asyncio
async def test_post_zinc_logs_auth_presence_without_header_content() -> None:
    response = Mock(spec=httpx.Response)
    response.raise_for_status.return_value = None
    response.json.return_value = {"rows": []}
    session = AsyncMock()
    session.post.return_value = response
    manager = SessionManager(
        session=session,
        base_url="https://sky.example/api",
        project="demo",
        token_provider=_TokenProvider(),
    )

    with patch("ace_skyspark_lib.http.session.logger") as logger:
        await manager.post_zinc("read", 'ver:"3.0"\nfilter\n"point"\n')

    log_fields = logger.debug.call_args.kwargs
    assert log_fields["has_auth"] is True
    assert "auth_header" not in log_fields
    assert "secret-token" not in repr(logger.mock_calls)
