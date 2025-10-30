"""Tests for entity models (Site, Equipment, Point)."""

import pytest
from pydantic import ValidationError

from ace_skyspark_lib.models.entities import Equipment, HaystackRef, Point, Site


class TestHaystackRef:
    """Test HaystackRef model."""

    def test_create_ref_with_id_only(self) -> None:
        """Test creating ref with just ID."""
        ref = HaystackRef(id="test123")
        assert ref.id == "test123"
        assert ref.dis is None
        assert str(ref) == "@test123"

    def test_create_ref_with_display_name(self) -> None:
        """Test creating ref with display name."""
        ref = HaystackRef(id="test123", dis="Test Display")
        assert ref.id == "test123"
        assert ref.dis == "Test Display"
        assert str(ref) == "@test123"


class TestSite:
    """Test Site entity model."""

    def test_create_minimal_site(self) -> None:
        """Test creating site with minimal required fields."""
        site = Site(dis="Building 1", refName="building1")
        assert site.dis == "Building 1"
        assert site.ref_name == "building1"
        assert site.tz == "UTC"  # Default
        assert site.id is None
        assert site.tags == {}

    def test_create_full_site(self) -> None:
        """Test creating site with all fields."""
        site = Site(
            id="site123",
            dis="Building 1",
            refName="building1",
            tz="America/New_York",
            geoAddr="123 Main St, City, ST 12345",
            area=50000.0,
            yearBuilt=2010,
            tags={"custom": "value"},
        )
        assert site.id == "site123"
        assert site.dis == "Building 1"
        assert site.ref_name == "building1"
        assert site.tz == "America/New_York"
        assert site.geo_addr == "123 Main St, City, ST 12345"
        assert site.area == 50000.0
        assert site.year_built == 2010
        assert site.tags == {"custom": "value"}

    def test_site_validates_timezone(self) -> None:
        """Test that invalid timezones are rejected."""
        with pytest.raises(ValidationError, match="Invalid timezone"):
            Site(dis="Building 1", refName="building1", tz="Invalid/Timezone")

    def test_site_accepts_valid_timezones(self) -> None:
        """Test various valid timezones."""
        timezones = ["UTC", "America/New_York", "Europe/London", "Asia/Tokyo"]
        for tz in timezones:
            site = Site(dis="Test", refName="test", tz=tz)
            assert site.tz == tz

    def test_site_to_zinc_dict_minimal(self) -> None:
        """Test Zinc dict conversion with minimal fields."""
        site = Site(dis="Building 1", refName="building1")
        zinc = site.to_zinc_dict()

        assert zinc["dis"] == "Building 1"
        assert zinc["refName"] == "building1"
        assert zinc["tz"] == "UTC"
        assert zinc["site"] == "m:"
        assert "id" not in zinc  # No ID yet

    def test_site_to_zinc_dict_with_id(self) -> None:
        """Test Zinc dict conversion with ID."""
        site = Site(id="site123", dis="Building 1", refName="building1")
        zinc = site.to_zinc_dict()

        assert zinc["id"] == "@site123"
        assert zinc["dis"] == "Building 1"
        assert zinc["site"] == "m:"

    def test_site_to_zinc_dict_full(self) -> None:
        """Test Zinc dict conversion with all fields."""
        site = Site(
            id="site123",
            dis="Building 1",
            refName="building1",
            tz="America/New_York",
            geoAddr="123 Main St",
            area=50000.0,
            yearBuilt=2010,
            tags={"custom": "value", "marker": "m:"},
        )
        zinc = site.to_zinc_dict()

        assert zinc["id"] == "@site123"
        assert zinc["geoAddr"] == "123 Main St"
        assert zinc["area"] == 50000.0
        assert zinc["yearBuilt"] == 2010
        assert zinc["custom"] == "value"
        assert zinc["marker"] == "m:"


