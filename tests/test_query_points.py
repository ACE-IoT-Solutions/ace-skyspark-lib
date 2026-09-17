"""Tests for point query filters."""

from unittest.mock import AsyncMock

import pytest
from structlog.testing import capture_logs

from ace_skyspark_lib.exceptions import ServerError
from ace_skyspark_lib.operations.query_ops import QueryOperations


@pytest.mark.asyncio
async def test_read_points_can_filter_to_historized_points() -> None:
    """read_points should include the his marker filter when requested."""
    session = AsyncMock()
    session.post_zinc.return_value = {"rows": []}
    query = QueryOperations(session)

    await query.read_points(site_ref="site-123", his_only=True)

    zinc = session.post_zinc.call_args.args[1]
    assert '"point and his and siteRef==@site-123"' in zinc


@pytest.mark.asyncio
async def test_read_points_defaults_to_all_points() -> None:
    """read_points should preserve existing default behavior."""
    session = AsyncMock()
    session.post_zinc.return_value = {"rows": []}
    query = QueryOperations(session)

    await query.read_points(site_ref="site-123")

    zinc = session.post_zinc.call_args.args[1]
    assert '"point and siteRef==@site-123"' in zinc


@pytest.mark.asyncio
async def test_read_by_filter_raises_sky_spark_error_grid() -> None:
    session = AsyncMock()
    session.post_zinc.return_value = {
        "meta": {
            "err": True,
            "dis": "Filter expression is too complex",
            "errType": "axon::ParseErr",
            "errTrace": "trace details",
        }
    }
    query = QueryOperations(session)

    with pytest.raises(ServerError, match="too complex") as exc_info:
        await query.read_by_filter("point and (id==@a or id==@b)")

    assert exc_info.value.error_type == "axon::ParseErr"
    assert exc_info.value.trace == "trace details"


@pytest.mark.asyncio
async def test_read_by_filter_bounds_logged_filter_preview() -> None:
    session = AsyncMock()
    session.post_zinc.return_value = {"rows": []}
    query = QueryOperations(session)
    filter_expr = "point and " + "x" * 600

    with capture_logs() as logs:
        await query.read_by_filter(filter_expr)

    read_log = next(entry for entry in logs if entry["event"] == "read_by_filter")
    assert read_log["filter"] == filter_expr[:500] + "..."
    assert read_log["filter_length"] == len(filter_expr)


@pytest.mark.asyncio
async def test_read_by_ids_uses_ordered_id_grid() -> None:
    session = AsyncMock()
    session.post_zinc.return_value = {"rows": [{"id": "r:a"}, {}, {"id": "r:b"}]}
    query = QueryOperations(session)

    rows = await query.read_by_ids(["a", "missing", "b"])

    session.post_zinc.assert_awaited_once_with("read", 'ver:"3.0"\nid\n@a\n@missing\n@b\n')
    assert rows == [{"id": "r:a"}, {}, {"id": "r:b"}]


@pytest.mark.asyncio
async def test_read_by_ids_raises_sky_spark_error_grid() -> None:
    session = AsyncMock()
    session.post_zinc.return_value = {
        "meta": {
            "err": True,
            "dis": "Invalid read grid",
            "errType": "sys::ParseErr",
            "trace": "trace details",
        }
    }
    query = QueryOperations(session)

    with pytest.raises(ServerError, match="Invalid read grid") as exc_info:
        await query.read_by_ids(["a"])

    assert exc_info.value.error_type == "sys::ParseErr"
    assert exc_info.value.trace == "trace details"


@pytest.mark.asyncio
async def test_read_by_id_uses_ordered_grid_and_returns_none_for_missing_id() -> None:
    session = AsyncMock()
    session.post_zinc.return_value = {"rows": [{}]}
    query = QueryOperations(session)

    result = await query.read_by_id("missing")

    session.post_zinc.assert_awaited_once_with("read", 'ver:"3.0"\nid\n@missing\n')
    assert result is None
