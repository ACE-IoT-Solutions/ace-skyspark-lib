"""Idempotent integration test that doesn't create duplicates."""

import os
from datetime import UTC, datetime, timedelta

from dotenv import load_dotenv

from ace_skyspark_lib import (
    Equipment,
    HistorySample,
    Point,
    Site,
    SkysparkClient,
)

load_dotenv()

TEST_URL = os.getenv("TEST_SKYSPARK_URL")
TEST_USER = os.getenv("TEST_SKYSPARK_USER")
TEST_PASS = os.getenv("TEST_SKYSPARK_PASS")


async def test_idempotent_roundtrip() -> None:
    """Test that finds/creates entities once and can be run multiple times."""
    base_url = TEST_URL.rstrip("/")
    if not base_url.endswith("/api"):
        base_url = f"{base_url}/api"

    print(f"\n{'=' * 60}")
    print(f"Idempotent Round-Trip Test")
    print(f"{'=' * 60}")
    print(f"URL: {base_url}")
    print(f"Project: aceTest")
    print(f"{'=' * 60}\n")

    async with SkysparkClient(
        base_url=base_url,
        project="aceTest",
        username=TEST_USER,
        password=TEST_PASS,
        timeout=30.0,
    ) as client:
        # Use unique refNames that we'll reuse across test runs
        site_refname = "ace_test_site_001"
        equip_refname = "ace_test_ahu_001"
        temp_point_refname = "ace_test_temp_001"
        status_point_refname = "ace_test_status_001"

        # Step 1: Find or create site
        print("📍 Step 1: Finding or creating site...")

        # Fetch all sites and filter by refName in Python (Zinc filter syntax issues)
        all_sites = await client.read("site")
        existing_sites = [s for s in all_sites if s.get("refName") == site_refname]

        if existing_sites:
            site_dict = existing_sites[0]
            site_id = site_dict["id"]["val"] if isinstance(site_dict["id"], dict) else site_dict["id"]
            print(f"   ✓ Found existing site: {site_id}")
            print(f"     - Display: {site_dict.get('dis')}")
            print(f"     - refName: {site_dict.get('refName')}")
        else:
            # Create new site
            test_site = Site(
                dis="ACE Test Building",
                tz="America/New_York",
                refName=site_refname,
                area_sqft=5000.0,
                marker_tags=["office", "test"],
            )
            created_sites = await client.create_sites([test_site])
            site_dict = created_sites[0]
            site_id = site_dict["id"]["val"] if isinstance(site_dict["id"], dict) else site_dict["id"]
            print(f"   ✓ Created new site: {site_id}")
            print(f"     - Display: {site_dict.get('dis')}")

        # Step 2: Find or create equipment
        print("\n🔧 Step 2: Finding or creating equipment...")

        # Fetch all equipment and filter by refName
        all_equips = await client.read("equip")
        existing_equips = [e for e in all_equips if e.get("refName") == equip_refname]

        if existing_equips:
            equip_dict = existing_equips[0]
            equip_id = equip_dict["id"]["val"] if isinstance(equip_dict["id"], dict) else equip_dict["id"]
            print(f"   ✓ Found existing equipment: {equip_id}")
            print(f"     - Display: {equip_dict.get('dis')}")
            print(f"     - refName: {equip_dict.get('refName')}")
        else:
            # Create new equipment
            test_equip = Equipment(
                dis="ACE Test AHU",
                site_ref=site_id,
                refName=equip_refname,
                marker_tags=["ahu", "hvac", "test"],
            )
            created_equips = await client.create_equipment([test_equip])
            equip_dict = created_equips[0]
            equip_id = equip_dict["id"]["val"] if isinstance(equip_dict["id"], dict) else equip_dict["id"]
            print(f"   ✓ Created new equipment: {equip_id}")
            print(f"     - Display: {equip_dict.get('dis')}")

        # Step 3: Find or create points
        print("\n📊 Step 3: Finding or creating points...")

        # Fetch all points and filter by refName
        all_points = await client.read("point")

        # Temperature point - find one that belongs to our equipment
        existing_temps = [
            p for p in all_points
            if p.get("refName") == temp_point_refname
            and (p.get("equipRef", {}).get("val") if isinstance(p.get("equipRef"), dict) else p.get("equipRef")) == equip_id
        ]

        if existing_temps:
            temp_dict = existing_temps[0]
            temp_point_id = temp_dict["id"]["val"] if isinstance(temp_dict["id"], dict) else temp_dict["id"]
            print(f"   ✓ Found existing temp sensor: {temp_point_id}")
        else:
            temp_point = Point(
                dis="ACE Test Temp Sensor",
                kind="Number",
                unit="°F",
                site_ref=site_id,
                equip_ref=equip_id,
                refName=temp_point_refname,
                marker_tags=["sensor", "temp", "air", "test"],
            )
            created = await client.create_points([temp_point])
            temp_dict = created[0]
            temp_point_id = temp_dict["id"]["val"] if isinstance(temp_dict["id"], dict) else temp_dict["id"]
            print(f"   ✓ Created new temp sensor: {temp_point_id}")

        # Status point - find one that belongs to our equipment
        existing_status = [
            p for p in all_points
            if p.get("refName") == status_point_refname
            and (p.get("equipRef", {}).get("val") if isinstance(p.get("equipRef"), dict) else p.get("equipRef")) == equip_id
        ]

        if existing_status:
            status_dict = existing_status[0]
            status_point_id = status_dict["id"]["val"] if isinstance(status_dict["id"], dict) else status_dict["id"]
            print(f"   ✓ Found existing status point: {status_point_id}")
        else:
            status_point = Point(
                dis="ACE Test Status",
                kind="Bool",
                site_ref=site_id,
                equip_ref=equip_id,
                refName=status_point_refname,
                marker_tags=["sensor", "run", "status", "test"],
            )
            created = await client.create_points([status_point])
            status_dict = created[0]
            status_point_id = status_dict["id"]["val"] if isinstance(status_dict["id"], dict) else status_dict["id"]
            print(f"   ✓ Created new status point: {status_point_id}")

        # Step 4: Write history data using the entity IDs
        print("\n📝 Step 4: Writing history samples...")
        now = datetime.now(UTC)

        # Temperature readings (last 6 hours)
        temp_samples = [
            HistorySample(
                point_id=temp_point_id,
                timestamp=now - timedelta(hours=6 - i),
                value=68.0 + (i % 6) * 0.5,
            )
            for i in range(6)
        ]

        # Status readings
        status_samples = [
            HistorySample(
                point_id=status_point_id,
                timestamp=now - timedelta(hours=6 - i),
                value=i % 2 == 0,
            )
            for i in range(6)
        ]

        all_samples = temp_samples + status_samples
        result = await client.write_history(all_samples)

        print(f"   ✓ Wrote {result.samples_written} history samples")
        print(f"     - Used point ID: {temp_point_id}")
        print(f"     - Used point ID: {status_point_id}")

        # Step 5: Read back entities by ID to verify
        print("\n🔍 Step 5: Verifying by reading back entities...")

        site_verify = await client.read_by_id(site_id)
        assert site_verify is not None
        print(f"   ✓ Verified site by ID: {site_verify.get('dis')}")

        equip_verify = await client.read_by_id(equip_id)
        assert equip_verify is not None
        print(f"   ✓ Verified equipment by ID: {equip_verify.get('dis')}")

        temp_verify = await client.read_by_id(temp_point_id)
        assert temp_verify is not None
        print(f"   ✓ Verified temp point by ID: {temp_verify.get('dis')}")

        status_verify = await client.read_by_id(status_point_id)
        assert status_verify is not None
        print(f"   ✓ Verified status point by ID: {status_verify.get('dis')}")

        # Step 6: Verify we're using the correct IDs consistently
        print("\n🎯 Step 6: Verifying entity references...")

        # Check equipment references site correctly
        equip_site_ref = equip_verify.get("siteRef", {})
        equip_site_id = equip_site_ref.get("val") if isinstance(equip_site_ref, dict) else equip_site_ref
        assert equip_site_id == site_id, f"Equipment siteRef mismatch: {equip_site_id} != {site_id}"
        print(f"   ✓ Equipment correctly references site")

        # Check temp point references
        temp_equip_ref = temp_verify.get("equipRef", {})
        temp_equip_id = temp_equip_ref.get("val") if isinstance(temp_equip_ref, dict) else temp_equip_ref
        assert temp_equip_id == equip_id, f"Temp point equipRef mismatch"
        print(f"   ✓ Temp point correctly references equipment")

        temp_site_ref = temp_verify.get("siteRef", {})
        temp_site_id = temp_site_ref.get("val") if isinstance(temp_site_ref, dict) else temp_site_ref
        assert temp_site_id == site_id, f"Temp point siteRef mismatch"
        print(f"   ✓ Temp point correctly references site")

        print(f"\n{'=' * 60}")
        print("✅ Idempotent test completed successfully!")
        print(f"{'=' * 60}")
        print("\nEntity IDs used (will be reused on next run):")
        print(f"  Site:     {site_id}")
        print(f"  Equip:    {equip_id}")
        print(f"  Temp:     {temp_point_id}")
        print(f"  Status:   {status_point_id}")
        print(f"{'=' * 60}\n")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_idempotent_roundtrip())
