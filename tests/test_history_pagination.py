"""Tests for paginated history reading."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta
from ace_skyspark_lib.operations.history_ops import HistoryOperations
from ace_skyspark_lib.models.history import HistoryReadResponse, HistorySample


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def history_ops(mock_session):
    return HistoryOperations(mock_session)


@pytest.mark.asyncio
async def test_read_history_single_page(history_ops, mock_session):
    """Test reading a single page of history."""
    point_id = "test_point"
    start = datetime.now(timezone.utc) - timedelta(hours=1)
    end = datetime.now(timezone.utc)
    
    # Mock response
    mock_session.get_json.return_value = {
        "page": 1,
        "pages": 1,
        "per_page": 100,
        "total": 2,
        "items": [
            {"pointId": point_id, "timestamp": start.isoformat(), "value": 70.0},
            {"pointId": point_id, "timestamp": end.isoformat(), "value": 71.0},
        ]
    }
    
    response = await history_ops.read_history(point_id, start, end)
    
    assert isinstance(response, HistoryReadResponse)
    assert response.page == 1
    assert response.total == 2
    assert len(response.items) == 2
    assert response.items[0].value == 70.0
    
    # Verify call params
    mock_session.get_json.assert_called_once()
    args, kwargs = mock_session.get_json.call_args
    assert args[0] == "timeseries"
    assert kwargs["params"]["id"] == f"@{point_id}"
    assert kwargs["params"]["page"] == 1


@pytest.mark.asyncio
async def test_read_history_all_multiple_pages(history_ops, mock_session):
    """Test reading all history across multiple pages."""
    point_id = "test_point"
    start = datetime.now(timezone.utc) - timedelta(hours=1)
    end = datetime.now(timezone.utc)
    
    # Mock sequence of responses for 3 pages
    mock_session.get_json.side_effect = [
        {
            "page": 1, "pages": 3, "per_page": 2, "total": 5,
            "items": [
                {"pointId": point_id, "timestamp": start.isoformat(), "value": 1.0},
                {"pointId": point_id, "timestamp": start.isoformat(), "value": 2.0},
            ]
        },
        {
            "page": 2, "pages": 3, "per_page": 2, "total": 5,
            "items": [
                {"pointId": point_id, "timestamp": start.isoformat(), "value": 3.0},
                {"pointId": point_id, "timestamp": start.isoformat(), "value": 4.0},
            ]
        },
        {
            "page": 3, "pages": 3, "per_page": 2, "total": 5,
            "items": [
                {"pointId": point_id, "timestamp": start.isoformat(), "value": 5.0},
            ]
        }
    ]
    
    samples = await history_ops.read_history_all(point_id, start, end, per_page=2)
    
    assert len(samples) == 5
    assert [s.value for s in samples] == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert mock_session.get_json.call_count == 3
