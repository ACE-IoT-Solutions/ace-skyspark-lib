"""Regression tests for IANA timezone names in Zinc DateTime literals."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from ace_skyspark_lib.formats.zinc import ZincEncoder
from ace_skyspark_lib.models.history import HistorySample
from ace_skyspark_lib.operations.history_ops import HistoryOperations


def test_history_encoders_convert_iana_timezone_to_haystack_city_name() -> None:
    sample = HistorySample(
        pointId="point-a",
        timestamp=datetime(2026, 9, 10, 5, 45, tzinfo=ZoneInfo("America/Chicago")),
        value=1.0,
    )

    batch = ZincEncoder.encode_his_write_batch([sample], "America/Chicago")
    single = ZincEncoder.encode_his_write_single(
        "point-a",
        [sample],
        "America/Chicago",
    )

    expected_timestamp = "2026-09-10T05:45:00-05:00 Chicago"
    assert expected_timestamp in batch
    assert expected_timestamp in single
    assert " America/Chicago" not in batch
    assert " America/Chicago" not in single


def test_generic_datetime_encoders_normalize_iana_timezone() -> None:
    timestamp = datetime(2026, 9, 10, 5, 45, tzinfo=ZoneInfo("America/Chicago"))
    encoded_datetime = ZincEncoder._encode_value(timestamp)
    encoded_json_datetime = ZincEncoder._encode_value(
        {
            "_kind": "dateTime",
            "val": "2026-09-10T05:45:00-05:00",
            "tz": "America/Chicago",
        }
    )

    assert encoded_datetime == "2026-09-10T05:45:00-05:00 Chicago"
    assert encoded_json_datetime == "2026-09-10T05:45:00-05:00 Chicago"


@pytest.mark.asyncio
async def test_batch_his_write_normalizes_iana_point_timezone() -> None:
    """Configured IANA zones use Haystack city names in the outgoing grid."""
    session = AsyncMock()
    session.post_zinc.side_effect = [
        {"rows": [{"tz": "America/Chicago"}]},
        {"text": 'ver:"3.0"\nempty\n'},
    ]
    history = HistoryOperations(session)
    sample = HistorySample(
        pointId="chicago-point",
        timestamp=datetime(2026, 9, 10, 10, 45, tzinfo=UTC),
        value=1.0,
    )

    result = await history.write_samples([sample])

    assert result.success is True
    request_grid = session.post_zinc.call_args_list[1].args[1]
    assert "2026-09-10T05:45:00-05:00 Chicago" in request_grid
    assert " America/Chicago" not in request_grid
