"""Tests for Zinc encoder."""

from datetime import datetime, timezone

import pytest

from ace_skyspark_lib.formats.zinc import ZincEncoder
from ace_skyspark_lib.models.entities import Equipment, Point, Site
from ace_skyspark_lib.models.history import HistorySample


class TestZincEncoderSites:
    """Test Zinc encoding for sites."""

    def test_encode_single_site(self) -> None:
        """Test encoding single site."""
        site = Site(dis="Building 1", refName="building1", tz="UTC")
        zinc = ZincEncoder.encode_commit_add_sites([site])

        assert 'ver:"3.0" commit:"add"' in zinc
        assert "dis" in zinc
        assert "refName" in zinc
        assert "tz" in zinc
        assert "site" in zinc
        assert '"Building 1"' in zinc
        assert '"building1"' in zinc
        assert '"UTC"' in zinc

    def test_encode_multiple_sites(self) -> None:
        """Test encoding multiple sites."""
        sites = [
            Site(dis="Building 1", refName="building1", tz="UTC"),
            Site(dis="Building 2", refName="building2", tz="America/New_York"),
        ]
        zinc = ZincEncoder.encode_commit_add_sites(sites)

        assert '"Building 1"' in zinc
        assert '"Building 2"' in zinc
        assert '"building1"' in zinc
        assert '"building2"' in zinc
        assert zinc.count("\n") >= 3  # Header + 2 data rows

    def test_encode_site_with_optional_fields(self) -> None:
        """Test encoding site with optional fields."""
        site = Site(
            dis="Building 1",
            refName="building1",
            tz="UTC",
            geoAddr="123 Main St",
            area=50000.0,
            yearBuilt=2010,
        )
        zinc = ZincEncoder.encode_commit_add_sites([site])

        assert "geoAddr" in zinc
        assert "area" in zinc
        assert "yearBuilt" in zinc
        assert "50000" in zinc
        assert "2010" in zinc

    def test_encode_site_with_custom_tags(self) -> None:
        """Test encoding site with custom tags."""
        site = Site(
            dis="Building 1",
            refName="building1",
            tags={"custom": "value", "marker": "m:"},
        )
        zinc = ZincEncoder.encode_commit_add_sites([site])

        assert "custom" in zinc
        assert "marker" in zinc

    def test_encode_empty_site_list(self) -> None:
        """Test encoding empty site list."""
        zinc = ZincEncoder.encode_commit_add_sites([])
        assert zinc == ""

    def test_site_encoding_excludes_id(self) -> None:
        """Test that ID is not included in add operations."""
        site = Site(id="site123", dis="Building 1", refName="building1")
        zinc = ZincEncoder.encode_commit_add_sites([site])

        # ID should not appear in add operations
        assert "@site123" not in zinc


class TestZincEncoderEquipment:
    """Test Zinc encoding for equipment."""

    def test_encode_single_equipment(self) -> None:
        """Test encoding single equipment."""
        equip = Equipment(
            dis="AHU-1",
            refName="ahu1",
            siteRef="site123",
            tz="UTC",
        )
        zinc = ZincEncoder.encode_commit_add_equipment([equip])

        assert 'ver:"3.0" commit:"add"' in zinc
        assert '"AHU-1"' in zinc
        assert '"ahu1"' in zinc
        assert "@site123" in zinc

    def test_encode_equipment_with_parent_equip(self) -> None:
        """Test encoding equipment with parent equipment."""
        equip = Equipment(
            dis="Fan",
            refName="fan",
            siteRef="site123",
            equipRef="ahu1",
        )
        zinc = ZincEncoder.encode_commit_add_equipment([equip])

        assert "equipRef" in zinc
        assert "@ahu1" in zinc

    def test_encode_multiple_equipment(self) -> None:
        """Test encoding multiple equipment."""
        equipment = [
            Equipment(dis="AHU-1", refName="ahu1", siteRef="site123"),
            Equipment(dis="AHU-2", refName="ahu2", siteRef="site123"),
        ]
        zinc = ZincEncoder.encode_commit_add_equipment(equipment)

        assert '"AHU-1"' in zinc
        assert '"AHU-2"' in zinc

    def test_encode_empty_equipment_list(self) -> None:
        """Test encoding empty equipment list."""
        zinc = ZincEncoder.encode_commit_add_equipment([])
        assert zinc == ""


