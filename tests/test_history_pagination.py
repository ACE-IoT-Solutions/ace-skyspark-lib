"""Tests for paginated history reading."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from structlog.testing import capture_logs

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
async def test_batch_his_write_skips_identified_bad_point_and_retries_bulk(
    history_ops: HistoryOperations, mock_session: AsyncMock
) -> None:
    timestamp = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    bad_point_id = "p:lcmcWestJefferson:r:2c7f6734-a60d5fce"
    samples = [
        HistorySample(pointId=bad_point_id, timestamp=timestamp, value=1.0),
        HistorySample(pointId="good-point", timestamp=timestamp, value=2.0),
        HistorySample(
            pointId=bad_point_id,
            timestamp=timestamp + timedelta(minutes=5),
            value=3.0,
        ),
    ]
    config_error = (
        "s:folio::HisConfigErr: Missing 'kind' tag "
        f'[@{bad_point_id} "Point missing kind"]'
    )
    mock_session.post_zinc.side_effect = [
        {"rows": [{"tz": "UTC"}, {"tz": "UTC"}]},
        {"meta": {"err": True, "dis": config_error}},
        {"text": 'ver:"3.0"\nempty\n'},
    ]

    result = await history_ops.write_samples(samples)

    assert result.success is True
    assert result.samples_written == 1
    assert result.error == config_error
    assert result.details == {
        "requests": 2,
        "timezones": ["UTC"],
        "rejected_point_ids": [bad_point_id],
        "rejected_samples": 2,
        "method": "batch_http",
        "preferred_method": "batch_http",
        "skipped_known_rejected_samples": 0,
        "session_rejected_point_ids": [bad_point_id],
    }
    calls = mock_session.post_zinc.call_args_list
    assert [call.args[0] for call in calls] == ["read", "hisWrite", "hisWrite"]
    assert f"@{bad_point_id}" in calls[1].args[1]
    assert "@good-point" in calls[1].args[1]
    assert f"@{bad_point_id}" not in calls[2].args[1]
    assert "@good-point" in calls[2].args[1]


@pytest.mark.asyncio
async def test_batch_his_write_keeps_rejected_point_out_of_later_chunks(
    history_ops: HistoryOperations, mock_session: AsyncMock
) -> None:
    start = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    samples = [
        HistorySample(pointId="bad-point", timestamp=start, value=1.0),
        HistorySample(pointId="good-a", timestamp=start, value=2.0),
        HistorySample(
            pointId="bad-point",
            timestamp=start + timedelta(minutes=5),
            value=3.0,
        ),
        HistorySample(
            pointId="good-b",
            timestamp=start + timedelta(minutes=5),
            value=4.0,
        ),
    ]
    error = "s:folio::HisConfigErr: Missing 'kind' tag [@bad-point]"
    mock_session.post_zinc.side_effect = [
        {"rows": [{"tz": "UTC"}, {"tz": "UTC"}, {"tz": "UTC"}]},
        {"text": f'ver:"3.0" err dis:"{error}" errType:"sys::Err"\nempty\n'},
        {"text": 'ver:"3.0"\nempty\n'},
        {"text": 'ver:"3.0"\nempty\n'},
    ]

    result = await history_ops.write_samples(samples, max_request_size=2)

    assert result.samples_written == 2
    assert result.details["rejected_point_ids"] == ["bad-point"]
    assert result.details["rejected_samples"] == 2
    write_grids = [call.args[1] for call in mock_session.post_zinc.call_args_list[1:]]
    assert "@bad-point" in write_grids[0]
    assert all("@bad-point" not in grid for grid in write_grids[1:])
    assert "@good-a" in write_grids[1]
    assert "@good-b" in write_grids[2]


def test_point_error_extraction_requires_safe_attribution() -> None:
    candidates = {"candidate"}

    assert HistoryOperations._point_ids_from_his_write_error(
        "s:folio::HisConfigErr [@candidate]",
        candidates,
    ) == {"candidate"}
    assert not HistoryOperations._point_ids_from_his_write_error(
        "s:folio::OtherErr [@candidate]",
        candidates,
    )
    assert not HistoryOperations._point_ids_from_his_write_error(
        "s:folio::HisConfigErr [@different-point]",
        candidates,
    )


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
async def test_partial_rpc_success_is_terminal_and_logs_failed_sample(
    history_ops: HistoryOperations, mock_session: AsyncMock
) -> None:
    timestamp = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    samples = [
        HistorySample(pointId="good-point", timestamp=timestamp, value=1.0),
        HistorySample(pointId="computed-point", timestamp=timestamp, value=2.0),
    ]
    computed_error = (
        'ver:"3.0" errType:"axon::EvalErr" err\n'
        "sys::ArgErr: Cannot write to computed history: Computed Point"
    )
    mock_session.post_zinc.side_effect = [
        {"rows": [{"tz": "UTC"}, {"tz": "UTC"}]},
        {"meta": {"err": True, "dis": "batch unsupported"}},
        {"text": f'ver:"3.0"\nempty\n\n{computed_error}'},
    ]

    with capture_logs() as logs:
        result = await history_ops.write_samples(samples)

    assert result.success is True
    assert result.samples_written == 1
    assert result.error is None
    assert result.details["method"] == "rpc"
    assert result.details["failed_point_ids"] == ["computed-point"]
    assert result.details["failed_samples"][0]["timestamp"] == timestamp.isoformat()
    assert result.details["fallback_errors"] == ["batch_http: batch unsupported"]
    assert [call.args[0] for call in mock_session.post_zinc.call_args_list] == [
        "read",
        "hisWrite",
        "evalAll",
    ]
    failed_logs = [log for log in logs if log["event"] == "write_samples_rpc_sample_failed"]
    assert len(failed_logs) == 1
    assert failed_logs[0]["point_id"] == "computed-point"
    assert "Cannot write to computed history" in str(failed_logs[0]["error"])


@pytest.mark.asyncio
async def test_partial_rpc_response_does_not_count_missing_grids_as_success(
    history_ops: HistoryOperations, mock_session: AsyncMock
) -> None:
    timestamp = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    samples = [
        HistorySample(pointId="confirmed-point", timestamp=timestamp, value=1.0),
        HistorySample(pointId="unreported-point", timestamp=timestamp, value=2.0),
    ]
    mock_session.post_zinc.side_effect = [
        {"rows": [{"tz": "UTC"}, {"tz": "UTC"}]},
        {"meta": {"err": True, "dis": "batch unsupported"}},
        {"text": 'ver:"3.0"\nempty\n'},
    ]

    result = await history_ops.write_samples(samples)

    assert result.success is True
    assert result.samples_written == 1
    assert result.details["method"] == "rpc"
    assert result.details["failed_point_ids"] == ["unreported-point"]
    assert result.details["failed_samples"][0]["error"] == (
        "Missing evalAll response grid"
    )
    assert result.details["response_grid_count"] == 1
    assert [call.args[0] for call in mock_session.post_zinc.call_args_list] == [
        "read",
        "hisWrite",
        "evalAll",
    ]


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
        {
            "text": (
                'ver:"3.0" errType:"test"\nempty\n\n'
                'ver:"3.0" errType:"test"\nempty\n'
            )
        },
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
    assert result.details["preferred_method"] == "auto"
    assert history_ops.preferred_write_method == "auto"

    mock_session.reset_mock()
    mock_session.post_zinc.side_effect = [
        {"rows": [{"tz": "UTC"}]},
        {"text": 'ver:"3.0"\nempty\n'},
    ]

    retry = await history_ops.write_samples([sample])

    assert retry.success is True
    assert retry.details["method"] == "batch_http"
    assert retry.details["preferred_method"] == "batch_http"
    assert [call.args[0] for call in mock_session.post_zinc.call_args_list] == [
        "read",
        "hisWrite",
    ]


@pytest.mark.asyncio
async def test_rejected_points_are_suppressed_for_later_writes(
    history_ops: HistoryOperations,
    mock_session: AsyncMock,
) -> None:
    timestamp = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    bad_point_id = "bad-point"
    samples = [
        HistorySample(pointId=bad_point_id, timestamp=timestamp, value=1.0),
        HistorySample(pointId="good-point", timestamp=timestamp, value=2.0),
    ]
    error = f"s:folio::HisConfigErr: Missing 'kind' tag [@{bad_point_id}]"
    mock_session.post_zinc.side_effect = [
        {"rows": [{"tz": "UTC"}, {"tz": "UTC"}]},
        {"meta": {"err": True, "dis": error}},
        {"text": 'ver:"3.0"\nempty\n'},
        {"rows": [{"tz": "UTC"}]},
        {"text": 'ver:"3.0"\nempty\n'},
    ]

    first = await history_ops.write_samples(samples)
    second = await history_ops.write_samples(samples)

    assert first.details["session_rejected_point_ids"] == [bad_point_id]
    assert second.samples_written == 1
    assert second.details["skipped_known_rejected_samples"] == 1
    assert second.details["method"] == "batch_http"
    second_read = mock_session.post_zinc.call_args_list[3].args[1]
    second_write = mock_session.post_zinc.call_args_list[4].args[1]
    assert f"@{bad_point_id}" not in second_read
    assert f"@{bad_point_id}" not in second_write


@pytest.mark.asyncio
async def test_successful_rpc_fallback_is_reused_without_retrying_batch(
    history_ops: HistoryOperations,
    mock_session: AsyncMock,
) -> None:
    sample = HistorySample(
        pointId="point",
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        value=1.0,
    )
    mock_session.post_zinc.side_effect = [
        {"rows": [{"tz": "UTC"}]},
        {"meta": {"err": True, "dis": "batch unsupported"}},
        {"text": 'ver:"3.0"\nempty\n'},
        {"text": 'ver:"3.0"\nempty\n'},
    ]

    first = await history_ops.write_samples([sample])
    second = await history_ops.write_samples([sample])

    assert first.details["method"] == "rpc"
    assert first.details["preferred_method"] == "rpc"
    assert second.details["method"] == "rpc"
    assert [call.args[0] for call in mock_session.post_zinc.call_args_list] == [
        "read",
        "hisWrite",
        "evalAll",
        "evalAll",
    ]


@pytest.mark.asyncio
async def test_batch_his_write_rejects_invalid_request_size(history_ops):
    sample = HistorySample(
        pointId="point",
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        value=1.0,
    )

    with pytest.raises(ValueError, match="max_request_size"):
        await history_ops.write_samples([sample], max_request_size=0)
