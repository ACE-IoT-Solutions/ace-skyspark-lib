"""Pydantic models for history operations."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class HistorySample(BaseModel):
    """Single history sample for a point."""

    point_id: str = Field(..., description="Point entity ID", alias="pointId")
    timestamp: datetime = Field(..., description="Sample timestamp with timezone")
    value: float | bool | str = Field(..., description="Sample value")

    model_config = {"populate_by_name": True}

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp_has_tz(cls, v: datetime) -> datetime:
        """Ensure timestamp has timezone info."""
        if v.tzinfo is None:
            msg = "Timestamp must include timezone information"
            raise ValueError(msg)
        return v

    def to_zinc_row(self) -> dict[str, Any]:
        """Convert to Zinc row format."""
        return {
            "ts": self.timestamp.isoformat(),
            "val": self.value,
        }


class TimeRange(BaseModel):
    """Time range for history queries."""

    start: datetime = Field(..., description="Start time (inclusive)")
    end: datetime = Field(..., description="End time (inclusive)")

    @field_validator("start", "end")
    @classmethod
    def validate_has_tz(cls, v: datetime) -> datetime:
        """Ensure datetime has timezone."""
        if v.tzinfo is None:
            msg = "Datetime must include timezone information"
            raise ValueError(msg)
        return v

    def to_zinc_range(self) -> str:
        """Convert to Zinc range format."""
        return f"{self.start.isoformat()},{self.end.isoformat()}"


class HistoryWriteResult(BaseModel):
    """Result of history write operation."""

    success: bool = Field(..., description="Operation succeeded")
    samples_written: int = Field(0, description="Number of samples written", alias="samplesWritten")
    error: str | None = Field(None, description="Error message if failed")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional details")

    model_config = {"populate_by_name": True}