class TestZincEncoderPoints:
    """Test Zinc encoding for points."""

    def test_encode_single_point(self) -> None:
        """Test encoding single point."""
        point = Point(
            dis="Zone Temp",
            refName="zone_temp",
            siteRef="site123",
            equipRef="ahu1",
            kind="Number",
            tz="UTC",
            markerTags=["sensor"],
        )
        zinc = ZincEncoder.encode_commit_add_points([point])

        assert 'ver:"3.0" commit:"add"' in zinc
        assert '"Zone Temp"' in zinc
        assert '"zone_temp"' in zinc
        assert "@site123" in zinc
        assert "@ahu1" in zinc
        assert '"Number"' in zinc

    def test_encode_point_with_unit(self) -> None:
        """Test encoding point with unit."""
        point = Point(
            dis="Zone Temp",
            refName="zone_temp",
            siteRef="site123",
            equipRef="ahu1",
            kind="Number",
            unit="°F",
            markerTags=["sensor"],
        )
        zinc = ZincEncoder.encode_commit_add_points([point])

        assert "unit" in zinc
        assert "°F" in zinc

    def test_encode_historized_point(self) -> None:
        """Test encoding historized point."""
        point = Point(
            dis="Zone Temp",
            refName="zone_temp",
            siteRef="site123",
            equipRef="ahu1",
            kind="Number",
            his=True,
            cur=True,
            markerTags=["sensor"],
        )
        zinc = ZincEncoder.encode_commit_add_points([point])

        assert "his" in zinc
        assert "cur" in zinc

    def test_encode_point_with_marker_tags(self) -> None:
        """Test encoding point with multiple marker tags."""
        point = Point(
            dis="Zone Temp",
            refName="zone_temp",
            siteRef="site123",
            equipRef="ahu1",
            kind="Number",
            markerTags=["sensor", "temp", "zone"],
        )
        zinc = ZincEncoder.encode_commit_add_points([point])

        # All marker tags should appear in header
        assert "sensor" in zinc
        assert "temp" in zinc
        assert "zone" in zinc

    def test_encode_point_with_kv_tags(self) -> None:
        """Test encoding point with kv tags."""
        point = Point(
            dis="Zone Temp",
            refName="zone_temp",
            siteRef="site123",
            equipRef="ahu1",
            kind="Number",
            markerTags=["sensor"],
            kvTags={"minVal": 32, "maxVal": 120},
        )
        zinc = ZincEncoder.encode_commit_add_points([point])

        assert "minVal" in zinc
        assert "maxVal" in zinc

    def test_encode_multiple_points(self) -> None:
        """Test encoding multiple points."""
        points = [
            Point(
                dis="Temp 1",
                refName="temp1",
                siteRef="site123",
                equipRef="ahu1",
                kind="Number",
                markerTags=["sensor"],
            ),
            Point(
                dis="Temp 2",
                refName="temp2",
                siteRef="site123",
                equipRef="ahu1",
                kind="Number",
                markerTags=["sensor"],
            ),
        ]
        zinc = ZincEncoder.encode_commit_add_points(points)

        assert '"Temp 1"' in zinc
        assert '"Temp 2"' in zinc

    def test_encode_empty_point_list(self) -> None:
        """Test encoding empty point list."""
        zinc = ZincEncoder.encode_commit_add_points([])
        assert zinc == ""


class TestZincEncoderPointUpdates:
    """Test Zinc encoding for point updates."""

    def test_encode_point_update(self) -> None:
        """Test encoding point update operation."""
        point = Point(
            id="point123",
            dis="Zone Temp",
            refName="zone_temp",
            siteRef="site123",
            equipRef="ahu1",
            kind="Number",
            markerTags=["sensor"],
        )
        zinc = ZincEncoder.encode_commit_update_points([point])

        assert 'ver:"3.0" commit:"update"' in zinc
        assert "@point123" in zinc

    def test_update_requires_id(self) -> None:
        """Test that update operation requires ID."""
        point = Point(
            dis="Zone Temp",
            refName="zone_temp",
            siteRef="site123",
            equipRef="ahu1",
            kind="Number",
            markerTags=["sensor"],
        )

        with pytest.raises(ValueError, match="must have an ID"):
            ZincEncoder.encode_commit_update_points([point])

    def test_encode_multiple_point_updates(self) -> None:
        """Test encoding multiple point updates."""
        points = [
            Point(
                id="point1",
                dis="Temp 1",
                refName="temp1",
                siteRef="site123",
                equipRef="ahu1",
                kind="Number",
                markerTags=["sensor"],
            ),
            Point(
                id="point2",
                dis="Temp 2",
                refName="temp2",
                siteRef="site123",
                equipRef="ahu1",
                kind="Number",
                markerTags=["sensor"],
            ),
        ]
        zinc = ZincEncoder.encode_commit_update_points(points)

        assert "@point1" in zinc
        assert "@point2" in zinc


