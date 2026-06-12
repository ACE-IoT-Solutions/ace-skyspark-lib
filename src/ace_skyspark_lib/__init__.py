"""Modern async SkySpark client library with Pydantic validation."""

from ace_skyspark_lib.client import SkysparkClient
from ace_skyspark_lib.models.entities import Equipment, Point, Site
from ace_skyspark_lib.models.history import (
    HistoryReadResponse,
    HistorySample,
    HistoryWriteResult,
    TimeRange,
)

__version__ = "0.1.13"

__all__ = [
    "Equipment",
    "HistoryReadResponse",
    "HistorySample",
    "HistoryWriteResult",
    "Point",
    "Site",
    "SkysparkClient",
    "TimeRange",
]


def main() -> None:
    """CLI entry point."""
    print("ace-skyspark-lib v0.1.13")
    print("Modern async SkySpark client with Pydantic validation")
    print("\nUsage:")
    print("  from ace_skyspark_lib import SkysparkClient")
    print("  async with SkysparkClient(...) as client:")
    print("      sites = await client.read_sites()")
