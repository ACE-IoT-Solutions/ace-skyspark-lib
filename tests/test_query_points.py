"""Tests for point query filters."""

from unittest.mock import AsyncMock

import pytest

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