class TestZincEncoderHistoryRPC:
    """Test Zinc encoding for history RPC operations."""

    def test_encode_single_history_sample(self) -> None:
        """Test encoding single history sample for RPC."""
        ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        sample = HistorySample(
            pointId="point123",
            timestamp=ts,
            value=72.5,
        )
        zinc = ZincEncoder.encode_his_write_rpc([sample])

        assert 'ver:"3.0"' in zinc
        assert "expr" in zinc
        assert "hisWrite" in zinc
        assert "@point123" in zinc
        assert "72.5" in zinc

    def test_encode_history_with_bool_value(self) -> None:
        """Test encoding history sample with boolean value."""
        ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        sample = HistorySample(
            pointId="point123",
            timestamp=ts,
            value=True,
        )
        zinc = ZincEncoder.encode_his_write_rpc([sample])

        assert "true" in zinc

    def test_encode_history_with_string_value(self) -> None:
        """Test encoding history sample with string value."""
        ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        sample = HistorySample(
            pointId="point123",
            timestamp=ts,
            value="online",
        )
        zinc = ZincEncoder.encode_his_write_rpc([sample])

        assert '"online"' in zinc

    def test_encode_multiple_history_samples(self) -> None:
        """Test encoding multiple history samples."""
        ts1 = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ts2 = datetime(2024, 1, 1, 12, 15, 0, tzinfo=timezone.utc)

        samples = [
            HistorySample(pointId="point123", timestamp=ts1, value=72.5),
            HistorySample(pointId="point123", timestamp=ts2, value=73.2),
        ]
        zinc = ZincEncoder.encode_his_write_rpc(samples)

        assert zinc.count("hisWrite") == 2
        assert "72.5" in zinc
        assert "73.2" in zinc

    def test_encode_history_preserves_timezone(self) -> None:
        """Test that timezone is preserved in encoding."""
        import pytz

        tz = pytz.timezone("America/New_York")
        ts = datetime(2024, 6, 1, 12, 0, 0, tzinfo=tz)  # Summer date for EDT
        sample = HistorySample(
            pointId="point123",
            timestamp=ts,
            value=72.5,
        )
        zinc = ZincEncoder.encode_his_write_rpc([sample])

        # Should contain timezone name in the parseDateTime call
        # The timezone name appears after the datetime string
        assert "parseDateTime" in zinc
        assert "2024-06-01" in zinc
        # Verify timezone info is present (any abbreviation)
        assert '", \\"' in zinc  # Pattern: datetime", \"YYYY-MM-DD\", \"TZ\"

    def test_encode_empty_history_list(self) -> None:
        """Test encoding empty history list."""
        zinc = ZincEncoder.encode_his_write_rpc([])
        assert zinc == ""


class TestZincEncoderReadOperations:
    """Test Zinc encoding for read operations."""

    def test_encode_read_by_filter(self) -> None:
        """Test encoding read by filter operation."""
        zinc = ZincEncoder.encode_read_by_filter("point and siteRef==@site123")

        assert 'ver:"3.0"' in zinc
        assert "filter" in zinc
        assert '"point and siteRef==@site123"' in zinc

    def test_encode_simple_filter(self) -> None:
        """Test encoding simple filter."""
        zinc = ZincEncoder.encode_read_by_filter("site")

        assert '"site"' in zinc

    def test_encode_complex_filter(self) -> None:
        """Test encoding complex filter expression."""
        filter_expr = "point and his and siteRef==@site123 and equipRef==@ahu1"
        zinc = ZincEncoder.encode_read_by_filter(filter_expr)

        assert filter_expr in zinc