class TestEquipment:
    """Test Equipment entity model."""

    def test_create_minimal_equipment(self) -> None:
        """Test creating equipment with minimal fields."""
        equip = Equipment(
            dis="AHU-1",
            refName="ahu1",
            siteRef="site123",
        )
        assert equip.dis == "AHU-1"
        assert equip.ref_name == "ahu1"
        assert equip.site_ref == "site123"
        assert equip.tz == "UTC"
        assert equip.equip_ref is None
        assert equip.id is None

    def test_create_equipment_with_parent_equip(self) -> None:
        """Test creating equipment with parent equipment reference."""
        equip = Equipment(
            dis="AHU-1 Fan",
            refName="ahu1_fan",
            siteRef="site123",
            equipRef="ahu1",
        )
        assert equip.equip_ref == "ahu1"

    def test_equipment_validates_timezone(self) -> None:
        """Test timezone validation."""
        with pytest.raises(ValidationError, match="Invalid timezone"):
            Equipment(
                dis="AHU-1",
                refName="ahu1",
                siteRef="site123",
                tz="Bad/Timezone",
            )

    def test_equipment_to_zinc_dict(self) -> None:
        """Test Zinc dict conversion."""
        equip = Equipment(
            id="equip123",
            dis="AHU-1",
            refName="ahu1",
            siteRef="site123",
            tz="America/New_York",
            tags={"ahu": "m:", "custom": "value"},
        )
        zinc = equip.to_zinc_dict()

        assert zinc["id"] == "@equip123"
        assert zinc["dis"] == "AHU-1"
        assert zinc["refName"] == "ahu1"
        assert zinc["siteRef"] == "@site123"
        assert zinc["tz"] == "America/New_York"
        assert zinc["equip"] == "m:"
        assert zinc["ahu"] == "m:"
        assert zinc["custom"] == "value"

    def test_equipment_to_zinc_dict_with_parent_equip(self) -> None:
        """Test Zinc dict with parent equipment ref."""
        equip = Equipment(
            id="fan123",
            dis="Fan",
            refName="fan",
            siteRef="site123",
            equipRef="ahu1",
        )
        zinc = equip.to_zinc_dict()

        assert zinc["equipRef"] == "@ahu1"


