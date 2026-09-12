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


@pytest.mark.asyncio
async def test_batch_his_write_splits_different_point_timezones(history_ops, mock_session):
    """Each configured point timezone is sent in a separate hisWrite request."""
    timestamp = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    samples = [
        HistorySample(pointId="new-york", timestamp=timestamp, value=1.0),
        HistorySample(pointId="los-angeles", timestamp=timestamp, value=2.0),
    ]
    mock_session.post_zinc.side_effect = [
        {"rows": [{"tz": "New_York"}, {"tz": "Los_Angeles"}]},
        {"text": 'ver:"3.0"\nempty\n'},
        {"text": 'ver:"3.0"\nempty\n'},
    ]

    result = await history_ops.write_samples(samples)

    assert result.success is True
    assert result.samples_written == 2
    assert result.details["requests"] == 2
    assert [call.args[0] for call in mock_session.post_zinc.call_args_list] == [
        "read",
        "hisWrite",
        "hisWrite",
    ]
    new_york_grid = mock_session.post_zinc.call_args_list[1].args[1]
    los_angeles_grid = mock_session.post_zinc.call_args_list[2].args[1]
    assert "2024-01-01T07:00:00-05:00 New_York" in new_york_grid
    assert "2024-01-01T04:00:00-08:00 Los_Angeles" in los_angeles_grid


@pytest.mark.asyncio
async def test_batch_his_write_honors_max_request_size(history_ops, mock_session):
    """Same-timezone samples are grouped only up to the configured request size."""
    start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    samples = [
        HistorySample(pointId=f"point-{index}", timestamp=start, value=float(index))
        for index in range(3)
    ]
    mock_session.post_zinc.side_effect = [
        {"rows": [{"tz": "UTC"}, {"tz": "UTC"}, {"tz": "UTC"}]},
        {"text": 'ver:"3.0"\nempty\n'},
        {"text": 'ver:"3.0"\nempty\n'},
    ]

    result = await history_ops.write_samples(samples, max_request_size=2)

    assert result.samples_written == 3
    assert result.details["requests"] == 2
    first_grid = mock_session.post_zinc.call_args_list[1].args[1]
    second_grid = mock_session.post_zinc.call_args_list[2].args[1]
    assert "v0 id:@point-0,v1 id:@point-1" in first_grid
    assert "v0 id:@point-2" in second_grid


@pytest.mark.asyncio
async def test_batch_his_write_falls_back_to_rpc(history_ops, mock_session):
    sample = HistorySample(
        pointId="point",
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        value=1.0,
    )
    mock_session.post_zinc.side_effect = [
        {"rows": [{"tz": "UTC"}]},
        {"meta": {"err": True, "dis": "batch unsupported"}},
        {"text": 'ver:"3.0"\nempty\n'},
    ]

    result = await history_ops.write_samples([sample])

    assert result.success is True
    assert result.samples_written == 1
    assert result.details["method"] == "rpc"
    assert result.details["fallback_errors"] == ["batch_http: batch unsupported"]


@pytest.mark.asyncio
async def test_batch_and_rpc_failures_fall_back_to_single_point_grids(
    history_ops, mock_session
):
    timestamp = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    samples = [
        HistorySample(pointId="point-a", timestamp=timestamp, value=1.0),
        HistorySample(pointId="point-b", timestamp=timestamp, value=2.0),
    ]
    mock_session.post_zinc.side_effect = [
        {"rows": [{"tz": "UTC"}, {"tz": "UTC"}]},
        {"meta": {"err": True, "dis": "batch unsupported"}},
        {"text": 'ver:"3.0" errType:"test"\nempty\n'},
        {"rows": [{"tz": "UTC"}, {"tz": "UTC"}]},
        {"text": 'ver:"3.0"\nempty\n'},
        {"text": 'ver:"3.0"\nempty\n'},
    ]

    result = await history_ops.write_samples(samples)

    assert result.success is True
    assert result.samples_written == 2
    assert result.details["method"] == "single_http"
    assert len(result.details["fallback_errors"]) == 2
    calls = mock_session.post_zinc.call_args_list
    assert [call.args[0] for call in calls] == [
        "read",
        "hisWrite",
        "evalAll",
        "read",
        "hisWrite",
        "hisWrite",
    ]
    assert 'ver:"3.0" id:@point-a\nts,val' in calls[4].args[1]
    assert 'ver:"3.0" id:@point-b\nts,val' in calls[5].args[1]


@pytest.mark.asyncio
async def test_all_his_write_methods_fail(history_ops, mock_session):
    sample = HistorySample(
        pointId="missing",
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        value=1.0,
    )
    mock_session.post_zinc.side_effect = [
        {"rows": [{}]},
        {"meta": {"err": True, "dis": "rpc failed"}},
        {"rows": [{}]},
    ]

    result = await history_ops.write_samples([sample])

    assert result.success is False
    assert result.details["method"] == "single_http"
    assert len(result.details["fallback_errors"]) == 3
    assert "no configured timezone" in str(result.error)
    assert "rpc failed" in str(result.error)


@pytest.mark.asyncio
async def test_batch_his_write_rejects_invalid_request_size(history_ops):
    sample = HistorySample(
        pointId="point",
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        value=1.0,
    )

    with pytest.raises(ValueError, match="max_request_size"):
        await history_ops.write_samples([sample], max_request_size=0)