class TestZincEncoderValueEncoding:
    """Test Zinc value encoding edge cases."""

    def test_encode_marker_value(self) -> None:
        """Test encoding marker value."""
        encoded = ZincEncoder._encode_value("m:")
        assert encoded == "M"

    def test_encode_ref_value(self) -> None:
        """Test encoding ref value."""
        encoded = ZincEncoder._encode_value("@site123")
        assert encoded == "@site123"

    def test_encode_string_value(self) -> None:
        """Test encoding string value."""
        encoded = ZincEncoder._encode_value("test string")
        assert encoded == '"test string"'

    def test_encode_bool_true(self) -> None:
        """Test encoding boolean true."""
        encoded = ZincEncoder._encode_value(True)
        assert encoded == "T"

    def test_encode_bool_false(self) -> None:
        """Test encoding boolean false."""
        encoded = ZincEncoder._encode_value(False)
        assert encoded == "F"

    def test_encode_integer(self) -> None:
        """Test encoding integer."""
        encoded = ZincEncoder._encode_value(42)
        assert encoded == "42"

    def test_encode_float(self) -> None:
        """Test encoding float."""
        encoded = ZincEncoder._encode_value(72.5)
        assert encoded == "72.5"

    def test_encode_empty_string(self) -> None:
        """Test encoding empty string."""
        encoded = ZincEncoder._encode_value("")
        assert encoded == ""

    def test_encode_datetime(self) -> None:
        """Test encoding datetime."""
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        encoded = ZincEncoder._encode_value(dt)
        assert "2024-01-01" in encoded
        assert "12:00:00" in encoded


class TestZincEncoderGridStructure:
    """Test Zinc grid structure and formatting."""

    def test_site_grid_has_correct_structure(self) -> None:
        """Test that site grid has correct structure."""
        site = Site(dis="Building 1", refName="building1")
        zinc = ZincEncoder.encode_commit_add_sites([site])

        lines = zinc.strip().split("\n")
        assert len(lines) >= 3  # Header line, column headers, data row
        assert lines[0].startswith('ver:"3.0"')
        assert "commit:" in lines[0]

    def test_point_grid_columns_sorted(self) -> None:
        """Test that grid columns are sorted alphabetically."""
        point = Point(
            dis="Test",
            refName="test",
            siteRef="site123",
            equipRef="equip123",
            kind="Number",
            markerTags=["sensor"],
        )
        zinc = ZincEncoder.encode_commit_add_points([point])

        lines = zinc.strip().split("\n")
        column_line = lines[1]

        # Check that columns appear in alphabetical order
        columns = column_line.split(", ")
        sorted_columns = sorted(columns)
        assert columns == sorted_columns

    def test_grid_handles_special_characters(self) -> None:
        """Test that grid handles special characters in strings."""
        site = Site(
            dis='Building "Main"',
            refName="building_main",
            geoAddr="123 Main St, Suite #100",
        )
        zinc = ZincEncoder.encode_commit_add_sites([site])

        # Special characters should be in quotes
        assert "Building" in zinc
        assert "Main" in zinc
        assert "Suite" in zinc

    def test_multiple_entities_same_tags(self) -> None:
        """Test encoding multiple entities with same tag structure."""
        sites = [
            Site(dis=f"Building {i}", refName=f"building{i}")
            for i in range(5)
        ]
        zinc = ZincEncoder.encode_commit_add_sites(sites)

        # Should have one header and 5 data rows
        lines = zinc.strip().split("\n")
        assert len(lines) == 7  # ver line, column line, 5 data rows

    def test_multiple_entities_different_tags(self) -> None:
        """Test encoding entities with different tag sets."""
        sites = [
            Site(dis="Building 1", refName="b1", area=1000.0),
            Site(dis="Building 2", refName="b2", yearBuilt=2020),
            Site(dis="Building 3", refName="b3"),
        ]
        zinc = ZincEncoder.encode_commit_add_sites(sites)

        # All unique tags should be in header
        assert "area" in zinc
        assert "yearBuilt" in zinc

        # Data rows should have empty values where tags don't apply
        lines = zinc.strip().split("\n")
        assert len(lines) == 5  # ver, columns, 3 data rows