class TestPoint:
    """Test Point entity model."""

    def test_create_minimal_point(self) -> None:
        """Test creating point with minimal fields."""
        point = Point(
            dis="Zone Temp",
            refName="zone_temp",
            siteRef="site123",
            equipRef="ahu1",
            kind="Number",
            markerTags=["sensor"],
        )
        assert point.dis == "Zone Temp"
        assert point.ref_name == "zone_temp"
        assert point.site_ref == "site123"
        assert point.equip_ref == "ahu1"
        assert point.kind == "Number"
        assert point.marker_tags == ["sensor"]
        assert not point.his
        assert not point.cur
        assert not point.writable

    def test_create_historized_point(self) -> None:
        """Test creating historized point."""
        point = Point(
            dis="Zone Temp",
            refName="zone_temp",
            siteRef="site123",
            equipRef="ahu1",
            kind="Number",
            tz="America/New_York",
            unit="°F",
            his=True,
            cur=True,
            markerTags=["sensor"],
        )
        assert point.his
        assert point.cur
        assert point.unit == "°F"
        assert point.tz == "America/New_York"

    def test_point_validates_kind(self) -> None:
        """Test that invalid kinds are rejected."""
        with pytest.raises(ValidationError, match="Invalid kind"):
            Point(
                dis="Test",
                refName="test",
                siteRef="site123",
                equipRef="ahu1",
                kind="InvalidKind",
                markerTags=["sensor"],
            )

    def test_point_accepts_valid_kinds(self) -> None:
        """Test all valid kinds."""
        for kind in ["Bool", "Number", "Str"]:
            point = Point(
                dis="Test",
                refName="test",
                siteRef="site123",
                equipRef="ahu1",
                kind=kind,
                markerTags=["sensor"],
            )
            assert point.kind == kind

    def test_point_validates_timezone(self) -> None:
        """Test timezone validation."""
        with pytest.raises(ValidationError, match="Invalid timezone"):
            Point(
                dis="Test",
                refName="test",
                siteRef="site123",
                equipRef="ahu1",
                kind="Number",
                tz="Bad/Timezone",
                markerTags=["sensor"],
            )

    def test_point_requires_function_marker(self) -> None:
        """Test that point requires exactly one function marker."""
        with pytest.raises(
            ValidationError,
            match="Point must have one function marker",
        ):
            Point(
                dis="Test",
                refName="test",
                siteRef="site123",
                equipRef="ahu1",
                kind="Number",
                markerTags=[],  # No function marker
            )

    def test_point_rejects_multiple_function_markers(self) -> None:
        """Test that point rejects multiple function markers."""
        with pytest.raises(
            ValidationError,
            match="Point can only have one function marker",
        ):
            Point(
                dis="Test",
                refName="test",
                siteRef="site123",
                equipRef="ahu1",
                kind="Number",
                markerTags=["sensor", "cmd"],  # Two function markers
            )

    def test_point_accepts_each_function_marker(self) -> None:
        """Test each valid function marker."""
        for function in ["sensor", "cmd", "sp", "synthetic"]:
            point = Point(
                dis="Test",
                refName="test",
                siteRef="site123",
                equipRef="ahu1",
                kind="Number",
                markerTags=[function],
            )
            assert function in point.marker_tags

    def test_point_to_zinc_dict_minimal(self) -> None:
        """Test Zinc dict conversion with minimal fields."""
        point = Point(
            dis="Zone Temp",
            refName="zone_temp",
            siteRef="site123",
            equipRef="ahu1",
            kind="Number",
            markerTags=["sensor"],
        )
        zinc = point.to_zinc_dict()

        assert zinc["dis"] == "Zone Temp"
        assert zinc["refName"] == "zone_temp"
        assert zinc["siteRef"] == "@site123"
        assert zinc["equipRef"] == "@ahu1"
        assert zinc["kind"] == "Number"
        assert zinc["tz"] == "UTC"
        assert zinc["point"] == "m:"
        assert zinc["sensor"] == "m:"
        assert "id" not in zinc

    def test_point_to_zinc_dict_full(self) -> None:
        """Test Zinc dict conversion with all fields."""
        point = Point(
            id="point123",
            dis="Zone Temp",
            refName="zone_temp",
            siteRef="site123",
            equipRef="ahu1",
            kind="Number",
            tz="America/New_York",
            unit="°F",
            his=True,
            cur=True,
            writable=False,
            markerTags=["sensor", "temp"],
            kvTags={"minVal": 32, "maxVal": 120, "custom": "value"},
        )
        zinc = point.to_zinc_dict()

        assert zinc["id"] == "@point123"
        assert zinc["unit"] == "°F"
        assert zinc["his"] == "m:"
        assert zinc["cur"] == "m:"
        assert zinc["sensor"] == "m:"
        assert zinc["temp"] == "m:"
        assert zinc["minVal"] == 32
        assert zinc["maxVal"] == 120
        assert zinc["custom"] == "value"
        assert "writable" not in zinc  # False, so not included

    def test_point_from_zinc_dict_minimal(self) -> None:
        """Test creating point from Zinc dict."""
        zinc = {
            "id": {"val": "point123"},
            "dis": "Zone Temp",
            "refName": "zone_temp",
            "siteRef": {"val": "site123"},
            "equipRef": {"val": "ahu1"},
            "kind": "Number",
            "tz": "UTC",
            "point": "m:",
            "sensor": "m:",
        }
        point = Point.from_zinc_dict(zinc)

        assert point.id == "point123"
        assert point.dis == "Zone Temp"
        assert point.ref_name == "zone_temp"
        assert point.site_ref == "site123"
        assert point.equip_ref == "ahu1"
        assert point.kind == "Number"
        assert "sensor" in point.marker_tags

    def test_point_from_zinc_dict_with_string_refs(self) -> None:
        """Test creating point from Zinc dict with string refs."""
        zinc = {
            "id": "@point123",
            "dis": "Zone Temp",
            "refName": "zone_temp",
            "siteRef": "@site123",
            "equipRef": "@ahu1",
            "kind": "Number",
            "tz": "UTC",
            "point": "m:",
            "sensor": "m:",
        }
        point = Point.from_zinc_dict(zinc)

        assert point.id == "point123"
        assert point.site_ref == "site123"
        assert point.equip_ref == "ahu1"

    def test_point_from_zinc_dict_with_markers_and_kv_tags(self) -> None:
        """Test creating point with various tag types."""
        zinc = {
            "id": "@point123",
            "dis": "Zone Temp",
            "refName": "zone_temp",
            "siteRef": "@site123",
            "equipRef": "@ahu1",
            "kind": "Number",
            "tz": "America/New_York",
            "unit": "°F",
            "point": "m:",
            "his": "m:",
            "cur": "m:",
            "sensor": "m:",
            "temp": "m:",
            "minVal": 32,
            "maxVal": 120,
            "custom": "value",
        }
        point = Point.from_zinc_dict(zinc)

        assert point.his
        assert point.cur
        assert "sensor" in point.marker_tags
        assert "temp" in point.marker_tags
        assert point.kv_tags["minVal"] == 32
        assert point.kv_tags["maxVal"] == 120
        assert point.kv_tags["custom"] == "value"

    def test_point_from_zinc_dict_with_json_marker_format(self) -> None:
        """Test parsing JSON v4 marker format."""
        zinc = {
            "id": {"_kind": "ref", "val": "point123"},
            "dis": "Zone Temp",
            "refName": "zone_temp",
            "siteRef": {"_kind": "ref", "val": "site123"},
            "equipRef": {"_kind": "ref", "val": "ahu1"},
            "kind": "Number",
            "tz": "UTC",
            "point": {"_kind": "marker"},
            "sensor": {"_kind": "marker"},
        }
        point = Point.from_zinc_dict(zinc)

        assert point.id == "point123"
        assert "sensor" in point.marker_tags


