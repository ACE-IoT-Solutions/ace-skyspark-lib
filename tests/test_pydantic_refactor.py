"""Test Pydantic refactor of Point model."""

from datetime import datetime

import pytz
from ace_skyspark_lib.models.entities import Point


def test_point_deserialization():
    """Test Point.model_validate() / from_zinc_dict()."""
    zinc_data = {
        "id": {"val": "p:demo:r:test123"},
        "dis": "Test Point",
        "refName": "test_point",
        "kind": "Number",
        "unit": "°F",
        "siteRef": {"val": "p:demo:r:site1"},
        "equipRef": {"val": "p:demo:r:equip1"},
        "tz": "UTC",
        "point": "m:",
        "his": "m:",
        "sensor": "m:",
        "temp": "m:",
        "mod": {"val": "2025-10-30T18:30:00-04:00 America/New_York", "tz": "America/New_York"},
    }

    # Test both methods work
    point1 = Point.from_zinc_dict(zinc_data)
    point2 = Point.model_validate(zinc_data)

    # They should be equivalent
    assert point1.id == point2.id == "p:demo:r:test123"
    assert point1.dis == point2.dis == "Test Point"
    assert point1.site_ref == point2.site_ref == "p:demo:r:site1"
    assert point1.equip_ref == point2.equip_ref == "p:demo:r:equip1"
    assert point1.his == point2.his == True
    assert "sensor" in point1.marker_tags
    assert "temp" in point1.marker_tags
    assert "mod" in point1.kv_tags
    assert isinstance(point1.kv_tags["mod"], datetime)
    assert point1.kv_tags["mod"].tzinfo is not None

    print("✓ Deserialization works!")
    print(f"  ID: {point1.id}")
    print(f"  Refs parsed: {point1.site_ref}, {point1.equip_ref}")
    print(f"  Markers: {point1.marker_tags}")
    print(f"  mod field: {point1.kv_tags.get('mod')}")
    print(f"  mod timezone: {point1.kv_tags['mod'].tzinfo}")


def test_point_serialization():
    """Test Point.model_dump() / to_zinc_dict()."""
    point = Point(
        id="p:demo:r:test456",
        dis="Serialization Test",
        ref_name="ser_test",
        site_ref="p:demo:r:site2",
        equip_ref="p:demo:r:equip2",
        kind="Number",
        unit="°F",
        his=True,
        marker_tags=["sensor", "temp", "zone"],  # sensor is function marker, temp/zone are regular markers
    )

    # Test both methods work
    dict1 = point.to_zinc_dict()
    dict2 = point.model_dump(mode='python')

    # They should be equivalent
    assert dict1 == dict2
    assert dict1["id"] == "@p:demo:r:test456"
    assert dict1["siteRef"] == "@p:demo:r:site2"
    assert dict1["point"] == "m:"
    assert dict1["his"] == "m:"
    assert dict1["sensor"] == "m:"
    assert dict1["temp"] == "m:"
    assert dict1["zone"] == "m:"

    print("\n✓ Serialization works!")
    print(f"  ID: {dict1['id']}")
    print(f"  Refs formatted: {dict1['siteRef']}, {dict1['equipRef']}")
    print(f"  Markers added: point={dict1['point']}, his={dict1['his']}")
    print(f"  Tags: sensor={dict1.get('sensor')}, temp={dict1.get('temp')}, zone={dict1.get('zone')}")


def test_round_trip():
    """Test full round-trip: Zinc → Point → Zinc."""
    original_zinc = {
        "id": "p:demo:r:round789",
        "dis": "Round Trip Test",
        "refName": "round_test",
        "kind": "Number",
        "siteRef": "@p:demo:r:site3",
        "equipRef": "@p:demo:r:equip3",
        "tz": "America/New_York",
        "point": "m:",
        "sensor": "m:",
        "occupied": "m:",
        "zone": "m:",
    }

    # Parse
    point = Point.model_validate(original_zinc)

    # Modify
    point.marker_tags.append("critical")

    # Serialize
    result_zinc = point.model_dump(mode='python')

    # Check
    assert result_zinc["id"] == "@p:demo:r:round789"
    assert result_zinc["point"] == "m:"
    assert result_zinc["sensor"] == "m:"
    assert result_zinc["occupied"] == "m:"
    assert result_zinc["zone"] == "m:"
    assert result_zinc["critical"] == "m:"  # New tag added

    print("\n✓ Round-trip works!")
    print(f"  Original markers: sensor, occupied, zone")
    print(f"  Added: critical")
    print(f"  Result has all 4 markers: {[k for k, v in result_zinc.items() if v == 'm:' and k != 'point']}")


if __name__ == "__main__":
    test_point_deserialization()
    test_point_serialization()
    test_round_trip()
    print("\n✅ All Pydantic refactor tests passed!")
