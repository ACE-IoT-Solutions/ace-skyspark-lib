"""Test Pydantic refactor of Site and Equipment models."""

from ace_skyspark_lib.models.entities import Equipment, Site


def test_site_serialization():
    """Test Site.model_dump() / to_zinc_dict()."""
    site = Site(
        id="p:demo:r:site123",
        dis="Test Building",
        ref_name="test_building",
        tz="America/New_York",
        geo_addr="123 Main St",
        area=50000.0,
        year_built=2020,
        tags={"custom": "value"},
    )

    # Test both methods work
    dict1 = site.to_zinc_dict()
    dict2 = site.model_dump(mode='python')

    assert dict1 == dict2
    assert dict1["id"] == "@p:demo:r:site123"
    assert dict1["dis"] == "Test Building"
    assert dict1["refName"] == "test_building"
    assert dict1["site"] == "m:"
    assert dict1["geoAddr"] == "123 Main St"
    assert dict1["area"] == 50000.0
    assert dict1["yearBuilt"] == 2020
    assert dict1["custom"] == "value"

    print("✓ Site serialization works!")
    print(f"  ID: {dict1['id']}")
    print(f"  Marker: site={dict1['site']}")
    print(f"  Custom tags: {dict1.get('custom')}")


def test_site_deserialization():
    """Test Site.model_validate()."""
    zinc_data = {
        "id": {"val": "p:demo:r:site456"},
        "dis": "Deserialization Test",
        "refName": "deser_test",
        "tz": "UTC",
        "site": "m:",
        "geoAddr": "456 Oak Ave",
    }

    site = Site.model_validate(zinc_data)

    assert site.id == "p:demo:r:site456"
    assert site.dis == "Deserialization Test"
    assert site.ref_name == "deser_test"
    assert site.geo_addr == "456 Oak Ave"

    print("\n✓ Site deserialization works!")
    print(f"  ID parsed: {site.id}")
    print(f"  Address: {site.geo_addr}")


def test_equipment_serialization():
    """Test Equipment.model_dump() / to_zinc_dict()."""
    equip = Equipment(
        id="p:demo:r:equip789",
        dis="Test AHU",
        ref_name="test_ahu",
        site_ref="p:demo:r:site123",
        equip_ref="p:demo:r:parent_equip",
        tz="America/Chicago",
        tags={"ahu": "m:", "hvac": "m:"},
    )

    dict1 = equip.to_zinc_dict()
    dict2 = equip.model_dump(mode='python')

    assert dict1 == dict2
    assert dict1["id"] == "@p:demo:r:equip789"
    assert dict1["siteRef"] == "@p:demo:r:site123"
    assert dict1["equipRef"] == "@p:demo:r:parent_equip"
    assert dict1["equip"] == "m:"
    assert dict1["ahu"] == "m:"
    assert dict1["hvac"] == "m:"

    print("\n✓ Equipment serialization works!")
    print(f"  ID: {dict1['id']}")
    print(f"  Refs: {dict1['siteRef']}, {dict1.get('equipRef')}")
    print(f"  Marker: equip={dict1['equip']}")


def test_equipment_deserialization():
    """Test Equipment.model_validate()."""
    zinc_data = {
        "id": "@p:demo:r:equip999",
        "dis": "Equipment Test",
        "refName": "equip_test",
        "siteRef": {"val": "p:demo:r:site456"},
        "tz": "UTC",
        "equip": "m:",
    }

    equip = Equipment.model_validate(zinc_data)

    assert equip.id == "p:demo:r:equip999"
    assert equip.dis == "Equipment Test"
    assert equip.site_ref == "p:demo:r:site456"
    assert equip.equip_ref is None

    print("\n✓ Equipment deserialization works!")
    print(f"  ID parsed: {equip.id}")
    print(f"  Site ref parsed: {equip.site_ref}")


if __name__ == "__main__":
    test_site_serialization()
    test_site_deserialization()
    test_equipment_serialization()
    test_equipment_deserialization()
    print("\n✅ All Site/Equipment refactor tests passed!")