class TestPointWritableFlag:
    """Test writable flag behavior in Point."""

    def test_writable_point_includes_marker(self) -> None:
        """Test that writable=True includes marker in Zinc."""
        point = Point(
            dis="Setpoint",
            refName="sp",
            siteRef="site123",
            equipRef="ahu1",
            kind="Number",
            writable=True,
            markerTags=["sp"],
        )
        zinc = point.to_zinc_dict()
        assert zinc["writable"] == "m:"

    def test_non_writable_point_excludes_marker(self) -> None:
        """Test that writable=False excludes marker from Zinc."""
        point = Point(
            dis="Sensor",
            refName="sensor",
            siteRef="site123",
            equipRef="ahu1",
            kind="Number",
            writable=False,
            markerTags=["sensor"],
        )
        zinc = point.to_zinc_dict()
        assert "writable" not in zinc


class TestPointMarkerAndKvTagsSeparation:
    """Test that marker tags and kv tags are properly separated."""

    def test_marker_tags_in_list(self) -> None:
        """Test marker tags are in the marker_tags list."""
        point = Point(
            dis="Test",
            refName="test",
            siteRef="site123",
            equipRef="ahu1",
            kind="Number",
            markerTags=["sensor", "temp", "zone"],
        )
        assert point.marker_tags == ["sensor", "temp", "zone"]
        assert point.kv_tags == {}

    def test_kv_tags_in_dict(self) -> None:
        """Test kv tags are in the kv_tags dict."""
        point = Point(
            dis="Test",
            refName="test",
            siteRef="site123",
            equipRef="ahu1",
            kind="Number",
            markerTags=["sensor"],
            kvTags={"minVal": 0, "maxVal": 100, "precision": 0.1},
        )
        assert point.kv_tags == {"minVal": 0, "maxVal": 100, "precision": 0.1}

    def test_mixed_tags_in_zinc_dict(self) -> None:
        """Test mixed marker and kv tags in Zinc output."""
        point = Point(
            dis="Test",
            refName="test",
            siteRef="site123",
            equipRef="ahu1",
            kind="Number",
            markerTags=["sensor", "temp"],
            kvTags={"minVal": 32, "unit": "°F"},
        )
        zinc = point.to_zinc_dict()

        # Marker tags should have "m:"
        assert zinc["sensor"] == "m:"
        assert zinc["temp"] == "m:"

        # KV tags should have values
        assert zinc["minVal"] == 32
        assert zinc["unit"] == "°F"
