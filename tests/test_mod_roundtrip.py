"""Test that mod field can round-trip through read → update operations."""

import pytest
from ace_skyspark_lib.models.entities import Point
from ace_skyspark_lib.formats.zinc import ZincEncoder


def test_mod_field_roundtrip():
    """Test that mod field doesn't break update operations.

    This reproduces the bug where:
    1. SkySpark returns mod as datetime dict: {"val": "2025-10-30T...", "tz": "UTC"}
    2. Point.from_zinc_dict() stores it in kv_tags
    3. ZincEncoder can't encode the dict, causing update to fail
    """
    # Simulate data from SkySpark with mod field
    zinc_data = {
        "id": {"val": "p:demo:r:test123"},
        "dis": "Test Point",
        "refName": "test_point",
        "kind": "Number",
        "unit": "°F",
        "point": "m:",
        "siteRef": {"val": "p:demo:r:site1"},
        "equipRef": {"val": "p:demo:r:equip1"},
        "mod": {"val": "2025-10-30T18:30:00-04:00 New_York", "tz": "America/New_York"},  # This is the problem
        "sensor": "m:",
        "temp": "m:",
    }

    # Convert to Point model (this stores mod in kv_tags)
    point = Point.from_zinc_dict(zinc_data)

    # Debug: check what mod looks like after parsing
    print(f"\nAfter from_zinc_dict:")
    if 'mod' in point.kv_tags:
        mod_val = point.kv_tags['mod']
        print(f"  mod value: {mod_val}")
        print(f"  mod type: {type(mod_val)}")
        if hasattr(mod_val, 'tzinfo'):
            print(f"  mod tzinfo: {mod_val.tzinfo}")
            print(f"  mod tzname: {mod_val.tzinfo.tzname(mod_val) if mod_val.tzinfo else None}")

    # Modify the point
    point.marker_tags.append("critical")

    # Try to convert back to Zinc for update
    point_dict = point.to_zinc_dict()

    # Check if mod is in the dict
    print(f"\nAfter to_zinc_dict:")
    print(f"  mod in point_dict: {'mod' in point_dict}")
    print(f"  mod value: {point_dict.get('mod')}")

    # Try to encode for update operation - THIS IS WHERE IT FAILS
    try:
        zinc_grid = ZincEncoder.encode_commit_update_points([point])
        print("✓ Successfully encoded point update")
        print(f"Zinc grid:\n{zinc_grid}")
    except Exception as e:
        print(f"✗ Failed to encode: {e}")
        pytest.fail(f"Failed to encode point update: {e}")


if __name__ == "__main__":
    test_mod_field_roundtrip()
