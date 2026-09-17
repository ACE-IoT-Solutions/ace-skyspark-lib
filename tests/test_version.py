"""Tests for synchronized package version metadata."""

from importlib.metadata import version

from ace_skyspark_lib import __version__


def test_runtime_version_matches_distribution_metadata() -> None:
    """Keep the runtime version synchronized with the built distribution."""
    assert __version__ == version("ace-skyspark-lib")
