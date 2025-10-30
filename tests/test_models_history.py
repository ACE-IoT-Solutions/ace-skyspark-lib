"""Tests for history models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ace_skyspark_lib.models.history import HistorySample, HistoryWriteResult, TimeRange


class TestHistorySample:
    """Test HistorySample model."""

    def test_create_sample_with_number_value(self) -> None:
        """Test creating sample with numeric value."""
        ts = datetime.now(timezone.utc)
        sample = HistorySample(
            pointId="point123",
            timestamp=ts,
            value=72.5,
        )
        assert sample.point_id == "point123"
        assert sample.timestamp == ts
        assert sample.value == 72.5

    def test_create_sample_with_bool_value(self) -> None:
        """Test creating sample with boolean value."""
        ts = datetime.now(timezone.utc)
        sample = HistorySample(
            pointId="point123",
            timestamp=ts,
            value=True,
        )
        assert sample.value is True

    def test_create_sample_with_string_value(self) -> None:
        """Test creating sample with string value."""
        ts = datetime.now(timezone.utc)
        sample = HistorySample(
            pointId="point123",
            timestamp=ts,
            value="online",
        )
        assert sample.value == "online"

    def test_sample_requires_timezone(self) -> None:
        """Test that timestamp must have timezone."""
        naive_dt = datetime(2024, 1, 1, 12, 0, 0)
        with pytest.raises(ValidationError, match="must include timezone"):
            HistorySample(
                pointId="point123",
                timestamp=naive_dt,
                value=72.5,
            )

    def test_sample_accepts_utc_timezone(self) -> None:
        """Test sample with UTC timezone."""
        ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        sample = HistorySample(
            pointId="point123",
            timestamp=ts,
            value=72.5,
        )
        assert sample.timestamp.tzinfo == timezone.utc

    def test_sample_accepts_named_timezone(self) -> None:
        """Test sample with named timezone."""
        import pytz

        tz = pytz.timezone("America/New_York")
        ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=tz)
        sample = HistorySample(
            pointId="point123",
            timestamp=ts,
            value=72.5,
        )
        assert sample.timestamp.tzinfo == tz

    def test_sample_to_zinc_row(self) -> None:
        """Test converting sample to Zinc row format."""
        ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        sample = HistorySample(
            pointId="point123",
            timestamp=ts,
            value=72.5,
        )
        row = sample.to_zinc_row()

        assert row["ts"] == "2024-01-01T12:00:00+00:00"
        assert row["val"] == 72.5

    def test_sample_to_zinc_row_with_bool(self) -> None:
        """Test Zinc row with boolean value."""
        ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        sample = HistorySample(
            pointId="point123",
            timestamp=ts,
            value=False,
        )
        row = sample.to_zinc_row()

        assert row["val"] is False

    def test_sample_alias_works(self) -> None:
        """Test that pointId alias works."""
        ts = datetime.now(timezone.utc)
        sample = HistorySample(
            point_id="point123",  # Using Python naming
            timestamp=ts,
            value=72.5,
        )
        assert sample.point_id == "point123"


class TestTimeRange:
    """Test TimeRange model."""

    def test_create_time_range(self) -> None:
        """Test creating time range."""
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 23, 59, 59, tzinfo=timezone.utc)
        time_range = TimeRange(start=start, end=end)

        assert time_range.start == start
        assert time_range.end == end

    def test_time_range_requires_timezone_on_start(self) -> None:
        """Test that start time must have timezone."""
        start = datetime(2024, 1, 1, 0, 0, 0)  # Naive
        end = datetime(2024, 1, 1, 23, 59, 59, tzinfo=timezone.utc)

        with pytest.raises(ValidationError, match="must include timezone"):
            TimeRange(start=start, end=end)

    def test_time_range_requires_timezone_on_end(self) -> None:
        """Test that end time must have timezone."""
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 23, 59, 59)  # Naive

        with pytest.raises(ValidationError, match="must include timezone"):
            TimeRange(start=start, end=end)

    def test_time_range_to_zinc_range(self) -> None:
        """Test converting to Zinc range format."""
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 23, 59, 59, tzinfo=timezone.utc)
        time_range = TimeRange(start=start, end=end)

        zinc_range = time_range.to_zinc_range()
        assert zinc_range == "2024-01-01T00:00:00+00:00,2024-01-01T23:59:59+00:00"

    def test_time_range_with_different_timezones(self) -> None:
        """Test time range with different timezones for start and end."""
        import pytz

        ny_tz = pytz.timezone("America/New_York")
        la_tz = pytz.timezone("America/Los_Angeles")

        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=ny_tz)
        end = datetime(2024, 1, 1, 23, 59, 59, tzinfo=la_tz)
        time_range = TimeRange(start=start, end=end)

        # Should preserve timezones
        assert time_range.start.tzinfo == ny_tz
        assert time_range.end.tzinfo == la_tz


class TestHistoryWriteResult:
    """Test HistoryWriteResult model."""

    def test_create_success_result(self) -> None:
        """Test creating successful write result."""
        result = HistoryWriteResult(
            success=True,
            samplesWritten=100,
        )
        assert result.success
        assert result.samples_written == 100
        assert result.error is None

    def test_create_failure_result(self) -> None:
        """Test creating failed write result."""
        result = HistoryWriteResult(
            success=False,
            samplesWritten=0,
            error="Connection timeout",
        )
        assert not result.success
        assert result.samples_written == 0
        assert result.error == "Connection timeout"

    def test_result_with_details(self) -> None:
        """Test result with additional details."""
        result = HistoryWriteResult(
            success=True,
            samplesWritten=100,
            details={"duration_ms": 1250, "chunks": 2},
        )
        assert result.details["duration_ms"] == 1250
        assert result.details["chunks"] == 2

    def test_result_defaults(self) -> None:
        """Test default values."""
        result = HistoryWriteResult(success=True)
        assert result.samples_written == 0
        assert result.error is None
        assert result.details == {}

    def test_result_alias_works(self) -> None:
        """Test that samplesWritten alias works."""
        result = HistoryWriteResult(
            success=True,
            samples_written=50,  # Using Python naming
        )
        assert result.samples_written == 50


class TestHistorySampleEdgeCases:
    """Test edge cases for HistorySample."""

    def test_sample_with_zero_value(self) -> None:
        """Test sample with zero value."""
        ts = datetime.now(timezone.utc)
        sample = HistorySample(
            pointId="point123",
            timestamp=ts,
            value=0.0,
        )
        assert sample.value == 0.0

    def test_sample_with_negative_value(self) -> None:
        """Test sample with negative value."""
        ts = datetime.now(timezone.utc)
        sample = HistorySample(
            pointId="point123",
            timestamp=ts,
            value=-25.5,
        )
        assert sample.value == -25.5

    def test_sample_with_empty_string_value(self) -> None:
        """Test sample with empty string value."""
        ts = datetime.now(timezone.utc)
        sample = HistorySample(
            pointId="point123",
            timestamp=ts,
            value="",
        )
        assert sample.value == ""

    def test_sample_with_very_large_number(self) -> None:
        """Test sample with very large number."""
        ts = datetime.now(timezone.utc)
        sample = HistorySample(
            pointId="point123",
            timestamp=ts,
            value=1e308,
        )
        assert sample.value == 1e308

    def test_sample_with_microseconds(self) -> None:
        """Test sample with microsecond precision."""
        ts = datetime(2024, 1, 1, 12, 0, 0, 123456, tzinfo=timezone.utc)
        sample = HistorySample(
            pointId="point123",
            timestamp=ts,
            value=72.5,
        )
        assert sample.timestamp.microsecond == 123456

    def test_multiple_samples_same_timestamp(self) -> None:
        """Test creating multiple samples with same timestamp (different points)."""
        ts = datetime.now(timezone.utc)

        sample1 = HistorySample(pointId="point1", timestamp=ts, value=72.5)
        sample2 = HistorySample(pointId="point2", timestamp=ts, value=68.3)

        assert sample1.timestamp == sample2.timestamp
        assert sample1.point_id != sample2.point_id


class TestTimeRangeEdgeCases:
    """Test edge cases for TimeRange."""

    def test_time_range_same_start_and_end(self) -> None:
        """Test time range where start equals end (single instant)."""
        ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        time_range = TimeRange(start=ts, end=ts)

        assert time_range.start == time_range.end

    def test_time_range_spanning_year(self) -> None:
        """Test time range spanning a full year."""
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        time_range = TimeRange(start=start, end=end)

        zinc_range = time_range.to_zinc_range()
        assert "2024-01-01" in zinc_range
        assert "2024-12-31" in zinc_range

    def test_time_range_very_short_duration(self) -> None:
        """Test time range with 1 second duration."""
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, 12, 0, 1, tzinfo=timezone.utc)
        time_range = TimeRange(start=start, end=end)

        assert (time_range.end - time_range.start).total_seconds() == 1
